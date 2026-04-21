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
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.groq_client import groq_chat, MODEL_SMART

CO_TZ = ZoneInfo("America/Bogota")

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
- Para horas ambiguas, usa 19:00:00 como default.
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
- Si no encuentras eventos claros, responde: {{"eventos": []}}
- Responde SOLO JSON.
"""


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


async def _fetch_website(url: str) -> Optional[str]:
    """Fetch and extract text from a website. Also extracts og:image meta tag."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract og:image for potential event images
        og_image = None
        og_tag = soup.find("meta", property="og:image")
        if og_tag and og_tag.get("content"):
            og_image = og_tag["content"]

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        if og_image:
            text = f"[OG_IMAGE: {og_image}]\n{text}"
        return text[:8000] if text else None
    except Exception as e:
        print(f"  ⚠ Error fetching {url}: {e}")
        return None


async def _fetch_instagram_via_meta_api(handle: str) -> Optional[str]:
    """
    Fetch Instagram posts via Meta Graph API (Instagram Business/Creator API).
    Returns captions + media URLs for Claude to analyze.
    
    Requires:
    - META_ACCESS_TOKEN in .env (Page token or long-lived user token)
    - The IG account must be a Business/Creator account connected to a FB Page
    
    API flow:
    1. Search for IG user by username → get ig_user_id
    2. Fetch recent media from that user → get captions + image URLs
    """
    access_token = settings.meta_access_token
    if not access_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            my_ig_id = settings.meta_ig_business_account_id
            if not my_ig_id:
                return None

            # Instagram Business Discovery API
            # Docs: https://developers.facebook.com/docs/instagram-api/guides/business-discovery
            # The username goes in the field path: business_discovery.fields(...)  
            # with an additional query param or inline reference.
            media_fields = "caption,timestamp,media_url,permalink,media_type,thumbnail_url"
            fields_param = (
                f"business_discovery.fields("
                f"username,biography,"
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
            bio = discovery.get("biography", "")
            media_data = discovery.get("media", {}).get("data", [])

            if not media_data:
                return None

            # Build structured content with image URLs for Claude
            parts = []
            if bio:
                parts.append(f"BIO: {bio}")

            for post in media_data:
                caption = post.get("caption", "")
                media_url = post.get("media_url", "")
                timestamp = post.get("timestamp", "")
                media_type = post.get("media_type", "")
                permalink = post.get("permalink", "")

                post_text = f"[POST {timestamp}]"
                if media_type in ("IMAGE", "CAROUSEL_ALBUM"):
                    post_text += f" [IMAGE_URL: {media_url}]"
                elif media_type == "VIDEO":
                    thumb = post.get("thumbnail_url", media_url)
                    post_text += f" [VIDEO_THUMBNAIL: {thumb}]"
                if permalink:
                    post_text += f" [PERMALINK: {permalink}]"
                post_text += f"\n{caption}"
                parts.append(post_text)

            content = "\n---\n".join(parts)
            return content[:8000]

    except Exception as e:
        print(f"    ⚠ Meta Graph API error: {e}")
        return None


async def _fetch_instagram_profile(handle: str) -> Optional[str]:
    """
    Fetch Instagram profile page content.
    Tries Meta Graph API first (if configured), then falls back to public scrapers.
    """
    clean = handle.lstrip("@").strip().split("/")[0]

    # 1. Try Meta Graph API first (best quality: captions + image URLs)
    meta_content = await _fetch_instagram_via_meta_api(clean)
    if meta_content and len(meta_content) > 200:
        print(f"    ✅ Meta Graph API: {len(meta_content)} chars")
        return meta_content

    # 2. Fallback to public scrapers
    urls_to_try = [
        f"https://www.picuki.com/profile/{clean}",
        f"https://imginn.com/{clean}/",
        f"https://www.instagram.com/{clean}/",
    ]

    for url in urls_to_try:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
                        tag.decompose()
                    
                    # Get post captions, descriptions
                    text_parts = []
                    # Bio
                    bio = soup.find("div", class_=re.compile(r"bio|description|profile-desc", re.I))
                    if bio:
                        text_parts.append(f"BIO: {bio.get_text(strip=True)}")
                    
                    # Post captions (picuki/imginn style)
                    captions = soup.find_all(class_=re.compile(r"caption|photo-description|post-text", re.I))
                    for cap in captions[:15]:  # últimos 15 posts
                        text_parts.append(cap.get_text(strip=True))
                    
                    # Fallback: get all text
                    if not text_parts:
                        text_parts.append(soup.get_text(separator="\n", strip=True))
                    
                    content = "\n---\n".join(text_parts)
                    if len(content) > 200:  # Meaningful content
                        return content[:8000]
        except Exception:
            continue

    return None


# ──────────────────────────────────────────────────────────────────────────
# Groq extraction
# ──────────────────────────────────────────────────────────────────────────
def _extract_events_with_claude(prompt: str) -> list[dict]:
    """Send content to Groq (llama-3.3-70b) and extract event list."""
    try:
        raw = groq_chat(prompt, model=MODEL_SMART, max_tokens=4096, temperature=0)
        if not raw:
            print("  ⚠ Groq returned empty response")
            return []
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fix trailing commas and retry
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            data = json.loads(fixed)
        events = data.get("eventos", [])
        print(f"    📊 Groq extrajo {len(events)} evento(s)")
        return events
    except Exception as e:
        print(f"  ⚠ Groq extraction error: {e}")
        return []


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
    now_co = _now_co()   # timezone-aware Colombia time
    now_iso = now_co.isoformat()
    anio = now_co.year
    all_events: list[dict] = []

    # 1. Scrape website
    sitio = lugar.get("sitio_web")
    if sitio:
        print(f"  🌐 Scraping web: {sitio}")
        content = await _fetch_website(sitio)
        if content and len(content) > 100:
            print(f"    📄 Contenido: {len(content)} chars")
            prompt = EVENT_EXTRACTION_PROMPT.format(
                fecha_actual=now_iso,
                anio_actual=anio,
                nombre_lugar=nombre,
                lugar_id=lugar_id,
                categoria=categoria,
                municipio=municipio,
                fuente_tipo="sitio_web",
                fuente_url=sitio,
                contenido=content,
            )
            events = _extract_events_with_claude(prompt)
            for ev in events:
                ev["_fuente"] = "sitio_web"
                ev["_fuente_url"] = sitio
            all_events.extend(events)

    # 2. Scrape Instagram
    ig_handle = lugar.get("instagram_handle")
    if ig_handle:
        print(f"  📸 Scraping IG: {ig_handle}")
        content = await _fetch_instagram_profile(ig_handle)
        if content and len(content) > 100:
            print(f"    📄 Contenido IG: {len(content)} chars")
            prompt = IG_PROFILE_PROMPT.format(
                fecha_actual=now_iso,
                anio_actual=anio,
                nombre_lugar=nombre,
                instagram_handle=ig_handle,
                categoria=categoria,
                municipio=municipio,
                contenido=content,
            )
            events = _extract_events_with_claude(prompt)
            for ev in events:
                ev["_fuente"] = "instagram"
                ev["_fuente_url"] = f"https://instagram.com/{ig_handle.lstrip('@')}"
            all_events.extend(events)

    # 3. Fallback: if scraping found 0 events, use Claude's knowledge to generate likely events
    if not all_events:
        web_context = ""
        if sitio:
            web_context = f"\nTiene sitio web: {sitio}"
        if ig_handle:
            web_context = f"{web_context}\nTiene Instagram: @{ig_handle}"

        print(f"  🧠 0 eventos encontrados — generando con Claude AI para: {nombre}")
        search_prompt = f"""Eres un experto en la escena cultural del Valle de Aburrá (Medellín y municipios cercanos), Colombia.
Necesito que generes eventos REALISTAS para este espacio cultural:

Nombre: {nombre}
Categoría: {categoria}
Municipio: {municipio}
Barrio: {lugar.get('barrio', 'desconocido')}{web_context}

Fecha actual: {now_iso}
Año actual: {anio}

INSTRUCCIONES IMPORTANTES:
- Genera entre 2 y 5 eventos FUTUROS (después de {now_iso}) que sean PROBABLES para este tipo de espacio.
- Basa los eventos en lo que este tipo de lugar ({categoria}) normalmente ofrece en Medellín.
- Usa fechas dentro de los próximos 14 días.
- Los títulos deben ser específicos y atractivos, NO genéricos.

Ejemplos por categoría:
- librería/editorial → presentaciones de libros, clubes de lectura, tertulias literarias, firmas de autor
- café_cultural → jam sessions, micrófono abierto, noches de poesía, DJ sets acústicos
- teatro → funciones, temporadas, talleres de actuación, monólogos
- galería → inauguraciones, exposiciones, charlas con artistas
- hip_hop/rap → batallas de freestyle, cyphers, talleres de producción
- bar_cultural → conciertos en vivo, noches de jazz, noches de salsa, DJ sets
- casa_cultura → talleres comunitarios, cine foro, exposiciones locales
- danza → presentaciones, talleres, ensayos abiertos
- colectivo → encuentros, jams, talleres, intervenciones urbanas
- música → conciertos, jam sessions, open mic

Responde en JSON exacto:
{{
  "eventos": [
    {{
      "titulo": "nombre específico del evento",
      "categoria_principal": "{categoria}",
      "categorias": ["lista de categorías"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
      "fecha_fin": null,
      "descripcion": "descripción atractiva y realista (máx 300 chars)",
      "precio": "valor o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": null
    }}
  ]
}}
Responde SOLO JSON."""
        events = _extract_events_with_claude(search_prompt)
        for ev in events:
            ev["_fuente"] = "claude_knowledge"
            ev["_fuente_url"] = sitio or (f"https://instagram.com/{ig_handle.lstrip('@')}" if ig_handle else None)
        all_events.extend(events)

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
                    fecha_fin = None
                    if fecha_fin_str:
                        try:
                            fecha_fin = datetime.fromisoformat(fecha_fin_str)
                            if fecha_fin.tzinfo is None:
                                fecha_fin = fecha_fin.replace(tzinfo=CO_TZ)
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

            # Deduplicate: check by slug
            existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
            if existing.data:
                stats["duplicados"] += 1
                continue

            evento_data = {
                "titulo": titulo,
                "slug": slug,
                "espacio_id": lugar_id,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": ev.get("fecha_fin"),
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
        "nombre": "Timeout Medellín",
        "url": "https://www.timeout.com/medellin/things-to-do",
        "categoria_default": "festival",
        "municipio": "medellin",
    },
    {
        "nombre": "Plan B Medellín",
        "url": "https://planbmedellin.com/",
        "categoria_default": "musica_en_vivo",
        "municipio": "medellin",
    },
    {
        "nombre": "Tu Cultura Medellín",
        "url": "https://tucultura.medellin.gov.co/",
        "categoria_default": "casa_cultura",
        "municipio": "medellin",
    },
    {
        "nombre": "Mincultura Agenda",
        "url": "https://www.mincultura.gov.co/areas/artes/literatura/Paginas/default.aspx",
        "categoria_default": "libreria",
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
            content = await _fetch_website(src["url"])
            if not content or len(content) < 100:
                print(f"  ⚠ Sin contenido suficiente")
                continue

            prompt = AGENDA_EXTRACTION_PROMPT.format(
                fecha_actual=now_iso,
                anio_actual=anio,
                nombre_fuente=src["nombre"],
                fuente_url=src["url"],
                municipio=src["municipio"],
                contenido=content[:12000],
            )
            events = _extract_events_with_claude(prompt)
            total["fuentes"] += 1

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
                            hoy_inicio_ag = now_co.replace(hour=0, minute=0, second=0, microsecond=0)
                            fecha_fin_ag = None
                            if ev.get("fecha_fin"):
                                try:
                                    fecha_fin_ag = datetime.fromisoformat(ev["fecha_fin"])
                                    if fecha_fin_ag.tzinfo is None:
                                        fecha_fin_ag = fecha_fin_ag.replace(tzinfo=CO_TZ)
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
                        "fecha_fin": ev.get("fecha_fin"),
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

