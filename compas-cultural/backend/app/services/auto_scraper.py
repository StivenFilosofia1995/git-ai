"""
Auto-scraper: sistema automático de scraping para todos los lugares registrados.
Recorre periódicamente los sitios web e Instagram de cada lugar,
extrae eventos futuros con Groq (llama-3.3-70b) y los inserta en la BD.
"""
import json
import re
import traceback
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.groq_client import groq_chat, parse_json_response, MODEL_SMART
from app.services.html_event_extractor import extract_events_code, parse_date
from app.services.playwright_fetcher import fetch_with_playwright, needs_playwright

CO_TZ = ZoneInfo("America/Bogota")

# Keyword list exported for RSS/other scrapers that import from this module.
EVENT_KEYWORDS = [
    "evento", "concierto", "taller", "exposicion", "exposición", "festival",
    "obra", "funcion", "función", "charla", "foro", "cine", "danza",
    "musica", "música", "lanzamiento", "performance", "show", "en vivo",
]


def _extract_time(text: str) -> tuple[int, int]:
    """Extract event time from free text. Defaults to 19:00 when unclear."""
    if not text:
        return 19, 0
    m = re.search(r"(\d{1,2})[:.](\d{2})(?:\s*([ap])\.?m?\.?)?", text, re.I)
    if not m:
        return 19, 0

    hour = int(m.group(1))
    minute = int(m.group(2))
    mer = (m.group(3) or "").lower().replace(".", "")
    if mer in ("pm", "p") and hour < 12:
        hour += 12
    elif mer in ("am", "a") and hour == 12:
        hour = 0
    if hour > 23:
        return 19, 0
    return hour, minute


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

# ── Prompt para extraer eventos de una página ────────────────────────────
EVENT_EXTRACTION_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Analiza el contenido de esta página/perfil y extrae TODOS los EVENTOS culturales mencionados.

Fecha actual: {fecha_actual}
Año actual: {anio_actual}

Lugar asociado: {nombre_lugar} (ID: {lugar_id})
Categoría principal del lugar: {categoria}
Municipio: {municipio}
Fuente: {fuente_tipo} — {fuente_url}

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
      "precio": "valor o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": "URL de imagen del evento si la hay, o null"
    }}
  ]
}}

Reglas:
- Cuando una fecha NO especifica año, usa {anio_actual}.
- Incluye eventos que ocurran DESPUÉS de {fecha_actual}.
- Extrae todos los eventos culturales que encuentres (conciertos, teatro, cine, talleres, charlas, exposiciones, festivales, danza, etc.).
- Si no hay eventos claros, responde: {{"eventos": []}}
- Para fechas ambiguas, infiere la más probable usando {anio_actual}.
- NO inventes la hora: si el contenido no trae hora explícita, usa 00:00:00.
- Si el contenido incluye [OG_IMAGE: url], usa esa URL como imagen_url del evento principal.
- Si el contenido incluye [IMAGE_URL: url] o [PERMALINK: url], usa la IMAGE_URL como imagen_url del evento asociado.
- Responde SOLO con el JSON, sin texto adicional.
"""

# ── Prompt para scraping de Instagram (perfil público) ───────────────────
IG_PROFILE_PROMPT = """Eres un experto en cultura urbana de Medellín analizando un perfil de Instagram.
El perfil es de: {nombre_lugar} ({instagram_handle})
Categoría: {categoria} | Municipio: {municipio}
Fecha actual: {fecha_actual} | Año actual: {anio_actual}

Analiza las publicaciones recientes y extrae EVENTOS culturales FUTUROS (después de {fecha_actual}).
Cuando una fecha NO especifica año, usa {anio_actual}.
Busca: fechas, horarios, nombres de eventos, precios, ubicaciones mencionados en los posts.

Contenido del perfil/posts:
---
{contenido}
---

Responde en JSON exacto:
{{
  "eventos": [
    {{
      "titulo": "nombre del evento",
      "categoria_principal": "categoría",
      "categorias": ["lista"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
      "fecha_fin": "YYYY-MM-DDTHH:MM:SS o null",
      "descripcion": "descripción corta",
      "precio": "valor o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": "URL de imagen si la hay"
    }}
  ]
}}

- Eventos FUTUROS únicamente.
- NO inventes la hora: si el contenido no trae hora explícita, usa 00:00:00.
- Si no encuentras eventos claros, responde: {{"eventos": []}}
- Responde SOLO JSON.
"""


def _extract_events_with_groq(prompt: str) -> list[dict]:
    """Extract events from real scraped content using Groq JSON output."""
    if not settings.groq_api_key:
        return []
    try:
        clean_prompt = _sanitize_text(prompt) or ""
        if not clean_prompt:
            return []

        raw = groq_chat(clean_prompt, model=MODEL_SMART, max_tokens=4096, temperature=0, json_mode=True)
        if not raw:
            raw = groq_chat(clean_prompt, model=MODEL_SMART, max_tokens=4096, temperature=0)
        if not raw:
            return []

        data = parse_json_response(raw)
        if data is None:
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            data = parse_json_response(fixed)
        if data is None:
            return []

        events = data.get("eventos", []) if isinstance(data, dict) else []
        return events if isinstance(events, list) else []
    except Exception as e:
        print(f"  ⚠ Groq extraction error: {e}")
        return []


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
            verify=False,  # handle SSL mismatches gracefully
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
    sitio = lugar.get("sitio_web")
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
                    print(f"    ⚠ Sin eventos de código para {sitio} — intentando Groq fallback")
                    text = _html_to_text(html)
                    short_text = text[:4000]
                    if short_text and len(short_text) > 100:
                        prompt = EVENT_EXTRACTION_PROMPT.format(
                            fecha_actual=now_iso,
                            anio_actual=anio,
                            nombre_lugar=nombre,
                            lugar_id=lugar_id,
                            categoria=categoria,
                            municipio=municipio,
                            fuente_tipo="sitio_web",
                            fuente_url=sitio,
                            contenido=short_text,
                        )
                        events_groq = _extract_events_with_groq(prompt)
                        for ev in events_groq:
                            ev["_fuente"] = "sitio_web"
                            ev["_fuente_url"] = sitio
                        if events_groq:
                            print(f"    🧠 Groq: {len(events_groq)} evento(s)")
                            all_events.extend(events_groq)

    # ── 2. Scrape Instagram (código puro — CERO tokens AI) ────────────────
    ig_handle = lugar.get("instagram_handle")
    if ig_handle:
        print(f"  📸 Scraping IG: {ig_handle}")
        from app.services.instagram_pw_scraper import fetch_ig_profile
        from app.services.ig_event_extractor import extract_events_from_ig_profile

        clean_handle = ig_handle.lstrip("@").strip()

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
                ev["_fuente"] = "instagram"
                # Use per-post permalink when available, fall back to profile URL
                ev["_fuente_url"] = ev.pop("_permalink", None) or ig_url
            all_events.extend(events_ig)
            print(f"    📊 Código extrajo {len(events_ig)} evento(s) de IG")

            # If regex/date extractor found nothing, use LLM on real captions as fallback.
            if not events_ig and settings.groq_api_key:
                from app.services.instagram_pw_scraper import profile_to_scraper_text
                ig_text = profile_to_scraper_text(profile, clean_handle)[:5000]
                if ig_text and len(ig_text) > 100:
                    prompt = IG_PROFILE_PROMPT.format(
                        fecha_actual=now_iso,
                        anio_actual=anio,
                        nombre_lugar=nombre,
                        instagram_handle=clean_handle,
                        categoria=categoria,
                        municipio=municipio,
                        contenido=ig_text,
                    )
                    ig_groq = _extract_events_with_groq(prompt)
                    for ev in ig_groq:
                        ev["_fuente"] = "instagram"
                        ev["_fuente_url"] = ig_url
                    if ig_groq:
                        print(f"    🧠 Groq IG: {len(ig_groq)} evento(s)")
                        all_events.extend(ig_groq)
        else:
            print(f"    ⚠ Sin contenido de IG para {ig_handle}")

    # 4. Insert events into DB
    stats = {"nuevos": 0, "duplicados": 0, "errores": 0}
    # For multi-day events: keep if fecha_fin >= today (still running).
    # Only skip single-day events whose fecha_inicio < today.
    hoy_inicio = now_co.replace(hour=0, minute=0, second=0, microsecond=0)

    for ev in all_events:
        try:
            titulo = ev.get("titulo")
            if not titulo:
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
                    fecha = now_co + timedelta(days=7)
            else:
                continue  # Skip events without date

            slug = _slugify(titulo)
            # Dedup by (slug + date) so recurring events with different dates are allowed
            fecha_date_str = fecha.strftime("%Y-%m-%d")
            slug_with_date = f"{slug}-{fecha_date_str}"

            existing = supabase.table("eventos").select("id").eq("slug", slug_with_date).execute()
            if existing.data:
                stats["duplicados"] += 1
                continue
            # Also check plain slug (legacy entries without date suffix)
            existing_plain = supabase.table("eventos").select("id").eq("slug", slug).execute()
            if existing_plain.data:
                # Check if the existing event has the same date — if so it's a true duplicate
                existing_event = supabase.table("eventos").select("fecha_inicio").eq("slug", slug).single().execute()
                if existing_event.data:
                    ex_date = existing_event.data.get("fecha_inicio", "")[:10]
                    if ex_date == fecha_date_str:
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
                "categorias": ev.get("categorias", [categoria]),
                "categoria_principal": ev.get("categoria_principal", categoria),
                "municipio": municipio,
                "barrio": lugar.get("barrio"),
                "nombre_lugar": nombre,
                "descripcion": ev.get("descripcion"),
                "precio": ev.get("precio"),
                "es_gratuito": ev.get("es_gratuito", False),
                "es_recurrente": ev.get("es_recurrente", False),
                "imagen_url": ev.get("imagen_url"),
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
async def run_auto_scraper(limit: Optional[int] = None) -> dict:
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

    if limit:
        lugares = lugares[:limit]

    total_stats = {"lugares_procesados": 0, "eventos_nuevos": 0, "duplicados": 0, "errores": 0}
    start_time = _now_co()

    for i, lugar in enumerate(lugares):
        print(f"\n📍 [{i+1}/{len(lugares)}] {lugar['nombre']}")
        try:
            stats = await _scrape_lugar(lugar)
            total_stats["lugares_procesados"] += 1
            total_stats["eventos_nuevos"] += stats["nuevos"]
            total_stats["duplicados"] += stats["duplicados"]
            total_stats["errores"] += stats["errores"]

            _log_scraping(
                fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
                registros_nuevos=stats["nuevos"],
                errores=stats["errores"],
                detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"]},
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

    print("\n✅ ═══════════════════════════════════════════════")
    print(f"   AUTO-SCRAPER completado en {elapsed:.0f}s")
    print(f"   Lugares: {total_stats['lugares_procesados']}")
    print(f"   Eventos nuevos: {total_stats['eventos_nuevos']}")
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


async def scrape_zona(municipio: str, limit: int = 20) -> dict:
    """
    Scrape all spaces in a municipio/zona.
    Used for zone-based AI search.
    """
    print(f"\n🗺️ Scraping zona: {municipio} (limit={limit})")

    resp = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    ).eq("municipio", municipio).limit(limit).execute()

    lugares = resp.data or []
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

    return total_stats


async def enrich_event_images() -> dict:
    """
    Scan eventos without imagen_url and try to fetch og:image from their
    fuente_url or the espacio's sitio_web.
    """
    print("\n🖼️  Enriqueciendo imágenes de eventos...")
    result = supabase.table("eventos").select(
        "id,titulo,fuente_url,espacio_id,imagen_url"
    ).is_("imagen_url", "null").execute()

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
                follow_redirects=True, timeout=12, http2=False
            ) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    tag = soup.find("meta", property="og:image")
                    if tag and tag.get("content"):
                        og_cache[url] = tag["content"]
                        return tag["content"]
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


# ──────────────────────────────────────────────────────────────────────────
# Alternative / independent agenda scraping
# ──────────────────────────────────────────────────────────────────────────
AGENDA_SOURCES = [
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
- Para horas ambiguas, usa 19:00:00 como default.
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
                if needs_playwright(src["url"]):
                    html_pw = await fetch_with_playwright(src["url"])
                    if html_pw and len(html_pw) > len(html_raw):
                        html_raw = html_pw
                events = extract_events_code(
                    html_raw, src["url"],
                    src["nombre"], src["categoria_default"], src["municipio"]
                )
                if events:
                    print(f"  ✅ Código: {len(events)} evento(s)")
                elif settings.groq_api_key:
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
                    events = _extract_events_with_groq(prompt)
                    if events:
                        print(f"  🧠 Groq: {len(events)} evento(s)")
            else:
                print(f"  ⚠ Sin eventos de código para {src['nombre']} (sin fallback AI)")  
            if not events:
                continue

            for ev in events:
                try:
                    titulo = ev.get("titulo")
                    if not titulo:
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
                            fecha = now_co + timedelta(days=7)
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
                        "categorias": ev.get("categorias", [src["categoria_default"]]),
                        "categoria_principal": ev.get("categoria_principal", src["categoria_default"]),
                        "municipio": ev.get("municipio", src["municipio"]),
                        "barrio": ev.get("barrio"),
                        "nombre_lugar": ev.get("nombre_lugar"),
                        "descripcion": ev.get("descripcion"),
                        "precio": ev.get("precio"),
                        "es_gratuito": ev.get("es_gratuito", False),
                        "es_recurrente": ev.get("es_recurrente", False),
                        "imagen_url": ev.get("imagen_url"),
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


# ──────────────────────────────────────────────────────────────────────────
# Cleanup: remove fully-past events
# ──────────────────────────────────────────────────────────────────────────
async def cleanup_past_events() -> dict:
    """
    Delete events that have fully ended.
    Rules:
    - Multi-day events (fecha_fin set): delete only if fecha_fin < yesterday
    - Single-day events (no fecha_fin): delete if fecha_inicio < today start
    Multi-day events still running (fecha_fin >= today) are KEPT.
    """
    print("\n🗑️  Limpiando eventos pasados...")
    now_co = _now_co()
    hoy_inicio = now_co.replace(hour=0, minute=0, second=0, microsecond=0)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    hoy_iso = hoy_inicio.isoformat()
    ayer_iso = ayer_inicio.isoformat()

    removed = 0

    # 1. Single-day events (no fecha_fin) that started before today
    try:
        resp = (
            supabase.table("eventos")
            .select("id,titulo,fecha_inicio")
            .lt("fecha_inicio", hoy_iso)
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
        print(f"  🗑️  Eventos de día único pasados eliminados: {len(ids_to_delete)}")
    except Exception as e:
        print(f"  ⚠ Error en cleanup single-day: {e}")

    # 2. Multi-day events where fecha_fin < yesterday
    try:
        resp2 = (
            supabase.table("eventos")
            .select("id,titulo,fecha_fin")
            .not_.is_("fecha_fin", "null")
            .lt("fecha_fin", ayer_iso)
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
        print(f"  🗑️  Eventos multi-día pasados eliminados: {len(ids_to_delete2)}")
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

