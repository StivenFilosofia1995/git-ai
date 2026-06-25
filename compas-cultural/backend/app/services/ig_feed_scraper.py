# -*- coding: utf-8 -*-
"""
IG Feed Scraper — escanea el feed personal de Instagram con login real.
Usa Playwright para simular un usuario humano y captura las respuestas de la API.

SEGURIDAD:
  - Las credenciales NUNCA se almacenan, loguean ni persisten.
  - Solo se usan en memoria durante la sesión Playwright y se descartan al cerrar.
  - El job_id almacena solo el estado/resultado, nunca las credenciales.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

CO_TZ = ZoneInfo("America/Bogota")

_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"
)

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['es-CO', 'es', 'en']});
"""


# ─── Job store (config_kv) ─────────────────────────────────────────────────────

def _job_update(job_id: str, data: dict) -> None:
    if not job_id:
        return
    try:
        from app.database import supabase
        supabase.table("config_kv").upsert(
            {"key": f"ig_feed_job:{job_id}", "value": json.dumps(data)},
            on_conflict="key",
        ).execute()
    except Exception:
        pass


def _job_get(job_id: str) -> dict:
    try:
        from app.database import supabase
        res = supabase.table("config_kv").select("value").eq("key", f"ig_feed_job:{job_id}").execute()
        if res.data:
            return json.loads(res.data[0]["value"])
    except Exception:
        pass
    return {}


def _job_delete(job_id: str) -> None:
    try:
        from app.database import supabase
        supabase.table("config_kv").delete().eq("key", f"ig_feed_job:{job_id}").execute()
    except Exception:
        pass


# ─── Feed item normalization ───────────────────────────────────────────────────

def _normalize_item(item: dict) -> Optional[dict]:
    """Normaliza un item del feed de Instagram a formato canónico."""
    if not isinstance(item, dict):
        return None

    # Caption
    caption = ""
    cap = item.get("caption")
    if isinstance(cap, dict):
        caption = cap.get("text", "")
    elif isinstance(cap, str):
        caption = cap
    if not caption:
        for edge in item.get("edge_media_to_caption", {}).get("edges", []):
            caption = edge.get("node", {}).get("text", "")
            if caption:
                break

    # User
    user = item.get("user") or {}
    username = user.get("username", "") if isinstance(user, dict) else ""
    full_name = user.get("full_name", "") if isinstance(user, dict) else ""

    # Image
    image_url = ""
    img = item.get("image_versions2") or {}
    candidates = img.get("candidates", []) if isinstance(img, dict) else []
    if candidates:
        image_url = (candidates[0] or {}).get("url", "")
    if not image_url:
        image_url = item.get("display_url", "")

    # Permalink
    shortcode = item.get("code") or item.get("shortcode") or ""
    permalink = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""
    taken_at = item.get("taken_at") or 0

    if not caption and not image_url:
        return None

    return {
        "caption": caption.strip(),
        "username": username,
        "full_name": full_name,
        "image_url": image_url,
        "shortcode": shortcode,
        "permalink": permalink,
        "taken_at": taken_at,
    }


# ─── Main scanner ──────────────────────────────────────────────────────────────

async def scan_ig_feed(
    email: str,
    password: str,
    max_posts: int = 60,
    job_id: Optional[str] = None,
) -> dict:
    """
    Inicia sesión en Instagram y escanea el feed personal buscando eventos culturales.

    Las credenciales se usan SOLO en memoria durante la sesión y NO se almacenan.

    Returns: {status, posts_scanned, events, error}
    """
    # IMPORTANTE: no loguear email ni password jamás
    _job_update(job_id, {"status": "iniciando", "progress": 5, "posts_captured": 0})

    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        err = "Playwright no instalado en este servidor"
        _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
        return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

    from app.services.ig_event_extractor import extract_events_from_ig_profile

    feed_items: list[dict] = []

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
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=_UA_MOBILE,
                viewport={"width": 390, "height": 844},
                locale="es-CO",
                timezone_id="America/Bogota",
            )
            await context.add_init_script(_STEALTH_SCRIPT)
            page = await context.new_page()

            # Interceptar respuestas de la API del feed
            async def on_response(response):
                url = response.url
                if any(kw in url for kw in [
                    "api/v1/feed/timeline",
                    "api/v1/feed/your_activity",
                    "graphql/query",
                    "api/graphql",
                ]):
                    try:
                        data = await response.json()
                        # Formato REST (mobile API)
                        items = data.get("items", [])
                        if items:
                            feed_items.extend(items)
                        # Formato GraphQL
                        edges = (
                            (data.get("data") or {})
                            .get("xhp_feed_units", {})
                            .get("edges", [])
                        ) or (
                            (data.get("data") or {})
                            .get("user", {})
                            .get("edge_web_feed_timeline", {})
                            .get("edges", [])
                        )
                        for edge in edges:
                            node = edge.get("node") or {}
                            if node:
                                feed_items.append(node)
                    except Exception:
                        pass

            page.on("response", on_response)

            _job_update(job_id, {"status": "navegando", "progress": 12})

            # Ir a Instagram
            try:
                await page.goto(
                    "https://www.instagram.com/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
            except PWTimeout:
                pass
            await page.wait_for_timeout(2000)

            _job_update(job_id, {"status": "iniciando_sesion", "progress": 22})

            # Completar formulario de login
            try:
                user_input = await page.wait_for_selector(
                    'input[name="username"]', timeout=12_000
                )
                await user_input.click()
                await page.wait_for_timeout(400)
                await page.type('input[name="username"]', email, delay=90)
                await page.wait_for_timeout(400)
                await page.type('input[name="password"]', password, delay=90)
                await page.wait_for_timeout(600)
                await page.click('button[type="submit"]')
            except PWTimeout:
                await browser.close()
                err = "No se encontró el formulario de login en Instagram"
                _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
                return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

            _job_update(job_id, {"status": "esperando_autenticacion", "progress": 38})

            # Esperar respuesta del servidor
            try:
                await page.wait_for_load_state("networkidle", timeout=20_000)
            except PWTimeout:
                pass
            await page.wait_for_timeout(3000)

            # Detectar errores de login
            current_url = page.url
            try:
                page_text = await page.inner_text("body")
            except Exception:
                page_text = ""

            if any(x in page_text.lower() for x in [
                "incorrect", "contraseña incorrecta", "wrong password",
                "password was incorrect", "credenciales incorrectas"
            ]):
                await browser.close()
                err = "Credenciales incorrectas — revisa tu correo y contraseña de Instagram"
                _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
                return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

            if "checkpoint" in current_url or "challenge" in current_url:
                await browser.close()
                err = (
                    "Instagram activó un checkpoint de seguridad. "
                    "Abre Instagram en tu celular, confirma el inicio de sesión, y vuelve a intentarlo."
                )
                _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
                return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

            if "two_factor" in current_url or "two-factor" in current_url:
                await browser.close()
                err = (
                    "Esta cuenta tiene verificación en dos pasos (2FA). "
                    "Usa una cuenta de Instagram sin 2FA, o desactívala temporalmente."
                )
                _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
                return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

            # Cerrar popups (Guardar info de sesión, Notificaciones)
            for sel in [
                'button:has-text("Ahora no")',
                'button:has-text("Not Now")',
                'button:has-text("Cancelar")',
                'button:has-text("Omitir")',
                'button:has-text("Skip")',
                'button:has-text("No, gracias")',
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=2500):
                        await btn.click()
                        await page.wait_for_timeout(800)
                except Exception:
                    pass

            _job_update(job_id, {"status": "escaneando_feed", "progress": 52, "posts_captured": 0})

            # Hacer scroll para cargar más posts
            rounds = max(3, min(10, max_posts // 6))
            for i in range(rounds):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2.5)")
                await page.wait_for_timeout(2200)
                captured = len(feed_items)
                _job_update(job_id, {
                    "status": "escaneando_feed",
                    "progress": 52 + int((i + 1) / rounds * 35),
                    "posts_captured": captured,
                })
                if captured >= max_posts:
                    break

            await browser.close()

    except Exception as e:
        err = f"Error Playwright: {type(e).__name__}: {str(e)[:200]}"
        _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
        return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

    _job_update(job_id, {"status": "procesando", "progress": 90})

    if not feed_items:
        err = (
            "No se capturaron posts del feed. "
            "Instagram puede haber bloqueado el acceso desde el servidor. "
            "Intenta de nuevo en unos minutos."
        )
        _job_update(job_id, {"status": "error", "error": err, "events": [], "posts_scanned": 0})
        return {"status": "error", "error": err, "events": [], "posts_scanned": 0}

    # Normalizar y deduplicar posts
    seen_codes: set[str] = set()
    unique_posts: list[dict] = []
    for raw in feed_items[:max_posts * 2]:  # extra para compensar duplicados
        post = _normalize_item(raw)
        if not post:
            continue
        code = post.get("shortcode", "")
        if code and code in seen_codes:
            continue
        if code:
            seen_codes.add(code)
        unique_posts.append(post)
        if len(unique_posts) >= max_posts:
            break

    # Extraer eventos de cada caption
    all_events: list[dict] = []
    for post in unique_posts:
        caption = post.get("caption", "")
        if not caption or len(caption) < 15:
            continue

        profile = {
            "captions": [caption],
            "biography": "",
            "image_urls": [post.get("image_url", "")],
            "permalink_urls": [post.get("permalink", "")],
            "timestamps": [post.get("taken_at", 0)],
        }
        ig_user = post.get("username", "")

        try:
            events = extract_events_from_ig_profile(
                profile=profile,
                nombre_lugar=post.get("full_name") or ig_user or "Cuenta de Instagram",
                categoria="otro",
                municipio="medellin",
            )
        except Exception:
            events = []

        for ev in events:
            ev["ig_usuario"] = f"@{ig_user}" if ig_user else ""
            ev["caption_original"] = caption[:400]
            if not ev.get("fuente_url") and post.get("permalink"):
                ev["fuente_url"] = post["permalink"]
            if not ev.get("imagen_url") and post.get("image_url"):
                ev["imagen_url"] = post["image_url"]
            ev["fuente"] = "ig_feed_manual"

        all_events.extend(events)

    result = {
        "status": "done",
        "posts_scanned": len(unique_posts),
        "events": all_events,
    }
    _job_update(job_id, {
        "status": "done",
        "progress": 100,
        "posts_scanned": len(unique_posts),
        "events_count": len(all_events),
        "events": all_events,
    })
    print(f"  [IG Feed] Completado — {len(unique_posts)} posts → {len(all_events)} eventos")
    return result


def get_job_status(job_id: str) -> dict:
    """Devuelve el estado actual de un job de escaneo."""
    return _job_get(job_id)
