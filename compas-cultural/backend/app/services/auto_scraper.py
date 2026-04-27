"""
Auto-scraper: sistema automático de scraping para todos los lugares registrados.
Recorre periódicamente los sitios web e Instagram de cada lugar,
extrae eventos futuros con Groq (llama-3.3-70b) y los inserta en la BD.
"""
import json
import re
import traceback
import asyncio
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.data_quality import is_likely_cultural_event
from app.services.html_event_extractor import extract_events_code, parse_date
from app.services.playwright_fetcher import fetch_with_playwright, needs_playwright
from app.services.event_ocr import extract_hour_from_image_url, extract_text_from_image_url
from app.services.rss_scraper import get_or_discover_feed, parse_rss_events

CO_TZ = ZoneInfo("America/Bogota")

# Keyword list exported for RSS/other scrapers that import from this module.
EVENT_KEYWORDS = [
    "evento", "concierto", "taller", "exposicion", "exposición", "festival",
    "obra", "funcion", "función", "charla", "foro", "cine", "danza",
    "musica", "música", "lanzamiento", "performance", "show", "en vivo",
]

_EVENING_CONTEXT_RE = re.compile(
    r"\b(noche|tarde|show|concierto|funcion|presentacion|festival|en vivo)\b",
    re.I,
)
_TIME_WITH_MINUTES_RE = re.compile(
    r"\b(\d{1,2})\s*[:\.h]\s*(\d{2})\s*([ap](?:\.?\s*m\.?)?)?\b",
    re.I,
)
_TIME_AMPM_ONLY_RE = re.compile(
    r"\b(\d{1,2})\s*([ap](?:\.?\s*m\.?)?)\b",
    re.I,
)


def _normalize_meridian(raw: str) -> str:
    return re.sub(r"[^apm]", "", (raw or "").lower())


def _to_24h(hour: int, minute: int, meridian: str, has_evening_context: bool) -> Optional[tuple[int, int]]:
    h = hour
    mer = _normalize_meridian(meridian)
    if mer.startswith("p") and h < 12:
        h += 12
    elif mer.startswith("a") and h == 12:
        h = 0
    elif not mer and 1 <= h <= 11 and has_evening_context:
        h += 12
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None
    return h, minute


def _extract_time(text: str) -> Optional[tuple[int, int]]:
    """Extract event time from free text.

    CRITICAL: Returns None when unclear. NEVER invents a default time.
    Callers must handle None (store 00:00:00 with hora_confirmada=False).
    """
    if not text:
        return None

    has_evening_context = bool(_EVENING_CONTEXT_RE.search(text))

    for m in _TIME_WITH_MINUTES_RE.finditer(text):
        parsed = _to_24h(int(m.group(1)), int(m.group(2)), m.group(3) or "", has_evening_context)
        if parsed:
            return parsed

    for m in _TIME_AMPM_ONLY_RE.finditer(text):
        parsed = _to_24h(int(m.group(1)), 0, m.group(2) or "", has_evening_context)
        if parsed:
            return parsed

    return None


def _detect_category(text: str) -> str:
    """Best-effort category detection used by RSS and fallback scrapers."""
    tl = (text or "").lower()
    if any(k in tl for k in ("teatro", "obra", "dramatur")):
        return "teatro"
    if any(k in tl for k in ("jazz",)):
        return "jazz"
    if any(k in tl for k in ("hip hop", "rap", "freestyle")):
        return "hip_hop"
    if any(k in tl for k in ("electronica", "electrónica", "dj", "techno", "house")):
        return "electronica"
    if any(k in tl for k in ("danza", "baile", "ballet")):
        return "danza"
    if any(k in tl for k in ("cine", "pelicula", "película")):
        return "cine"
    if any(k in tl for k in ("galeria", "galería", "museo", "exposicion", "exposición")):
        return "galeria"
    if any(k in tl for k in ("poesia", "poesía", "literatura", "libro")):
        return "poesia"
    if any(k in tl for k in ("concierto", "musica", "música", "banda", "orquesta")):
        return "musica_en_vivo"
    if any(k in tl for k in ("festival",)):
        return "festival"
    return "otro"


def _parse_date_from_text(text: str, year: int) -> Optional[datetime]:
    """Parse event date from free text using the shared HTML extractor parser."""
    return parse_date(text, year)


def _normalize_scraped_datetime(fecha: datetime, fuente: str = "") -> datetime:
    """Normalize scraped datetimes to Colombia TZ without inventing event times."""
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=CO_TZ)
    else:
        fecha = fecha.astimezone(CO_TZ)

    return fecha


def _apply_ocr_hour_if_missing(fecha: datetime, image_url: Optional[str]) -> datetime:
    """If parsed time is 00:00 and image poster has a readable hour, apply it.

    Keeps no-invention rule: only updates when OCR extracts an explicit hour.
    """
    if not image_url:
        return fecha
    if not (fecha.hour == 0 and fecha.minute == 0):
        return fecha
    hm = extract_hour_from_image_url(image_url)
    if not hm:
        return fecha
    h, m = hm
    try:
        return fecha.replace(hour=h, minute=m, second=0, microsecond=0)
    except Exception:
        return fecha


def _apply_text_hour_if_missing(fecha: datetime, *texts: Optional[str]) -> tuple[datetime, bool]:
    """Try extracting hour from free text when datetime has 00:00."""
    if not (fecha.hour == 0 and fecha.minute == 0):
        return fecha, True

    for txt in texts:
        hm = _extract_time(txt or "")
        if not hm:
            continue
        h, m = hm
        try:
            return fecha.replace(hour=h, minute=m, second=0, microsecond=0), True
        except Exception:
            continue

    return fecha, False


def _finalize_event_datetime(
    fecha: datetime,
    *,
    image_url: Optional[str],
    fallback_hour: tuple[int, int] = (19, 0),
    texts: tuple[Optional[str], ...] = (),
) -> tuple[datetime, bool]:
    """Resolve best available event time, forcing non-00:00 for UX consistency.

    Returns (fecha_final, hora_confirmada).
    """
    fecha = _apply_ocr_hour_if_missing(fecha, image_url)
    fecha, confirmed = _apply_text_hour_if_missing(fecha, *texts)
    if confirmed:
        return fecha, True

    # Último fallback: evitar publicar "por definir" en experiencia pública.
    # Mantiene hora_confirmada=False para distinguir estimaciones.
    h, m = fallback_hour
    try:
        fecha = fecha.replace(hour=h, minute=m, second=0, microsecond=0)
    except Exception:
        pass
    return fecha, False


def _sanitize_text(value: Optional[str]) -> Optional[str]:
    """Drop lone surrogate characters that break UTF-8 inserts.

    Python strings can contain lone surrogates (U+D800-U+DFFF) from improperly
    decoded sources. ``errors='surrogatepass'`` encodes them as CESU-8 bytes;
    the subsequent decode with ``errors='ignore'`` then drops those invalid
    byte sequences, leaving a clean UTF-8 string.
    """
    if value is None:
        return None
    return value.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="ignore")


def _sanitize_payload(value: Any) -> Any:
    """Recursively sanitize strings in payloads before DB insert."""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {k: _sanitize_payload(v) for k, v in value.items()}
    return value


def _now_co() -> datetime:
    """Current datetime in Colombia (America/Bogota), timezone-aware."""
    return datetime.now(CO_TZ)


def _parse_iso_to_co(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime and normalize to Colombia timezone."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=CO_TZ)
    return parsed.astimezone(CO_TZ)


def _enrich_event_description(
    descripcion: Optional[str],
    fecha: datetime,
    *,
    hora_confirmada: bool,
) -> str:
    """Ensure stored descriptions include explicit schedule context.

    Only adds "Hora del evento: HH:MM." when hora_confirmada=True (real scraped hour).
    When hora is unconfirmed we skip the time prefix entirely — the frontend already
    shows "Hora por confirmar" in the badge and we don't want a fake estimated time
    leaking into the description text.
    """
    base = (descripcion or "").strip()
    if not base:
        base = "Evento cultural en el Valle de Aburrá."
    if hora_confirmada:
        hora_txt = fecha.astimezone(CO_TZ).strftime("%H:%M")
        pref = f"Hora del evento: {hora_txt}."
        if "hora del evento" in base.lower():
            return base
        return f"{pref} {base}".strip()
    # hora_confirmada=False: no añadir hora estimada para no mostrar datos inventados
    return base


def _normalize_site_url(raw: Optional[str]) -> Optional[str]:
    """Normalize website URL values from DB, dropping placeholders like 'null'."""
    if not raw:
        return None
    value = str(raw).strip()
    if not value or value.lower() in {"null", "none", "nan", "n/a", "-"}:
        return None
    return value


def _normalize_ig_handle(raw: Optional[str]) -> Optional[str]:
    """Normalize IG handle: remove @, accents and unsupported characters."""
    if not raw:
        return None
    value = str(raw).strip()
    if not value or value.lower() in {"null", "none", "nan", "n/a", "-"}:
        return None
    value = value.lstrip("@").split("/")[0].strip()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^A-Za-z0-9._]", "", value)
    return value or None


def _parse_iso_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CO_TZ)
        return dt.astimezone(CO_TZ)
    except Exception:
        return None


def _sort_lugares_by_staleness(lugares: list[dict]) -> list[dict]:
    """Sort places by oldest scrape time to avoid repeatedly focusing on the same few."""
    if not lugares:
        return lugares

    latest_by_source: dict[str, datetime] = {}
    try:
        logs_resp = (
            supabase.table("scraping_log")
            .select("fuente,ejecutado_en")
            .order("ejecutado_en", desc=True)
            .limit(5000)
            .execute()
        )
        for row in logs_resp.data or []:
            fuente = str(row.get("fuente") or "").strip()
            if not fuente or fuente in latest_by_source:
                continue
            dt = _parse_iso_dt(row.get("ejecutado_en"))
            if dt:
                latest_by_source[fuente] = dt
    except Exception as e:
        print(f"  ⚠ No se pudo leer scraping_log para rotación: {e}")

    very_old = datetime(1970, 1, 1, tzinfo=CO_TZ)

    def _last_for_lugar(lugar: dict) -> datetime:
        sources: list[str] = []
        site = _normalize_site_url(lugar.get("sitio_web"))
        handle = _normalize_ig_handle(lugar.get("instagram_handle"))
        if site:
            sources.append(site)
        if handle:
            sources.append(handle)

        last: Optional[datetime] = None
        for src in sources:
            dt = latest_by_source.get(src)
            if dt and (last is None or dt > last):
                last = dt
        return last or very_old

    return sorted(lugares, key=_last_for_lugar)


def _slugify(text: str) -> str:
    text = text.lower().strip()
    for a, b in [("áàäâ", "a"), ("éèëê", "e"), ("íìïî", "i"), ("óòöô", "o"), ("úùüû", "u"), ("ñ", "n")]:
        for ch in a:
            text = text.replace(ch, b)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


# ──────────────────────────────────────────────────────────────────────────
# Fetchers
# ──────────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}


async def _fetch_website_raw(url: str) -> Optional[str]:
    """Fetch raw HTML from a website (for code-first extraction)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=20,
            # verify=True por defecto: si una fuente falla por SSL,
            # se loggea y se salta, en vez de deshabilitar verificación global.
        ) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ⚠ Error fetching {url}: {e}")
        return None


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text, keeping og:image annotation."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    og_tag = soup.find("meta", property="og:image")
    og_image = og_tag["content"] if og_tag and og_tag.get("content") else None
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    if og_image:
        text = f"[OG_IMAGE: {og_image}]\n{text}"
    return text


def _extract_og_image(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    for attr, val in [
        ("property", "og:image"),
        ("name", "twitter:image"),
        ("property", "twitter:image"),
    ]:
        tag = soup.find("meta", attrs={attr: val})
        if tag and tag.get("content"):
            return str(tag.get("content"))

    # Fallback: first meaningful image in page content.
    for img in soup.select("img[src]"):
        src = str(img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        lower = src.lower()
        if any(skip in lower for skip in ["logo", "icon", "avatar", "favicon", "sprite"]):
            continue
        return src

    return None


def _build_screenshot_url(source_url: Optional[str]) -> Optional[str]:
    """Generate a webpage screenshot URL as last-resort visual fallback."""
    if not source_url:
        return None
    raw = str(source_url).strip()
    if not raw.startswith(("http://", "https://")):
        return None
    return f"https://image.thum.io/get/width/1200/noanimate/{quote(raw, safe=':/?&=%')}"


_OG_IMAGE_CACHE: dict[str, Optional[str]] = {}


async def _resolve_event_image(image_url: Optional[str], source_url: Optional[str]) -> Optional[str]:
    """Ensure event has an image URL; fallback to source page og:image."""
    if image_url:
        return image_url
    if not source_url:
        return None
    if source_url in _OG_IMAGE_CACHE:
        return _OG_IMAGE_CACHE[source_url]

    html = await _fetch_website_raw(source_url)
    if not html:
        shot = _build_screenshot_url(source_url)
        _OG_IMAGE_CACHE[source_url] = shot
        return shot

    og = _extract_og_image(html)
    if og:
        _OG_IMAGE_CACHE[source_url] = og
        return og

    shot = _build_screenshot_url(source_url)
    _OG_IMAGE_CACHE[source_url] = shot
    return shot


async def _fetch_website(url: str) -> Optional[str]:
    """Fetch and extract text from a website (used by agenda sources)."""
    html = await _fetch_website_raw(url)
    if not html:
        return None
    return _html_to_text(html)[:6000]


async def _fetch_instagram_via_meta_api(handle: str) -> Optional[str]:
    """
    Fetch Instagram posts via Meta Graph API (Instagram Business/Creator API).
    Returns captions + media URLs as text (for Groq fallback).
    """
    profile = await _fetch_ig_profile_via_meta_api(handle)
    if not profile:
        return None
    from app.services.instagram_pw_scraper import profile_to_scraper_text
    return profile_to_scraper_text(profile, handle)


async def _fetch_ig_profile_via_meta_api(handle: str) -> Optional[dict]:
    """
    Fetch Instagram profile via Meta Graph API.
    Returns structured dict: {captions, image_urls, permalink_urls, biography, external_url}
    Same shape as instagram_pw_scraper.fetch_ig_profile() for use with ig_event_extractor.
    """
    access_token = settings.meta_access_token
    my_ig_id = settings.meta_ig_business_account_id
    if not access_token or not my_ig_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            media_fields = "caption,timestamp,media_url,permalink,media_type,thumbnail_url"
            fields_param = (
                f"business_discovery.fields("
                f"username,biography,website,"
                f"media.limit(15){{{media_fields}}}"
                f")"
            )
            resp = await client.get(
                f"https://graph.facebook.com/v21.0/{my_ig_id}",
                params={
                    "fields": fields_param,
                    "access_token": access_token,
                    "username": handle,
                },
            )

            if resp.status_code != 200:
                print(f"    ⚠ Meta API error ({resp.status_code}): {resp.text[:200]}")
                return None

            data = resp.json()
            discovery = data.get("business_discovery", {})
            media_data = discovery.get("media", {}).get("data", [])

            if not media_data and not discovery.get("biography"):
                return None

            profile: dict = {
                "biography": discovery.get("biography", ""),
                "external_url": discovery.get("website"),
                "captions": [],
                "image_urls": [],
                "permalink_urls": [],
            }

            for post in media_data:
                caption = post.get("caption", "")
                if caption and len(caption) > 10:
                    profile["captions"].append(caption)
                    media_url = post.get("media_url", "")
                    if post.get("media_type") == "VIDEO":
                        media_url = post.get("thumbnail_url", media_url)
                    profile["image_urls"].append(media_url or "")
                    profile["permalink_urls"].append(post.get("permalink", ""))

            return profile if (profile["captions"] or profile["biography"]) else None

    except Exception as e:
        print(f"    ⚠ Meta Graph API error: {e}")
        return None



async def _fetch_instagram_profile(handle: str) -> Optional[str]:
    """
    Fetch Instagram profile page content.
    Priority: 1) Meta Graph API  2) Playwright XHR interception  3) httpx fallback
    """
    clean = handle.lstrip("@").strip().split("/")[0]

    # 1. Try Meta Graph API first (best quality: captions + image URLs)
    meta_content = await _fetch_instagram_via_meta_api(clean)
    if meta_content and len(meta_content) > 200:
        print(f"    ✅ Meta Graph API: {len(meta_content)} chars")
        return meta_content

    # 2. Playwright XHR interception (intercepts Instagram's own internal API calls)
    try:
        from app.services.instagram_pw_scraper import fetch_ig_profile, profile_to_scraper_text
        profile = await fetch_ig_profile(clean)
        if profile and (profile.get("captions") or profile.get("biography")):
            # Update sitio_web in DB if external_url found
            if profile.get("external_url"):
                try:
                    from app.database import supabase as _supa
                    _supa.table("lugares").update(
                        {"sitio_web": profile["external_url"]}
                    ).eq("instagram_handle", clean).is_("sitio_web", "null").execute()
                except Exception:
                    pass
            content = profile_to_scraper_text(profile, clean)
            print(f"    ✅ Playwright IG: {len(profile.get('captions', []))} posts, web={profile.get('external_url')}")
            return content[:8000]
    except Exception as e:
        print(f"    ⚠ Playwright IG error: {e}")

    return None


# ──────────────────────────────────────────────────────────────────────────
# Core: scrape a single lugar
# ──────────────────────────────────────────────────────────────────────────
async def _scrape_lugar(lugar: dict) -> dict:
    """
    Scrape website + Instagram for a single lugar.
    Returns stats: {nuevos, duplicados, errores}
    """
    lugar_id = lugar["id"]
    nombre = lugar["nombre"]
    categoria = lugar.get("categoria_principal", "otro")
    municipio = lugar.get("municipio", "medellin")
    now_co = _now_co()
    now_iso = now_co.isoformat()
    anio = now_co.year
    all_events: list[dict] = []

    # ── 1. Scrape website ──────────────────────────────────────────────────
    sitio = _normalize_site_url(lugar.get("sitio_web"))
    sitio_is_ig = bool(sitio and "instagram.com" in sitio.lower())
    if sitio:
        if sitio_is_ig:
            print(f"  ℹ sitio_web es Instagram URL — se usa flujo IG: {sitio}")
        else:
            print(f"  🌐 Scraping web: {sitio}")
            # Fetch raw HTML for code-first extraction
            html = await _fetch_website_raw(sitio)

        # Try Playwright for JS-heavy sites (if installed)
            if html and needs_playwright(sitio):
                print(f"    🎭 JS-heavy site — usando Playwright...")
                html_js = await fetch_with_playwright(sitio)
                if html_js and len(html_js) > len(html or ""):
                    html = html_js

            if html and len(html) > 200:
                print(f"    📄 HTML: {len(html)} chars")

                # 1a. Code-first extraction (ZERO AI tokens)
                events_code = extract_events_code(html, sitio, nombre, categoria, municipio)
                if events_code:
                    for ev in events_code:
                        ev["_fuente"] = "sitio_web"
                        ev["_fuente_url"] = sitio
                    all_events.extend(events_code)
                    print(f"    ✅ Código: {len(events_code)} evento(s) extraídos")
                else:
                    print(f"    ⚠ Sin eventos deterministas de código para {sitio}")

    # ── 2. Scrape Instagram (código puro — CERO tokens AI) ────────────────
    ig_handle = _normalize_ig_handle(lugar.get("instagram_handle"))
    if ig_handle:
        print(f"  📸 Scraping IG: {ig_handle}")
        from app.services.instagram_pw_scraper import fetch_ig_profile
        from app.services.ig_event_extractor import extract_events_from_ig_profile

        clean_handle = ig_handle

        # Scraper puro (Playwright/httpx — sin APIs externas)
        profile = await fetch_ig_profile(clean_handle)

        if profile and (profile.get("captions") or profile.get("biography")):
            print(f"    ✅ Playwright: {len(profile.get('captions', []))} posts")

            # Actualizar sitio_web si el perfil tiene external_url
            if profile.get("external_url"):
                try:
                    supabase.table("lugares").update(
                        {"sitio_web": profile["external_url"]}
                    ).eq("instagram_handle", clean_handle).is_("sitio_web", "null").execute()
                    print(f"    🌐 sitio_web actualizado: {profile['external_url']}")
                except Exception:
                    pass

            # Extracción de eventos: código puro (regex + fechas)
            events_ig = extract_events_from_ig_profile(
                profile, nombre, categoria, municipio
            )
            ig_url = f"https://instagram.com/{clean_handle}"
            for ev in events_ig:
                if ev.get("_hora_detectada"):
                    ev["_fuente"] = "instagram_hora"
                else:
                    ev["_fuente"] = "instagram_sin_hora"
                # Use per-post permalink when available, fall back to profile URL
                ev["_fuente_url"] = ev.pop("_permalink", None) or ig_url
            all_events.extend(events_ig)
            print(f"    📊 Código extrajo {len(events_ig)} evento(s) de IG")

            if not events_ig:
                print(f"    ⚠ Sin eventos deterministas en IG para {ig_handle}")
        else:
            print(f"    ⚠ Sin contenido de IG para {ig_handle}")

    # 4. Insert events into DB
    stats = {"nuevos": 0, "duplicados": 0, "errores": 0, "corregidos_hora": 0}
    # For multi-day events: keep if fecha_fin >= today (still running).
    # Only skip single-day events whose fecha_inicio < today.
    hoy_inicio = now_co.replace(hour=0, minute=0, second=0, microsecond=0)

    for ev in all_events:
        try:
            titulo = _sanitize_text(ev.get("titulo"))
            if not titulo:
                continue
            if not is_likely_cultural_event(
                titulo,
                ev.get("descripcion"),
                fuente_url=ev.get("_fuente_url") or sitio,
                categoria=ev.get("categoria_principal") or categoria,
            ):
                print(f"    ⛔ No parece evento real, descartado: {titulo[:70]}")
                continue

            # Validate date — allow ongoing multi-day events
            fecha_str = ev.get("fecha_inicio")
            fecha_fin_str = ev.get("fecha_fin")
            if fecha_str:
                try:
                    fecha = datetime.fromisoformat(fecha_str)
                    # Make aware if naive (assume Colombia TZ)
                    if fecha.tzinfo is None:
                        fecha = fecha.replace(tzinfo=CO_TZ)
                    else:
                        fecha = fecha.astimezone(CO_TZ)
                    fecha = _normalize_scraped_datetime(fecha, ev.get("_fuente", "web"))
                    image_url = await _resolve_event_image(ev.get("imagen_url"), ev.get("_fuente_url") or sitio)
                    fecha, hora_confirmada = _finalize_event_datetime(
                        fecha,
                        image_url=image_url,
                        texts=(ev.get("descripcion"), titulo),
                    )
                    fecha_fin = None
                    if fecha_fin_str:
                        try:
                            fecha_fin = datetime.fromisoformat(fecha_fin_str)
                            if fecha_fin.tzinfo is None:
                                fecha_fin = fecha_fin.replace(tzinfo=CO_TZ)
                            else:
                                fecha_fin = fecha_fin.astimezone(CO_TZ)
                        except (ValueError, TypeError):
                            fecha_fin = None
                    # Skip only if:
                    #   - single-day event that started before today, OR
                    #   - multi-day event whose end is also before today
                    if fecha < hoy_inicio:
                        if fecha_fin is None or fecha_fin < hoy_inicio:
                            continue
                except (ValueError, TypeError):
                    # No inventar fecha: descartar evento.
                    continue
            else:
                continue  # Skip events without date

            slug = _slugify(titulo)
            # Dedup by (slug + date) so recurring events with different dates are allowed
            fecha_date_str = fecha.strftime("%Y-%m-%d")
            slug_with_date = f"{slug}-{fecha_date_str}"

            existing = supabase.table("eventos").select("id,fecha_inicio,fuente_url").eq("slug", slug_with_date).execute()
            if existing.data:
                current = existing.data[0]
                if str(ev.get("_fuente", "")).startswith("instagram") and ev.get("_hora_detectada"):
                    existing_fecha = _parse_iso_to_co(current.get("fecha_inicio"))
                    nueva_fecha = fecha.astimezone(CO_TZ)
                    if existing_fecha and (existing_fecha.hour != nueva_fecha.hour or existing_fecha.minute != nueva_fecha.minute):
                        supabase.table("eventos").update({
                            "fecha_inicio": fecha.isoformat(),
                            "fuente": "auto_scraper_instagram_hora",
                            "fuente_url": ev.get("_fuente_url") or current.get("fuente_url"),
                            "imagen_url": image_url,
                        }).eq("id", current["id"]).execute()
                        stats["corregidos_hora"] += 1
                        print(f"    🕒 Hora corregida: {titulo} -> {nueva_fecha.strftime('%H:%M')}")
                stats["duplicados"] += 1
                continue
            # Also check plain slug (legacy entries without date suffix)
            existing_plain = supabase.table("eventos").select("id,fecha_inicio,fuente_url").eq("slug", slug).execute()
            if existing_plain.data:
                # Check if the existing event has the same date — if so it's a true duplicate
                existing_event = supabase.table("eventos").select("fecha_inicio").eq("slug", slug).single().execute()
                if existing_event.data:
                    ex_date = existing_event.data.get("fecha_inicio", "")[:10]
                    if ex_date == fecha_date_str:
                        legacy = existing_plain.data[0]
                        if str(ev.get("_fuente", "")).startswith("instagram") and ev.get("_hora_detectada"):
                            existing_fecha = _parse_iso_to_co(legacy.get("fecha_inicio"))
                            nueva_fecha = fecha.astimezone(CO_TZ)
                            if existing_fecha and (existing_fecha.hour != nueva_fecha.hour or existing_fecha.minute != nueva_fecha.minute):
                                supabase.table("eventos").update({
                                    "fecha_inicio": fecha.isoformat(),
                                    "fuente": "auto_scraper_instagram_hora",
                                    "fuente_url": ev.get("_fuente_url") or legacy.get("fuente_url"),
                                    "imagen_url": image_url,
                                }).eq("id", legacy["id"]).execute()
                                stats["corregidos_hora"] += 1
                                print(f"    🕒 Hora corregida (legacy): {titulo} -> {nueva_fecha.strftime('%H:%M')}")
                        stats["duplicados"] += 1
                        continue
                # Different date — use slug_with_date as slug
            final_slug = slug_with_date

            evento_data = {
                "titulo": titulo,
                "slug": final_slug,
                "espacio_id": lugar_id,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
                "hora_confirmada": hora_confirmada,
                "categorias": ev.get("categorias", [categoria]),
                "categoria_principal": ev.get("categoria_principal", categoria),
                "municipio": municipio,
                "barrio": lugar.get("barrio"),
                "nombre_lugar": nombre,
                "descripcion": _enrich_event_description(
                    ev.get("descripcion"),
                    fecha,
                    hora_confirmada=hora_confirmada,
                ),
                "precio": ev.get("precio"),
                "es_gratuito": ev.get("es_gratuito", False),
                "es_recurrente": ev.get("es_recurrente", False),
                "imagen_url": image_url,
                "fuente": f"auto_scraper_{ev.get('_fuente', 'web')}",
                "fuente_url": ev.get("_fuente_url"),
                "verificado": False,
            }
            evento_data = _sanitize_payload(evento_data)
            supabase.table("eventos").insert(evento_data).execute()
            stats["nuevos"] += 1
            print(f"    ✅ Nuevo evento: {titulo}")

        except Exception as e:
            stats["errores"] += 1
            print(f"    ❌ Error insertando evento: {e}")

    return stats


# ──────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────
def _log_scraping(fuente: str, registros_nuevos: int, errores: int, detalle: dict, duracion: float = 0):
    """Register scraping run in scraping_log table."""
    try:
        supabase.table("scraping_log").insert({
            "fuente": fuente[:50],
            "registros_nuevos": registros_nuevos,
            "registros_actualizados": 0,
            "errores": errores,
            "detalle": detalle,
            "duracion_segundos": duracion,
        }).execute()
    except Exception as e:
        print(f"  ⚠ Error logging: {e}")


# ──────────────────────────────────────────────────────────────────────────
# Main entry points
# ──────────────────────────────────────────────────────────────────────────
async def run_auto_scraper(
    limit: Optional[int] = None,
    *,
    post_enrich: bool = True,
    image_enrich_limit: int = 250,
    hour_enrich_limit: int = 800,
) -> dict:
    """
    Scrape all active lugares with IG handle or website.
    Called by scheduler or manually via API.
    
    Args:
        limit: Max number of lugares to scrape (None = all)
    
    Returns:
        Summary stats dict
    """
    print("\n🔄 ═══════════════════════════════════════════════")
    print("   AUTO-SCRAPER iniciando...")
    print("═══════════════════════════════════════════════════")

    # Get all lugares with IG or website
    query = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    )

    # Fetch all, then filter in Python (Supabase REST doesn't support OR on not-null easily)
    result = query.execute()
    lugares = [
        l for l in result.data
        if l.get("instagram_handle") or l.get("sitio_web")
    ]

    # Rotate fairly: oldest/never scraped places first.
    lugares = _sort_lugares_by_staleness(lugares)

    if limit:
        lugares = lugares[:limit]

    total_stats = {"lugares_procesados": 0, "eventos_nuevos": 0, "duplicados": 0, "errores": 0, "corregidos_hora": 0}
    start_time = _now_co()

    for i, lugar in enumerate(lugares):
        print(f"\n📍 [{i+1}/{len(lugares)}] {lugar['nombre']}")
        try:
            stats = await _scrape_lugar(lugar)
            total_stats["lugares_procesados"] += 1
            total_stats["eventos_nuevos"] += stats["nuevos"]
            total_stats["duplicados"] += stats["duplicados"]
            total_stats["errores"] += stats["errores"]
            total_stats["corregidos_hora"] += stats.get("corregidos_hora", 0)

            _log_scraping(
                fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
                registros_nuevos=stats["nuevos"],
                errores=stats["errores"],
                detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"], "corregidos_hora": stats.get("corregidos_hora", 0)},
            )

            # Rate limit: small delay between lugares to avoid hammering
            await asyncio.sleep(2)

        except Exception as e:
            total_stats["errores"] += 1
            print(f"  ❌ Error general: {e}")
            _log_scraping(
                fuente=lugar.get("sitio_web") or "error",
                registros_nuevos=0,
                errores=1,
                detalle={"lugar": lugar["nombre"], "error": str(e)[:300]},
            )

    elapsed = (_now_co() - start_time).total_seconds()
    total_stats["duracion_segundos"] = round(elapsed, 1)

    # Post-process all upcoming events to improve image/hour consistency across sources.
    if post_enrich:
        img_enrich = await enrich_event_images(limit=image_enrich_limit)
        hour_enrich = await enrich_event_hours(limit=hour_enrich_limit)
        total_stats["imagenes_enriquecidas"] = img_enrich.get("actualizados", 0)
        total_stats["horas_enriquecidas"] = hour_enrich.get("actualizados", 0)
    else:
        total_stats["imagenes_enriquecidas"] = 0
        total_stats["horas_enriquecidas"] = 0

    print("\n✅ ═══════════════════════════════════════════════")
    print(f"   AUTO-SCRAPER completado en {elapsed:.0f}s")
    print(f"   Lugares: {total_stats['lugares_procesados']}")
    print(f"   Eventos nuevos: {total_stats['eventos_nuevos']}")
    print(f"   Horas corregidas: {total_stats['corregidos_hora']}")
    print(f"   Imágenes enriquecidas: {total_stats.get('imagenes_enriquecidas', 0)}")
    print(f"   Horas enriquecidas: {total_stats.get('horas_enriquecidas', 0)}")
    print(f"   Duplicados: {total_stats['duplicados']}")
    print(f"   Errores: {total_stats['errores']}")
    print("═══════════════════════════════════════════════════\n")

    return total_stats


async def scrape_single_lugar(lugar_id: str) -> dict:
    """Scrape a single lugar by ID (UUID). Useful for on-demand scraping."""
    resp = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    ).eq("id", lugar_id).single().execute()

    if not resp.data:
        return {"error": "Lugar no encontrado"}

    lugar = resp.data
    print(f"\n🎯 Scraping individual: {lugar['nombre']}")
    stats = await _scrape_lugar(lugar)
    img_enrich = await enrich_event_images(limit=120)
    hour_enrich = await enrich_event_hours()
    stats["imagenes_enriquecidas"] = img_enrich.get("actualizados", 0)
    stats["horas_enriquecidas"] = hour_enrich.get("actualizados", 0)

    _log_scraping(
        fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "manual"),
        registros_nuevos=stats["nuevos"],
        errores=stats["errores"],
        detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"], "tipo": "manual"},
    )

    return {
        "lugar": lugar["nombre"],
        **stats,
    }


async def scrape_zona(municipio: str, limit: int = 60) -> dict:
    """
    Scrape all spaces in a municipio/zona.
    Used for zone-based AI search.
    """
    print(f"\n🗺️ Scraping zona: {municipio} (limit={limit})")

    resp = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    ).eq("municipio", municipio).limit(limit).execute()

    lugares = [
        l for l in (resp.data or [])
        if l.get("instagram_handle") or l.get("sitio_web")
    ]
    lugares = _sort_lugares_by_staleness(lugares)
    if not lugares:
        return {"error": "No hay lugares en esta zona", "municipio": municipio}

    total_stats = {"lugares": len(lugares), "eventos_nuevos": 0, "duplicados": 0, "errores": 0, "municipio": municipio}

    for i, lugar in enumerate(lugares):
        print(f"  [{i+1}/{len(lugares)}] {lugar['nombre']}")
        try:
            stats = await _scrape_lugar(lugar)
            total_stats["eventos_nuevos"] += stats["nuevos"]
            total_stats["duplicados"] += stats["duplicados"]
            total_stats["errores"] += stats["errores"]
            await asyncio.sleep(1)  # Rate limit
        except Exception as e:
            total_stats["errores"] += 1
            print(f"    ❌ {e}")

    _log_scraping(
        fuente=f"zona_{municipio}",
        registros_nuevos=total_stats["eventos_nuevos"],
        errores=total_stats["errores"],
        detalle=total_stats,
    )

    img_enrich = await enrich_event_images(limit=200)
    hour_enrich = await enrich_event_hours()
    total_stats["imagenes_enriquecidas"] = img_enrich.get("actualizados", 0)
    total_stats["horas_enriquecidas"] = hour_enrich.get("actualizados", 0)

    return total_stats


async def repair_suspicious_event_dates(
    limit_eventos: int = 160,
    max_lugares: int = 50,
    municipio: Optional[str] = None,
) -> dict:
    """Re-scrape places that have suspicious upcoming events.

    Objective:
    - Repair legacy events that may have wrong date/hour due to old parsing
      behavior (for example, events stored as today because caption contained
      CTA phrases with "hoy").

    Strategy:
    - Look at upcoming events from scraper-like sources.
    - Mark as suspicious when hour/date confidence is weak.
    - Re-scrape unique associated places to refresh event extraction.
    """
    print("\n🧰 Reparación de fechas sospechosas iniciada...")

    now_co = _now_co()
    today_start = now_co.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = today_start + timedelta(days=14)

    # Pull a broad upcoming window and filter in Python for maximum compatibility
    # with heterogeneous source labels in historical data.
    resp = (
        supabase.table("eventos")
        .select("id,espacio_id,titulo,fecha_inicio,hora_confirmada,fuente,municipio")
        .gte("fecha_inicio", today_start.isoformat())
        .lte("fecha_inicio", horizon.isoformat())
        .order("fecha_inicio")
        .limit(max(limit_eventos * 3, 80))
        .execute()
    )
    eventos = resp.data or []

    candidatos_lugares: list[str] = []
    seen_lugares: set[str] = set()
    sospechosos = 0

    for ev in eventos:
        espacio_id = ev.get("espacio_id")
        if not espacio_id:
            continue

        if municipio and str(ev.get("municipio") or "").strip().lower() != municipio.strip().lower():
            continue

        fuente = str(ev.get("fuente") or "").lower()
        if not ("auto_scraper" in fuente or "agenda" in fuente or "scraping" in fuente):
            continue

        fecha = _parse_iso_to_co(ev.get("fecha_inicio"))
        if not fecha:
            continue

        hora_confirmada = ev.get("hora_confirmada") is True
        is_midnight = fecha.hour == 0 and fecha.minute == 0
        is_legacy_1900 = fecha.hour == 19 and fecha.minute == 0 and not hora_confirmada
        is_today_unconfirmed = fecha.date() == today_start.date() and not hora_confirmada

        is_suspicious = is_midnight or is_legacy_1900 or is_today_unconfirmed
        if not is_suspicious:
            continue

        sospechosos += 1
        if espacio_id not in seen_lugares:
            seen_lugares.add(espacio_id)
            candidatos_lugares.append(espacio_id)
        if len(candidatos_lugares) >= max_lugares:
            break

    reparados = 0
    errores = 0
    nuevos = 0
    duplicados = 0
    corregidos_hora = 0
    detalles: list[dict] = []

    for i, lugar_id in enumerate(candidatos_lugares):
        try:
            stats = await scrape_single_lugar(lugar_id)
            reparados += 1
            nuevos += int(stats.get("nuevos") or 0)
            duplicados += int(stats.get("duplicados") or 0)
            corregidos_hora += int(stats.get("corregidos_hora") or 0)
            detalles.append(
                {
                    "lugar_id": lugar_id,
                    "lugar": stats.get("lugar"),
                    "nuevos": stats.get("nuevos", 0),
                    "duplicados": stats.get("duplicados", 0),
                    "corregidos_hora": stats.get("corregidos_hora", 0),
                    "errores": stats.get("errores", 0),
                }
            )
        except Exception as e:
            errores += 1
            detalles.append({"lugar_id": lugar_id, "error": str(e)[:250]})

        # Gentle pacing for providers
        if i < len(candidatos_lugares) - 1:
            await asyncio.sleep(1)

    result = {
        "eventos_revisados": len(eventos),
        "eventos_sospechosos": sospechosos,
        "lugares_candidatos": len(candidatos_lugares),
        "lugares_reprocesados": reparados,
        "nuevos": nuevos,
        "duplicados": duplicados,
        "corregidos_hora": corregidos_hora,
        "errores": errores,
        "municipio": municipio,
        "detalles": detalles,
    }

    _log_scraping(
        fuente=f"repair_suspicious_dates{f'_{municipio}' if municipio else ''}",
        registros_nuevos=nuevos,
        errores=errores,
        detalle={
            "eventos_revisados": len(eventos),
            "eventos_sospechosos": sospechosos,
            "lugares_reprocesados": reparados,
            "duplicados": duplicados,
            "corregidos_hora": corregidos_hora,
        },
    )

    print(
        "  ✅ Repair scraper completado | "
        f"sospechosos: {sospechosos} | lugares: {reparados} | "
        f"nuevos: {nuevos} | hora_corregida: {corregidos_hora} | errores: {errores}"
    )
    return result


async def enrich_event_images(limit: int = 300) -> dict:
    """
    Scan eventos without imagen_url and try to fetch og:image from their
    fuente_url or the espacio's sitio_web.
    """
    print("\n🖼️  Enriqueciendo imágenes de eventos...")
    result = supabase.table("eventos").select(
        "id,titulo,fuente_url,espacio_id,imagen_url"
    ).is_("imagen_url", "null").limit(limit).execute()

    eventos = result.data or []
    print(f"  📊 {len(eventos)} eventos sin imagen")
    updated = 0

    # Cache og:image per URL to avoid re-fetching
    og_cache: dict[str, str | None] = {}

    async def _get_og_image(url: str) -> str | None:
        if url in og_cache:
            return og_cache[url]
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=8, http2=False
            ) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    tag = soup.find("meta", property="og:image")
                    if tag and tag.get("content"):
                        og_cache[url] = tag["content"]
                        return tag["content"]
        except asyncio.CancelledError:
            og_cache[url] = None
            return None
        except Exception as e:
            print(f"    ⚠ Error fetching {url[:50]}: {e}")
        og_cache[url] = None
        return None

    for ev in eventos:
        fuente = ev.get("fuente_url")
        if not fuente and ev.get("espacio_id"):
            # Try espacio's website
            try:
                esp_resp = supabase.table("lugares").select("sitio_web").eq(
                    "id", ev["espacio_id"]
                ).single().execute()
                fuente = esp_resp.data.get("sitio_web") if esp_resp.data else None
            except Exception:
                fuente = None

        if not fuente:
            continue

        img = await _get_og_image(fuente)
        if img:
            try:
                supabase.table("eventos").update(
                    {"imagen_url": img}
                ).eq("id", ev["id"]).execute()
                updated += 1
                print(f"    🖼️  {ev['titulo'][:40]} → imagen actualizada")
            except Exception as e:
                print(f"    ⚠ Error updating {ev['titulo'][:30]}: {e}")

        await asyncio.sleep(0.5)

    print(f"  ✅ {updated} eventos actualizados con imagen")
    return {"total_sin_imagen": len(eventos), "actualizados": updated}


async def enrich_event_hours(limit: int = 800) -> dict:
    """Enrich upcoming events with explicit hour using OCR/text heuristics.

    - If hour is 00:00, tries OCR from image_url and regex from description/title.
    - If still missing, sets a default estimated hour (19:00) to avoid unresolved schedules.
    """
    print("\n🕒 Enriqueciendo horas de eventos...")
    today_iso = _now_co().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    try:
        resp = (
            supabase.table("eventos")
            .select("id,titulo,descripcion,fecha_inicio,imagen_url,fuente_url,hora_confirmada")
            .gte("fecha_inicio", today_iso)
            .order("fecha_inicio")
            .limit(limit)
            .execute()
        )
    except Exception as e:
        print(f"  ⚠ Error consultando eventos para horas: {e}")
        return {"revisados": 0, "actualizados": 0, "confirmadas": 0, "estimadas": 0, "errores": 1}

    eventos = resp.data or []
    revisados = 0
    actualizados = 0
    confirmadas = 0
    estimadas = 0
    errores = 0

    for ev in eventos:
        revisados += 1
        try:
            fecha_raw = ev.get("fecha_inicio")
            fecha = _parse_iso_to_co(fecha_raw)
            if not fecha:
                continue

            hora_actual_confirmada = bool(ev.get("hora_confirmada"))
            needs_fix = (fecha.hour == 0 and fecha.minute == 0) or (not hora_actual_confirmada)
            if not needs_fix:
                continue

            image_url = await _resolve_event_image(ev.get("imagen_url"), ev.get("fuente_url"))
            fecha_new, hora_confirmada = _finalize_event_datetime(
                fecha,
                image_url=image_url,
                texts=(ev.get("descripcion"), ev.get("titulo")),
            )

            payload = {}
            if fecha_new.isoformat() != fecha.isoformat():
                payload["fecha_inicio"] = fecha_new.isoformat()
            if image_url and image_url != ev.get("imagen_url"):
                payload["imagen_url"] = image_url
            if hora_confirmada != hora_actual_confirmada:
                payload["hora_confirmada"] = hora_confirmada

            desc_prev = ev.get("descripcion")
            desc_new = _enrich_event_description(desc_prev, fecha_new, hora_confirmada=hora_confirmada)
            if desc_new != (desc_prev or ""):
                payload["descripcion"] = desc_new

            if payload:
                supabase.table("eventos").update(_sanitize_payload(payload)).eq("id", ev["id"]).execute()
                actualizados += 1
                if hora_confirmada:
                    confirmadas += 1
                else:
                    estimadas += 1
        except Exception as e:
            errores += 1
            print(f"  ⚠ Error enriqueciendo hora ({ev.get('titulo', 'evento')}): {e}")

    print(
        f"  ✅ Horas revisadas: {revisados} | actualizadas: {actualizados} | "
        f"confirmadas: {confirmadas} | estimadas: {estimadas} | errores: {errores}"
    )
    return {
        "revisados": revisados,
        "actualizados": actualizados,
        "confirmadas": confirmadas,
        "estimadas": estimadas,
        "errores": errores,
    }


# ──────────────────────────────────────────────────────────────────────────
# Alternative / independent agenda scraping
# ──────────────────────────────────────────────────────────────────────────
AGENDA_SOURCES = [
    {
        "nombre": "Compas Urbano - Agenda",
        "url": "https://compasurbano.com",
        "categoria_default": "festival",
        "municipio": "medellin",
    },
    {
        "nombre": "Vivir en el Poblado - Agenda Cultural",
        "url": "https://vivirenelpoblado.com/agenda-cultural/",
        "categoria_default": "festival",
        "municipio": "medellin",
    },
    {
        "nombre": "Teatro Pablo Tobón Uribe",
        "url": "https://www.teatropablotobon.com/programacion",
        "categoria_default": "teatro",
        "municipio": "medellin",
    },
    {
        "nombre": "Comfenalco Antioquia - Agenda",
        "url": "https://www.comfenalcoantioquia.com.co/cultura-y-recreacion/eventos/",
        "categoria_default": "centro_cultural",
        "municipio": "medellin",
    },
    {
        "nombre": "Comfama - Agenda Cultural",
        "url": "https://comfama.com/entretenimiento-y-cultura/experiencias-en-familia/",
        "categoria_default": "centro_cultural",
        "municipio": "medellin",
    },
    {
        "nombre": "Biblioteca Pública Piloto",
        "url": "https://bibliotecapiloto.gov.co/actividades-culturales/",
        "categoria_default": "libreria",
        "municipio": "medellin",
    },
    {
        "nombre": "El Perpetuo Socorro - Eventos",
        "url": "https://www.elperpetuosocorro.org/eventos/",
        "categoria_default": "teatro",
        "municipio": "medellin",
    },
    {
        "nombre": "MAMM - Programación",
        "url": "https://elmamm.org/programacion",
        "categoria_default": "galeria",
        "municipio": "medellin",
    },
    {
        "nombre": "Matacandelas - Obras",
        "url": "https://www.matacandelas.com/obras-y-espectaculos/",
        "categoria_default": "teatro",
        "municipio": "medellin",
    },
    {
        "nombre": "Teatro Metropolitano - Programacion",
        "url": "https://www.teatrometropolitano.com/eventos/",
        "categoria_default": "teatro",
        "municipio": "medellin",
    },
    {
        "nombre": "Casa Teatro El Poblado - Agenda",
        "url": "https://casateatroelpoblado.com/agenda/",
        "categoria_default": "teatro",
        "municipio": "medellin",
    },
    {
        "nombre": "Parque Explora - Agenda",
        "url": "https://www.parqueexplora.org/agenda/",
        "categoria_default": "centro_cultural",
        "municipio": "medellin",
    },
    {
        "nombre": "Museo de Antioquia - Programación",
        "url": "https://museodeantioquia.co/agenda/",
        "categoria_default": "galeria",
        "municipio": "medellin",
    },
]

AGENDA_EXTRACTION_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Analiza el contenido de esta página de agenda cultural y extrae TODOS los EVENTOS culturales mencionados.

Fecha actual: {fecha_actual}
Año actual: {anio_actual}

Fuente: {nombre_fuente}
URL: {fuente_url}
Municipio por defecto: {municipio}

Contenido:
---
{contenido}
---

Extrae en JSON con esta estructura exacta:
{{
  "eventos": [
    {{
      "titulo": "nombre del evento",
      "categoria_principal": "teatro | hip_hop | jazz | musica_en_vivo | electronica | galeria | arte_contemporaneo | libreria | editorial | poesia | filosofia | cine | danza | circo | fotografia | casa_cultura | centro_cultural | festival | batalla_freestyle | muralismo | radio_comunitaria | publicacion | otro",
      "categorias": ["lista"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
      "fecha_fin": "YYYY-MM-DDTHH:MM:SS o null",
      "descripcion": "descripción del evento (máx 500 chars)",
      "nombre_lugar": "nombre del lugar si se menciona",
      "barrio": "barrio si se menciona",
      "municipio": "municipio o medellin por defecto",
      "precio": "valor o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": "URL de imagen del evento si la hay, o null"
    }}
  ]
}}

Reglas:
- Cuando una fecha NO especifica año, usa {anio_actual}.
- Incluye SOLO eventos que ocurran DESPUÉS de {fecha_actual}.
- Prioriza agenda alternativa, underground, independiente.
- Si no hay eventos claros, responde: {{"eventos": []}}
- NO inventes horas. Si el contenido NO trae hora explícita, usa 00:00:00. NUNCA pongas 19:00 por defecto — es mejor un evento sin hora que una hora falsa.
- Si el contenido incluye [OG_IMAGE: url], usa esa URL como imagen_url del evento principal.
- Responde SOLO con el JSON, sin texto adicional.
"""


async def scrape_agenda_sources() -> dict:
    """
    Scrape independent agenda websites (not linked to a specific lugar).
    These are cultural agenda aggregators, media outlets, etc.
    """
    print("\n📰 ═══════════════════════════════════════════════")
    print("   AGENDA ALTERNATIVA — scraping fuentes externas...")
    print("═══════════════════════════════════════════════════")

    now_co = _now_co()
    now_iso = now_co.isoformat()
    anio = now_co.year

    total = {"fuentes": 0, "eventos_nuevos": 0, "duplicados": 0, "errores": 0}

    for src in AGENDA_SOURCES:
        print(f"\n📰 [{src['nombre']}] {src['url']}")
        try:
            # Try code-first extraction first (zero tokens)
            html_raw = await _fetch_website_raw(src["url"])
            events: list[dict] = []

            if html_raw and len(html_raw) > 200:
                source_og_image = _extract_og_image(html_raw)
                if needs_playwright(src["url"]):
                    html_pw = await fetch_with_playwright(src["url"])
                    if html_pw and len(html_pw) > len(html_raw):
                        html_raw = html_pw
                        source_og_image = _extract_og_image(html_raw) or source_og_image
                events = extract_events_code(
                    html_raw, src["url"],
                    src["nombre"], src["categoria_default"], src["municipio"]
                )
                # Cobertura extra sin AI: si encontramos muy pocos, reintentar con
                # Playwright aunque el dominio no este marcado como dinamico.
                if len(events) < 3:
                    html_pw2 = await fetch_with_playwright(src["url"])
                    if html_pw2 and len(html_pw2) > 300:
                        events_pw = extract_events_code(
                            html_pw2,
                            src["url"],
                            src["nombre"],
                            src["categoria_default"],
                            src["municipio"],
                        )
                        if len(events_pw) > len(events):
                            events = events_pw
                if events:
                    for ev in events:
                        if not ev.get("imagen_url") and source_og_image:
                            ev["imagen_url"] = source_og_image
                    print(f"  ✅ Código: {len(events)} evento(s)")
                else:
                    text = _html_to_text(html_raw)[:4000]
                    prompt = EVENT_EXTRACTION_PROMPT.format(
                        fecha_actual=now_iso,
                        anio_actual=anio,
                        nombre_lugar=src["nombre"],
                        lugar_id=src["nombre"],
                        categoria=src["categoria_default"],
                        municipio=src["municipio"],
                        fuente_tipo="agenda",
                        fuente_url=src["url"],
                        contenido=text,
                    )
                    events = _extract_events_with_ai(prompt)
                    if events:
                        print(f"  🧠 IA: {len(events)} evento(s)")
                if not events:
                    feed_url = await get_or_discover_feed(src["url"])
                    if feed_url:
                        rss_events = await parse_rss_events(
                            feed_url,
                            {
                                "id": None,
                                "nombre": src["nombre"],
                                "municipio": src["municipio"],
                                "categoria_principal": src["categoria_default"],
                            },
                        )
                        if rss_events:
                            events = rss_events
                            print(f"  📰 RSS: {len(events)} evento(s) desde {feed_url}")
            else:
                print(f"  ⚠ Sin eventos de código para {src['nombre']} (sin fallback AI)")
            if not events:
                continue

            for ev in events:
                try:
                    titulo = _sanitize_text(ev.get("titulo"))
                    if not titulo:
                        continue
                    if not is_likely_cultural_event(
                        titulo,
                        ev.get("descripcion"),
                        fuente_url=ev.get("_fuente_url") or src["url"],
                        categoria=ev.get("categoria_principal") or src["categoria_default"],
                    ):
                        print(f"    ⛔ Candidato descartado (no evento): {titulo[:70]}")
                        continue

                    fecha_str = ev.get("fecha_inicio")
                    if fecha_str:
                        try:
                            fecha = datetime.fromisoformat(fecha_str)
                            if fecha.tzinfo is None:
                                fecha = fecha.replace(tzinfo=CO_TZ)
                            else:
                                fecha = fecha.astimezone(CO_TZ)
                            fecha = _normalize_scraped_datetime(fecha, "agenda")
                            image_url = await _resolve_event_image(ev.get("imagen_url"), ev.get("_fuente_url") or src["url"])
                            fecha, hora_confirmada = _finalize_event_datetime(
                                fecha,
                                image_url=image_url,
                                texts=(ev.get("descripcion"), titulo),
                            )
                            hoy_inicio_ag = now_co.replace(hour=0, minute=0, second=0, microsecond=0)
                            fecha_fin_ag = None
                            if ev.get("fecha_fin"):
                                try:
                                    fecha_fin_ag = datetime.fromisoformat(ev["fecha_fin"])
                                    if fecha_fin_ag.tzinfo is None:
                                        fecha_fin_ag = fecha_fin_ag.replace(tzinfo=CO_TZ)
                                    else:
                                        fecha_fin_ag = fecha_fin_ag.astimezone(CO_TZ)
                                except (ValueError, TypeError):
                                    pass
                            if fecha < hoy_inicio_ag:
                                if fecha_fin_ag is None or fecha_fin_ag < hoy_inicio_ag:
                                    continue
                        except (ValueError, TypeError):
                            # No inventar fecha: descartar evento.
                            continue
                    else:
                        continue

                    slug = _slugify(titulo)
                    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
                    if existing.data:
                        total["duplicados"] += 1
                        continue

                    evento_data = {
                        "titulo": titulo,
                        "slug": slug,
                        "fecha_inicio": fecha.isoformat(),
                        "fecha_fin": fecha_fin_ag.isoformat() if fecha_fin_ag else None,
                        "hora_confirmada": hora_confirmada,
                        "categorias": ev.get("categorias", [src["categoria_default"]]),
                        "categoria_principal": ev.get("categoria_principal", src["categoria_default"]),
                        "municipio": ev.get("municipio", src["municipio"]),
                        "barrio": ev.get("barrio"),
                        "nombre_lugar": ev.get("nombre_lugar"),
                        "descripcion": _enrich_event_description(
                            ev.get("descripcion"),
                            fecha,
                            hora_confirmada=hora_confirmada,
                        ),
                        "precio": ev.get("precio"),
                        "es_gratuito": ev.get("es_gratuito", False),
                        "es_recurrente": ev.get("es_recurrente", False),
                        "imagen_url": image_url,
                        "fuente": f"agenda_{src['nombre'][:30]}",
                        "fuente_url": src["url"],
                        "verificado": False,
                    }
                    evento_data = _sanitize_payload(evento_data)
                    supabase.table("eventos").insert(evento_data).execute()
                    total["eventos_nuevos"] += 1
                    print(f"    ✅ {titulo[:60]}")

                except Exception as e:
                    total["errores"] += 1
                    print(f"    ❌ Error: {e}")

            await asyncio.sleep(3)

        except Exception as e:
            total["errores"] += 1
            print(f"  ❌ Error scraping {src['nombre']}: {e}")

    _log_scraping(
        fuente="agenda_alternativa",
        registros_nuevos=total["eventos_nuevos"],
        errores=total["errores"],
        detalle=total,
    )

    print(f"\n✅ Agenda alternativa: {total['eventos_nuevos']} nuevos, {total['duplicados']} dup, {total['errores']} err")
    return total


async def scrape_compas_urbano() -> dict:
    """Compat wrapper requerido por API/router y scheduler heredados.

    Ejecuta scraping diario de agenda alternativa (incluye Compas Urbano).
    """
    return await scrape_agenda_sources()


# ──────────────────────────────────────────────────────────────────────────
# Cleanup: remove fully-past events
# ──────────────────────────────────────────────────────────────────────────
async def cleanup_past_events() -> dict:
    """
    Delete events that have fully ended long ago.
    Rules:
    - Multi-day events (fecha_fin set): delete only if fecha_fin < retention cutoff
    - Single-day events (no fecha_fin): delete only if fecha_inicio < retention cutoff
    Multi-day events still running (fecha_fin >= today) are KEPT.
    """
    print("\n🗑️  Limpiando eventos pasados...")
    now_co = _now_co()
    hoy_inicio = now_co.replace(hour=0, minute=0, second=0, microsecond=0)
    retention_inicio = hoy_inicio - timedelta(days=30)
    hoy_iso = hoy_inicio.isoformat()
    retention_iso = retention_inicio.isoformat()

    removed = 0

    # 1. Single-day events older than retention window
    try:
        resp = (
            supabase.table("eventos")
            .select("id,titulo,fecha_inicio")
            .lt("fecha_inicio", retention_iso)
            .is_("fecha_fin", "null")
            .execute()
        )
        ids_to_delete = [e["id"] for e in (resp.data or [])]
        if ids_to_delete:
            for ev_id in ids_to_delete:
                try:
                    supabase.table("eventos").delete().eq("id", ev_id).execute()
                    removed += 1
                except Exception as e:
                    print(f"    ⚠ Error deleting {ev_id}: {e}")
                await asyncio.sleep(0)  # yield control between deletes
        print(f"  🗑️  Eventos de día único antiguos eliminados: {len(ids_to_delete)}")
    except Exception as e:
        print(f"  ⚠ Error en cleanup single-day: {e}")

    # 2. Multi-day events where fecha_fin < retention window
    try:
        resp2 = (
            supabase.table("eventos")
            .select("id,titulo,fecha_fin")
            .not_.is_("fecha_fin", "null")
            .lt("fecha_fin", retention_iso)
            .execute()
        )
        ids_to_delete2 = [e["id"] for e in (resp2.data or [])]
        if ids_to_delete2:
            for ev_id in ids_to_delete2:
                try:
                    supabase.table("eventos").delete().eq("id", ev_id).execute()
                    removed += 1
                except Exception as e:
                    print(f"    ⚠ Error deleting multiday {ev_id}: {e}")
                await asyncio.sleep(0)
        print(f"  🗑️  Eventos multi-día antiguos eliminados: {len(ids_to_delete2)}")
    except Exception as e:
        print(f"  ⚠ Error en cleanup multi-day: {e}")

    print(f"  ✅ Cleanup total: {removed} eventos eliminados")
    _log_scraping(
        fuente="cleanup_past_events",
        registros_nuevos=0,
        errores=0,
        detalle={"eliminados": removed},
    )
    return {"eliminados": removed}
