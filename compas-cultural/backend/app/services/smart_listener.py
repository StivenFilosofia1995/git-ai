"""
Smart Listener: extracción determinista de eventos desde RSS e Instagram.
SIN IA — usa únicamente regex, HTML parsing y scrapers de código.
Detecta cambios de contenido para no reprocesar fuentes sin novedades.
"""
import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase


# ══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DETERMINISTA — SIN IA
# Las funciones de Vision/AI se eliminaron para evitar alucinaciones.
# Los eventos se extraen únicamente de texto estructurado (regex + fechas).
# ══════════════════════════════════════════════════════════════════

async def analyze_image_with_vision(
    image_url: str,
    caption: str = "",
    lugar_nombre: str = "",
    municipio: str = "medellin",
) -> list[dict]:
    """Vision AI eliminada — retorna vacío para evitar alucinaciones.
    Los captions de Instagram se procesan en extract_events_from_ig_profile (regex puro).
    """
    return []


async def _analyze_caption_only(caption: str, lugar_nombre: str, municipio: str) -> list[dict]:
    """Caption AI eliminada — retorna vacío para evitar alucinaciones.
    Los captions se procesan mediante ig_event_extractor (regex + fechas).
    """
    return []


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
    """Instagram scraping sin IA — usa ig_event_extractor (regex puro).
    Obtiene posts via Meta API y extrae eventos con patrones deterministas.
    """
    ig_handle = lugar.get("instagram_handle")
    if not ig_handle:
        return []

    nombre = lugar.get("nombre", "")
    municipio = lugar.get("municipio", "medellin")
    categoria = lugar.get("categoria_principal", "otro")

    try:
        from app.services.auto_scraper import _fetch_ig_profile_via_meta_api
        from app.services.instagram_pw_scraper import fetch_ig_profile
        from app.services.ig_event_extractor import extract_events_from_ig_profile

        clean_handle = ig_handle.lstrip("@").split("/")[0].strip()

        profile = await _fetch_ig_profile_via_meta_api(clean_handle)
        if not profile:
            profile = await fetch_ig_profile(clean_handle)

        if not profile or not (profile.get("captions") or profile.get("biography")):
            print(f"  [SMART] No profile content for {ig_handle}")
            return []

        events = extract_events_from_ig_profile(profile, nombre, categoria, municipio)
        ig_url = f"https://instagram.com/{clean_handle}"
        for ev in events:
            if not ev.get("fuente_url"):
                ev["fuente_url"] = ev.pop("_permalink", None) or ig_url

        events = _deduplicate_events(events)
        if events:
            print(f"  [SMART] ✓ {len(events)} evento(s) extraídos (regex) de @{clean_handle}")
        return events

    except Exception as e:
        print(f"  [SMART] Error scraping @{ig_handle}: {e}")
        return []


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
