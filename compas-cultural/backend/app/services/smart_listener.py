"""
Smart Listener: intelligent event extraction system.
Uses Groq Vision (Llama 4 Scout) to read event flyers/images from Instagram posts.
Falls back to Claude only if Groq is unavailable.
Detects content changes to avoid re-processing.
Auto-discovers RSS feeds for real-time listening.
"""
import asyncio
import base64
import hashlib
import json
import re
import traceback
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.groq_client import groq_vision, groq_chat, parse_json_response, MODEL_FAST, MODEL_VISION


# ══════════════════════════════════════════════════════════════════
# CLAUDE VISION: Extract events from flyer images
# ══════════════════════════════════════════════════════════════════

VISION_PROMPT = """Hoy es {fecha_hoy} y estamos en el Valle de Aburrá, Colombia.

Analiza esta imagen de un evento/flyer cultural y extrae la información.
Si la imagen NO es un flyer de evento (es una foto casual, meme, selfie, etc.), responde {{"es_evento": false}}.

Si SÍ es un evento, extrae:
{{
  "es_evento": true,
  "titulo": "nombre del evento",
  "fecha_iso": "YYYY-MM-DDTHH:MM:SS (calcula la fecha real si dice 'este sábado', 'próximo viernes', etc.)",
  "descripcion": "descripción breve del evento (máx 200 chars)",
  "lugar": "nombre del lugar/venue si aparece",
  "direccion": "dirección si aparece",
  "precio": "precio si se menciona, o 'Entrada libre'",
  "es_gratuito": true/false,
  "categoria": "teatro|musica_en_vivo|jazz|hip_hop|electronica|danza|cine|galeria|arte_contemporaneo|libreria|poesia|fotografia|festival|taller|conferencia|otro",
  "artistas": ["lista de artistas/performers mencionados"]
}}

REGLAS:
- Si hay una fecha relativa ("este sábado"), calcula la fecha real desde hoy {fecha_hoy}
- Si no hay hora, usa 19:00:00 por defecto
- Si no hay fecha clara, intenta inferir del contexto
- Responde SOLO con JSON, sin texto adicional
"""

CAPTION_VISION_PROMPT = """Hoy es {fecha_hoy}, Valle de Aburrá, Colombia.

Analiza este post de Instagram (caption + imagen si hay) del espacio/colectivo cultural "{nombre_lugar}" ({municipio}).

CAPTION:
{caption}

{imagen_instruccion}

Extrae TODOS los eventos futuros mencionados. Para cada uno:
{{
  "titulo": "nombre del evento",
  "fecha_iso": "YYYY-MM-DDTHH:MM:SS",
  "descripcion": "descripción breve (máx 200 chars)",
  "lugar": "lugar del evento",
  "precio": "precio o 'Entrada libre'",
  "es_gratuito": true/false,
  "categoria": "teatro|musica_en_vivo|jazz|hip_hop|electronica|danza|cine|galeria|arte_contemporaneo|libreria|poesia|fotografia|festival|taller|conferencia|otro",
  "imagen_url": "URL de la imagen del post si existe"
}}

REGLAS:
- "Este sábado", "mañana", "el viernes" → calcula la fecha real
- Solo eventos FUTUROS (después de {fecha_hoy})
- Si NO hay eventos, devuelve []

Responde SOLO con un JSON array. Sin texto adicional.
"""


async def analyze_image_with_vision(
    image_url: str,
    caption: str = "",
    lugar_nombre: str = "",
    municipio: str = "medellin",
) -> list[dict]:
    """Use Groq Vision (Llama 4 Scout) to extract event data from an image.
    Falls back to Claude Vision ONLY if Groq is unavailable.
    """
    if not settings.groq_api_key and not settings.anthropic_api_key:
        return []

    now_co = datetime.utcnow() - timedelta(hours=5)
    fecha_hoy = now_co.strftime("%A %d de %B de %Y")

    try:
        # Build prompt
        if caption:
            prompt = CAPTION_VISION_PROMPT.format(
                fecha_hoy=fecha_hoy,
                nombre_lugar=lugar_nombre or "desconocido",
                municipio=municipio,
                caption=caption[:3000],
                imagen_instruccion="También analiza la imagen adjunta (flyer/poster) para extraer información visual.",
            )
        else:
            prompt = VISION_PROMPT.format(fecha_hoy=fecha_hoy)

        raw = None

        # ── PRIMARY: Groq Vision (Llama 4 Scout) — FREE ──
        if settings.groq_api_key:
            # Try passing image URL directly (up to 20MB supported)
            raw = await asyncio.to_thread(
                groq_vision, prompt, image_url=image_url,
                max_tokens=1500, temperature=0, json_mode=True,
            )
            if raw:
                print(f"  [VISION] Using Groq Llama 4 Scout (FREE)")

        # ── FALLBACK: Claude Vision (costs money) ──
        if not raw and settings.anthropic_api_key:
            image_data = await _download_image(image_url)
            if not image_data:
                if caption and len(caption) > 30:
                    return await _analyze_caption_only(caption, lugar_nombre, municipio)
                return []

            img_bytes, media_type = image_data
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": prompt},
            ]
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500, temperature=0,
                messages=[{"role": "user", "content": content}],
            )
            raw = response.content[0].text.strip()
            print(f"  [VISION] Fallback to Claude (costs tokens)")

        if not raw:
            return []

        parsed = parse_json_response(raw)
        if parsed is None:
            return []

        # Handle single event response vs array
        if isinstance(parsed, dict):
            if not parsed.get("es_evento", True):
                return []
            parsed = [parsed]

        # Convert to standard event format
        events = []
        for item in parsed:
            titulo = (item.get("titulo") or "").strip()
            if not titulo:
                continue

            fecha_str = item.get("fecha_iso", "")
            try:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha < now_co:
                    continue
            except (ValueError, TypeError):
                continue

            events.append({
                "titulo": titulo[:200],
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": None,
                "descripcion": (item.get("descripcion") or "")[:500],
                "precio": item.get("precio") or "",
                "es_gratuito": item.get("es_gratuito", False),
                "imagen_url": image_url,
                "nombre_lugar": item.get("lugar") or lugar_nombre,
                "categoria_principal": item.get("categoria") or "otro",
                "categorias": [item.get("categoria") or "otro"],
                "municipio": municipio,
                "fuente": "smart_listener_vision",
            })

        if events:
            print(f"  [VISION] ✓ {len(events)} evento(s) extraídos de imagen")
        return events

    except json.JSONDecodeError as e:
        print(f"  [VISION] JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"  [VISION] Error: {e}")
        return []
        print(f"  [VISION] Error: {e}")
        return []


async def _analyze_caption_only(caption: str, lugar_nombre: str, municipio: str) -> list[dict]:
    """Analyze caption text without image using Groq (free) or Claude (fallback)."""
    if not settings.groq_api_key and not settings.anthropic_api_key:
        return []

    now_co = datetime.utcnow() - timedelta(hours=5)
    fecha_hoy = now_co.strftime("%A %d de %B de %Y")

    prompt = CAPTION_VISION_PROMPT.format(
        fecha_hoy=fecha_hoy,
        nombre_lugar=lugar_nombre or "desconocido",
        municipio=municipio,
        caption=caption[:4000],
        imagen_instruccion="(Sin imagen disponible, analiza solo el texto del caption)",
    )

    try:
        raw = None

        # ── PRIMARY: Groq (Llama 3.1 8B — ultra cheap) ──
        if settings.groq_api_key:
            raw = await asyncio.to_thread(
                groq_chat, prompt, MODEL_FAST, 1500, 0, True,
            )

        # ── FALLBACK: Claude Haiku ──
        if not raw and settings.anthropic_api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=1500, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

        parsed = parse_json_response(raw)
        if not isinstance(parsed, list):
            return []

        events = []
        for item in parsed:
            titulo = (item.get("titulo") or "").strip()
            fecha_str = item.get("fecha_iso", "")
            if not titulo or not fecha_str:
                continue
            try:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha < now_co:
                    continue
            except (ValueError, TypeError):
                continue
            events.append({
                "titulo": titulo[:200],
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": None,
                "descripcion": (item.get("descripcion") or "")[:500],
                "precio": item.get("precio") or "",
                "es_gratuito": item.get("es_gratuito", False),
                "imagen_url": item.get("imagen_url"),
                "nombre_lugar": lugar_nombre,
                "categoria_principal": item.get("categoria") or "otro",
                "categorias": [item.get("categoria") or "otro"],
                "municipio": municipio,
                "fuente": "smart_listener_caption",
            })
        return events
    except Exception as e:
        print(f"  [CAPTION] Error: {e}")
        return []


async def _download_image(url: str) -> tuple[bytes, str] | None:
    """Download an image and return (bytes, media_type)."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "image/jpeg")
            if "jpeg" in content_type or "jpg" in content_type:
                media_type = "image/jpeg"
            elif "png" in content_type:
                media_type = "image/png"
            elif "webp" in content_type:
                media_type = "image/webp"
            elif "gif" in content_type:
                media_type = "image/gif"
            else:
                media_type = "image/jpeg"  # default

            img_bytes = resp.content
            # Limit to 5MB
            if len(img_bytes) > 5 * 1024 * 1024:
                return None

            return img_bytes, media_type
    except Exception as e:
        print(f"  [IMG] Download failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
# CONTENT CHANGE DETECTION: Only process new/changed content
# ══════════════════════════════════════════════════════════════════

def _hash_content(content: str) -> str:
    """Create a hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


async def has_content_changed(lugar_id: str, content: str) -> bool:
    """Check if the content for a lugar has changed since last scrape."""
    new_hash = _hash_content(content)
    try:
        resp = supabase.table("scraping_state").select("content_hash").eq(
            "lugar_id", lugar_id
        ).single().execute()
        if resp.data and resp.data["content_hash"] == new_hash:
            return False  # No change
    except Exception:
        pass  # Table may not exist yet, or no previous state — treat as changed
    return True


async def update_scraping_state(lugar_id: str, content: str, events_found: int):
    """Update the scraping state for a lugar after processing."""
    new_hash = _hash_content(content)
    now = datetime.utcnow().isoformat()
    try:
        supabase.table("scraping_state").upsert({
            "lugar_id": lugar_id,
            "content_hash": new_hash,
            "last_scraped_at": now,
            "events_found": events_found,
            "consecutive_empty": 0 if events_found > 0 else None,  # reset on success
        }, on_conflict="lugar_id").execute()
    except Exception:
        pass  # Table may not exist yet — silently skip


async def increment_empty_count(lugar_id: str):
    """Track consecutive empty scrapes to reduce frequency for inactive sources."""
    try:
        resp = supabase.table("scraping_state").select("consecutive_empty").eq(
            "lugar_id", lugar_id
        ).single().execute()
        current = (resp.data or {}).get("consecutive_empty", 0) or 0
        supabase.table("scraping_state").upsert({
            "lugar_id": lugar_id,
            "last_scraped_at": datetime.utcnow().isoformat(),
            "consecutive_empty": current + 1,
            "events_found": 0,
        }, on_conflict="lugar_id").execute()
    except Exception:
        pass  # Table may not exist yet


async def get_scrape_priority(lugar_id: str) -> str:
    """Determine scrape priority: 'high', 'normal', 'low' based on history."""
    try:
        resp = supabase.table("scraping_state").select(
            "consecutive_empty,events_found,last_scraped_at"
        ).eq("lugar_id", lugar_id).single().execute()
        if not resp.data:
            return "high"  # Never scraped = high priority

        empty = resp.data.get("consecutive_empty", 0) or 0
        last_events = resp.data.get("events_found", 0) or 0

        if empty >= 5:
            return "low"  # 5+ consecutive empties → scrape less
        if last_events > 0:
            return "high"  # Recently had events → scrape more
        return "normal"
    except Exception:
        return "normal"  # Table may not exist yet


# ══════════════════════════════════════════════════════════════════
# RSS/ATOM FEED AUTO-DISCOVERY & LISTENING
# ══════════════════════════════════════════════════════════════════

async def discover_rss_feed(url: str) -> str | None:
    """Auto-discover RSS/Atom feed from a website URL."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CulturaEterea/1.0)"
            })
            if resp.status_code != 200:
                return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for <link rel="alternate" type="application/rss+xml">
        for link in soup.find_all("link", rel="alternate"):
            link_type = (link.get("type") or "").lower()
            if "rss" in link_type or "atom" in link_type or "xml" in link_type:
                href = link.get("href")
                if href:
                    # Handle relative URLs
                    if href.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        href = f"{parsed.scheme}://{parsed.netloc}{href}"
                    return href

        # Try common feed paths
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        common_paths = ["/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/blog/feed"]

        for path in common_paths:
            feed_url = base + path
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
                    resp = await client.head(feed_url)
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "")
                        if "xml" in content_type or "rss" in content_type:
                            return feed_url
            except Exception:
                continue

        return None
    except Exception:
        return None


async def parse_rss_events(feed_url: str, lugar: dict) -> list[dict]:
    """Parse an RSS/Atom feed and extract cultural events."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(feed_url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CulturaEterea/1.0)"
            })
            if resp.status_code != 200:
                return []

        soup = BeautifulSoup(resp.text, "xml")
        events = []
        now_co = datetime.utcnow() - timedelta(hours=5)
        nombre = lugar.get("nombre", "")
        municipio = lugar.get("municipio", "medellin")

        # Parse RSS items
        items = soup.find_all("item") or soup.find_all("entry")
        for item in items[:30]:
            title = item.find("title")
            desc = item.find("description") or item.find("content") or item.find("summary")
            link = item.find("link")
            pub_date = item.find("pubDate") or item.find("published") or item.find("updated")

            if not title:
                continue

            titulo = title.get_text(strip=True)
            descripcion = ""
            if desc:
                # Strip HTML from description
                desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
                descripcion = desc_soup.get_text(strip=True)[:500]

            link_url = ""
            if link:
                link_url = link.get("href") or link.get_text(strip=True)

            # Check if this looks like an event
            from app.services.auto_scraper import _detect_category, _parse_date_from_text, _extract_time, EVENT_KEYWORDS
            full_text = f"{titulo} {descripcion}".lower()
            is_event = any(kw in full_text for kw in EVENT_KEYWORDS)

            if not is_event:
                continue

            # Try to extract date from content
            fecha = _parse_date_from_text(f"{titulo} {descripcion}", now_co.year)
            if not fecha or fecha < now_co:
                continue

            hour, minute = _extract_time(f"{titulo} {descripcion}")
            fecha = fecha.replace(hour=hour, minute=minute)

            # Extract image from description HTML
            imagen_url = None
            if desc:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc))
                if img_match:
                    imagen_url = img_match.group(1)

            events.append({
                "titulo": titulo[:200],
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": None,
                "descripcion": descripcion[:500],
                "precio": "",
                "es_gratuito": False,
                "imagen_url": imagen_url,
                "nombre_lugar": nombre,
                "categoria_principal": _detect_category(full_text),
                "categorias": [_detect_category(full_text)],
                "municipio": municipio,
                "barrio": lugar.get("barrio"),
                "fuente": "smart_listener_rss",
                "fuente_url": link_url or feed_url,
            })

        if events:
            print(f"  [RSS] ✓ {len(events)} evento(s) de feed RSS")
        return events

    except Exception as e:
        print(f"  [RSS] Error parsing feed: {e}")
        return []


# ══════════════════════════════════════════════════════════════════
# META GRAPH API: Enhanced Instagram with Vision
# ══════════════════════════════════════════════════════════════════

async def fetch_ig_posts_with_images(handle: str) -> list[dict]:
    """Fetch Instagram posts WITH image URLs via Meta Graph API.
    Returns structured posts with caption + image_url for Vision analysis.
    """
    from app.services.meta_token_manager import get_valid_token

    token = await get_valid_token()
    if not token:
        # Fallback to env token
        token = settings.meta_access_token
    if not token or not settings.meta_ig_business_account_id:
        return []

    clean = handle.lstrip("@").strip().split("/")[0]
    fields = (
        "business_discovery.fields(username,biography,"
        "media.limit(20){caption,timestamp,media_url,permalink,media_type,thumbnail_url})"
        f".username({clean})"
    )
    url = (
        f"https://graph.facebook.com/v21.0/{settings.meta_ig_business_account_id}"
        f"?fields={fields}&access_token={token}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                print(f"  [IG Meta] {resp.status_code} for @{clean}: {resp.text[:200]}")
                return []

            data = resp.json()
            bd = data.get("business_discovery", {})
            media_items = bd.get("media", {}).get("data", [])

            posts = []
            for m in media_items:
                post = {
                    "caption": (m.get("caption") or "").strip(),
                    "image_url": m.get("media_url") or m.get("thumbnail_url"),
                    "permalink": m.get("permalink", ""),
                    "timestamp": m.get("timestamp", ""),
                    "media_type": m.get("media_type", ""),
                }
                if post["caption"] or post["image_url"]:
                    posts.append(post)

            if posts:
                print(f"  [IG Meta] ✓ {len(posts)} posts con imagen para @{clean}")
            return posts

    except Exception as e:
        print(f"  [IG Meta] Error: {e}")
        return []


async def smart_scrape_instagram(lugar: dict) -> list[dict]:
    """Intelligent Instagram scraping:
    1. Fetch posts via Meta API (text + images)
    2. For each post with a flyer image → Claude Vision
    3. For text-heavy posts → Claude text analysis
    4. Deduplicate results
    """
    ig_handle = lugar.get("instagram_handle")
    if not ig_handle:
        return []

    nombre = lugar.get("nombre", "")
    municipio = lugar.get("municipio", "medellin")

    # Get posts with images
    posts = await fetch_ig_posts_with_images(ig_handle)
    if not posts:
        print(f"  [SMART] No posts from Meta API for {ig_handle}")
        return []

    all_events = []
    vision_count = 0
    max_vision_calls = 5  # Limit Vision calls per lugar (cost control)

    for post in posts:
        caption = post.get("caption", "")
        image_url = post.get("image_url", "")
        permalink = post.get("permalink", "")

        # Skip posts older than 30 days (unlikely to have future events)
        timestamp = post.get("timestamp", "")
        if timestamp:
            try:
                post_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00").split("+")[0])
                if post_date < datetime.utcnow() - timedelta(days=30):
                    continue
            except (ValueError, TypeError):
                pass

        # Strategy: Use Vision for image posts, text analysis for captions
        if image_url and vision_count < max_vision_calls:
            # Check if this looks like it could be an event post
            if _might_be_event_post(caption):
                events = await analyze_image_with_vision(
                    image_url, caption, nombre, municipio
                )
                vision_count += 1
                for ev in events:
                    ev["fuente_url"] = permalink or ev.get("fuente_url", "")
                    ev["imagen_url"] = image_url
                all_events.extend(events)
                if events:
                    continue  # Got events from Vision, skip text analysis

        # Text-only analysis for posts with substantial captions
        if caption and len(caption) > 50 and _might_be_event_post(caption):
            events = await _analyze_caption_only(caption, nombre, municipio)
            for ev in events:
                ev["fuente_url"] = permalink or ev.get("fuente_url", "")
                if image_url:
                    ev["imagen_url"] = image_url
            all_events.extend(events)

    # Deduplicate by title similarity
    all_events = _deduplicate_events(all_events)

    if all_events:
        print(f"  [SMART] ✓ {len(all_events)} evento(s) total ({vision_count} Vision calls)")
    return all_events


def _might_be_event_post(caption: str) -> bool:
    """Quick heuristic: does this caption look like it might announce an event?"""
    if not caption:
        return True  # If no caption, check the image

    caption_lower = caption.lower()
    event_signals = [
        "evento", "concierto", "taller", "exposición", "exposicion",
        "festival", "presentación", "presentacion", "inauguración",
        "inauguracion", "charla", "foro", "clase", "jam", "open mic",
        "entrada", "boleta", "cover", "gratis", "libre",
        "fecha", "hora", "lugar", "dónde", "donde", "cuándo", "cuando",
        "sábado", "sabado", "viernes", "domingo", "jueves",
        "próximo", "proximo", "este", "mañana", "hoy",
        "pm", "am", "p.m.", "a.m.",
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        "invitamos", "te esperamos", "los esperamos", "no te pierdas",
        "lanzamiento", "estreno", "función", "funcion", "tocada",
        "fiesta", "party", "show", "live", "en vivo",
        "dirección", "direccion", "reserva", "reservas",
    ]
    return any(signal in caption_lower for signal in event_signals)


def _deduplicate_events(events: list[dict]) -> list[dict]:
    """Remove duplicate events by similar titles and dates."""
    seen = set()
    unique = []
    for ev in events:
        # Create a key from normalized title + date
        title_key = re.sub(r"[^a-z0-9]", "", (ev.get("titulo") or "").lower())[:30]
        date_key = (ev.get("fecha_inicio") or "")[:10]
        key = f"{title_key}_{date_key}"
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique
