"""
instagram_pw_scraper.py
=======================
Scraper de perfiles de Instagram — CERO tokens de AI.
Extrae datos públicos usando tres estrategias en cascada:

  1. httpx → Instagram web_profile_info API  (rápido, sin browser)
  2. httpx → HTML plano + regex              (fallback ligero)
  3. Playwright Chromium headless            (fallback pesado, más fiable)

Extracciones:
  - external_url  (sitio web del perfil)
  - biography
  - captions      (últimos posts, texto plano)
  - image_urls

Uso directo (test):
    cd backend
    python app/services/instagram_pw_scraper.py casadelteatro
    python app/services/instagram_pw_scraper.py accionimpro
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import sys
from typing import Optional

import httpx

# ── User-agents rotativos para evitar bloqueos ────────────────────────────
_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]

# ── Instagram App IDs (rotativos) ─────────────────────────────────────────
_IG_APP_IDS = ["936619743392459", "1217981644879628", "124024574287414"]


def _random_ua() -> str:
    return random.choice(_UA_LIST)

def _random_app_id() -> str:
    return random.choice(_IG_APP_IDS)


async def _fetch_via_httpx_api(handle: str) -> Optional[dict]:
    """
    Strategy 1: Hit Instagram's internal web_profile_info endpoint directly.
    Works for many public profiles without a browser.
    """
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={handle}"
    ua = _random_ua()
    headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
        "X-IG-App-ID": _random_app_id(),
        "X-ASBD-ID": "129477",
        "X-IG-WWW-Claim": "0",
        "Referer": f"https://www.instagram.com/{handle}/",
        "Origin": "https://www.instagram.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=12.0,
            headers={"User-Agent": ua},
        ) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                result = _parse_api_response(data)
                if result and (result.get("captions") or result.get("biography")):
                    print(f"    ✅ httpx-api: {len(result.get('captions', []))} posts")
                    return result
    except Exception as e:
        print(f"    ℹ httpx-api falló ({e.__class__.__name__}), intentando HTML...")
    return None


async def _fetch_via_httpx_html(handle: str) -> Optional[dict]:
    """
    Strategy 2: Fetch the plain HTML page and extract embedded JSON.
    No browser needed. Works when Instagram embeds profile data in script tags.
    """
    url = f"https://www.instagram.com/{handle}/"
    ua = _random_ua()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.instagram.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "no-cache",
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                html = resp.text
                result = _parse_ig_html(html, handle)
                if result and (result.get("captions") or result.get("biography")):
                    print(f"    ✅ httpx-html: {len(result.get('captions', []))} posts")
                    return result
    except Exception as e:
        print(f"    ℹ httpx-html falló ({e.__class__.__name__}), intentando Playwright...")
    return None


async def fetch_ig_profile(handle: str, timeout_ms: int = 28_000) -> Optional[dict]:
    """
    Fetch public Instagram profile data.

    Three-strategy cascade (fast → heavy):
      1. httpx → Instagram web_profile_info API  (no browser, ~3s)
      2. httpx → plain HTML + embedded JSON       (no browser, ~5s)
      3. Playwright Chromium headless             (browser, ~25s, last resort)

    Returns a dict with keys: external_url, biography, captions (list[str]), image_urls (list[str])
    Returns None if all strategies fail (private/blocked profile).
    """
    clean = handle.lstrip("@").strip().split("/")[0]
    print(f"    🔎 IG fetch: @{clean}")

    # ── Strategy 1: httpx API ──────────────────────────────────────────────
    result = await _fetch_via_httpx_api(clean)
    if result:
        return result

    # ── Strategy 2: httpx plain HTML ──────────────────────────────────────
    result = await _fetch_via_httpx_html(clean)
    if result:
        return result

    # ── Strategy 3: Playwright (last resort) ──────────────────────────────
    print(f"    🎭 Playwright fallback para @{clean}...")
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[ig_pw] playwright not installed")
        return None

    captured_api: dict = {}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--disable-setuid-sandbox",
                    "--single-process",
                ],
            )
            context = await browser.new_context(
                user_agent=_random_ua(),
                viewport={"width": 1280, "height": 900},
                locale="es-CO",
                extra_http_headers={
                    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
                    "X-IG-App-ID": _random_app_id(),
                },
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            async def on_response(response):
                url = response.url
                if "web_profile_info" in url or (
                    "graphql/query" in url and "edge_owner_to_timeline_media" in url
                ):
                    try:
                        body = await response.json()
                        captured_api.update(body)
                    except Exception:
                        pass

            page.on("response", on_response)

            try:
                await page.goto(
                    f"https://www.instagram.com/{clean}/",
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                try:
                    await page.wait_for_selector("article, main", timeout=10_000)
                except PWTimeout:
                    pass
                await page.wait_for_timeout(3000)
            except PWTimeout:
                pass

            html = await page.content()
            await browser.close()

        if captured_api:
            pw_result = _parse_api_response(captured_api)
            if pw_result:
                print(f"    ✅ Playwright-api: {len(pw_result.get('captions', []))} posts")
                return pw_result

        pw_result = _parse_ig_html(html, clean)
        if pw_result:
            print(f"    ✅ Playwright-html: {len(pw_result.get('captions', []))} posts")
        return pw_result

    except Exception as e:
        print(f"    ⚠ Playwright error: {e.__class__.__name__}: {e}")
        return None


def _parse_api_response(data: dict) -> Optional[dict]:
    """Parse Instagram's web_profile_info API JSON response."""
    result = {"external_url": None, "biography": "", "captions": [], "image_urls": [], "permalink_urls": []}
    try:
        user = (
            data.get("data", {}).get("user")
            or data.get("graphql", {}).get("user")
            or {}
        )
        if not user:
            return None
        result["external_url"] = user.get("external_url") or None
        if result["external_url"]:
            result["external_url"] = _unescape_ig_text(result["external_url"])
        result["biography"] = user.get("biography", "")

        # Posts from edge_owner_to_timeline_media
        edges = (
            user.get("edge_owner_to_timeline_media", {}).get("edges", [])
            or user.get("edge_felix_video_timeline", {}).get("edges", [])
        )
        for edge in edges[:15]:
            node = edge.get("node", {})
            # Caption
            cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            if cap_edges:
                text = cap_edges[0].get("node", {}).get("text", "")
                if text and len(text) > 10:
                    result["captions"].append(text)
            # Image
            img = node.get("display_url") or node.get("thumbnail_src")
            if img:
                result["image_urls"].append(img)
            # Permalink
            shortcode = node.get("shortcode") or node.get("code") or ""
            permalink = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""
            result["permalink_urls"].append(permalink)

        if result["biography"] or result["captions"]:
            return result
    except Exception:
        pass
    return None


def _parse_ig_html(html: str, handle: str) -> Optional[dict]:
    """
    Extract profile data from Instagram HTML.
    Tries multiple extraction strategies.
    """
    result = {
        "external_url": None,
        "biography": "",
        "captions": [],
        "image_urls": [],
        "permalink_urls": [],
    }

    # ── Strategy 1: JSON embedded in <script data-sjs> tags ───────────────
    # Instagram embeds profile + post data as JSON in multiple script tags
    script_jsons = re.findall(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    for raw_json in script_jsons:
        try:
            data = json.loads(raw_json)
            _extract_from_json(data, result)
        except (json.JSONDecodeError, Exception):
            continue
        if result["external_url"] or result["captions"]:
            break

    # ── Strategy 2: Regex patterns on raw HTML ────────────────────────────
    if not result["external_url"]:
        # external_url pattern
        m = re.search(r'"external_url"\s*:\s*"([^"]+)"', html)
        if m:
            result["external_url"] = _unescape_ig_text(m.group(1))

    if not result["biography"]:
        m = re.search(r'"biography"\s*:\s*"([^"]*)"', html)
        if m:
            result["biography"] = _unescape_ig_text(m.group(1))

    if not result["captions"]:
        # edge_media_to_timeline_media captions
        captions_raw = re.findall(r'"text"\s*:\s*"([^"]{20,})"', html)
        seen = set()
        for c in captions_raw[:20]:
            clean_c = _unescape_ig_text(c)
            if clean_c not in seen and len(clean_c) > 30:
                result["captions"].append(clean_c)
                seen.add(clean_c)

    if not result["image_urls"]:
        # display_url or display_resources
        urls = re.findall(r'"display_url"\s*:\s*"(https://[^"]+)"', html)
        result["image_urls"] = list(dict.fromkeys(urls))[:10]  # deduplicate

    # ── Strategy 3: og: meta tags ─────────────────────────────────────────
    if not result["biography"]:
        m = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', html, re.I)
        if m:
            result["biography"] = m.group(1)

    # If nothing useful found (login wall, bot block)
    if not result["external_url"] and not result["captions"] and not result["biography"]:
        return None

    return result


def _extract_from_json(data: any, result: dict, depth: int = 0) -> None:
    """Recursively search a JSON structure for Instagram profile/post data."""
    if depth > 10:
        return
    if isinstance(data, dict):
        # Direct field extraction
        if "external_url" in data and data["external_url"]:
            result["external_url"] = data["external_url"]
        if "biography" in data and data["biography"]:
            result["biography"] = data["biography"]
        # Post caption
        if "text" in data and isinstance(data["text"], str) and len(data["text"]) > 30:
            result["captions"].append(data["text"])
        # Image URL
        if "display_url" in data and isinstance(data["display_url"], str):
            result["image_urls"].append(data["display_url"])
        # Permalink via shortcode
        if "shortcode" in data and isinstance(data["shortcode"], str) and data["shortcode"]:
            sc = data["shortcode"]
            permalink = f"https://www.instagram.com/p/{sc}/"
            # align with captions length so indexes match
            while len(result["permalink_urls"]) < len(result["captions"]):
                result["permalink_urls"].append("")
            if permalink not in result["permalink_urls"]:
                result["permalink_urls"].append(permalink)
        # Recurse into values
        for v in data.values():
            if isinstance(v, (dict, list)):
                _extract_from_json(v, result, depth + 1)
    elif isinstance(data, list):
        for item in data[:30]:  # cap to avoid deep recursion on huge arrays
            _extract_from_json(item, result, depth + 1)


def _unescape_ig_text(text: str) -> str:
    """Decode \\uXXXX unicode escapes and clean up Instagram's JSON encoding."""
    # Replace \\/ with /
    text = text.replace("\\/", "/")
    # Decode \uXXXX sequences
    try:
        text = re.sub(
            r'\\u([0-9a-fA-F]{4})',
            lambda m: chr(int(m.group(1), 16)),
            text
        )
    except Exception:
        pass
    text = text.replace("\\n", "\n").replace("\\t", " ")
    return text


def profile_to_scraper_text(profile: dict, handle: str) -> str:
    """
    Convert profile dict to the same text format that auto_scraper.py expects
    (for Groq event extraction).
    """
    parts = []
    if profile.get("biography"):
        parts.append(f"BIO: {profile['biography']}")
    if profile.get("external_url"):
        parts.append(f"WEB: {profile['external_url']}")
    for i, caption in enumerate(profile.get("captions", [])[:15], 1):
        parts.append(f"[POST {i}]\n{caption}")
    if profile.get("image_urls"):
        parts.append(f"[IMAGE_URL: {profile['image_urls'][0]}]")
    return "\n---\n".join(parts)


# ── CLI test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    handle = sys.argv[1] if len(sys.argv) > 1 else "casadelteatro"
    print(f"Scraping @{handle} (httpx → Playwright cascade)...")

    result = asyncio.run(fetch_ig_profile(handle))
    if not result:
        print("❌ Sin resultados (posible bot block o login wall)")
        sys.exit(1)

    print(f"✅ external_url : {result['external_url']}")
    print(f"   biography    : {result['biography'][:120]}")
    print(f"   posts cap.   : {len(result['captions'])}")
    print(f"   images       : {len(result['image_urls'])}")
    if result["captions"]:
        print(f"\nPrimer post:\n{result['captions'][0][:300]}")
