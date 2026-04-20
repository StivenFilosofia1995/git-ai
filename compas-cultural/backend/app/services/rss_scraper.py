# -*- coding: utf-8 -*-
"""
RSS Feed Scraper — descubrimiento y parseo de feeds RSS/Atom.
Sin LLM, sin rate limits, sin tokens. La fuente más eficiente.

Sitios confirmados con RSS:
- festivaldepoesiademedellin.org  → /feed
- comfama.com/agenda             → buscar en head
- platohedro.org                 → /feed
- Cualquier sitio WordPress/Ghost → /feed automático
"""
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from email.utils import parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup

# ─── RSS/Atom feed probing ─────────────────────────────────────────────────────

# Paths to try when looking for feeds
RSS_PROBE_PATHS = [
    "/feed",
    "/feed.xml",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed/rss",
    "/feed/atom",
    "/agenda/feed",
    "/eventos/feed",
    "/noticias/feed",
    "/programacion/feed",
    "/blog/feed",
    "/?feed=rss2",
]

RSS_CONTENT_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CulturaEtereaScraper/1.0)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
}


async def discover_rss_feed(site_url: str) -> Optional[str]:
    """
    Discover RSS/Atom feed for a site URL.
    
    Strategy:
    1. Check <link rel="alternate" type="application/rss+xml"> in page <head>
    2. Probe common RSS paths
    
    Returns the feed URL or None.
    """
    if not site_url:
        return None

    # Normalize base URL
    base = site_url.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"

    # 1. Parse <head> for feed link tags
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(base, headers=_HEADERS)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("link", rel="alternate"):
                    link_type = link.get("type", "")
                    if any(ct in link_type for ct in RSS_CONTENT_TYPES):
                        href = link.get("href", "")
                        if href:
                            if href.startswith("http"):
                                return href
                            return f"{base}/{href.lstrip('/')}"
    except Exception:
        pass

    # 2. Probe common paths
    from urllib.parse import urlparse
    parsed = urlparse(base)
    domain_base = f"{parsed.scheme}://{parsed.netloc}"

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for path in RSS_PROBE_PATHS:
            try:
                url = f"{domain_base}{path}"
                resp = await client.get(url, headers=_HEADERS)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "").lower()
                    if any(c in ct for c in ("xml", "rss", "atom")):
                        return url
                    # Also check if body looks like XML feed
                    text_start = resp.text[:200].strip().lower()
                    if "<rss" in text_start or "<feed" in text_start or "<channel" in text_start:
                        return url
            except Exception:
                continue

    return None


# ─── RSS Parsing ───────────────────────────────────────────────────────────────

def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RFC 2822 or ISO 8601 date strings from RSS/Atom."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Try RFC 2822 (RSS standard)
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        pass
    # Try ISO 8601 (Atom standard)
    try:
        clean = re.sub(r"[+-]\d{2}:\d{2}$", "", date_str)
        clean = re.sub(r"Z$", "", clean)
        return datetime.fromisoformat(clean)
    except Exception:
        pass
    return None


def _strip_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _extract_image_from_item(item_soup) -> Optional[str]:
    """Extract image from RSS item (enclosure, media:content, or img in description)."""
    # media:content
    media = item_soup.find("media:content")
    if media and media.get("url"):
        return media["url"]

    # enclosure
    enc = item_soup.find("enclosure")
    if enc and enc.get("url") and "image" in enc.get("type", ""):
        return enc["url"]

    # img in description/content:encoded
    for tag_name in ("content:encoded", "description", "summary", "content"):
        tag = item_soup.find(tag_name)
        if tag:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(tag))
            if img_match:
                return img_match.group(1)

    return None


async def parse_rss_events(feed_url: str, lugar: dict) -> list[dict]:
    """
    Parse RSS/Atom feed and extract events.
    
    Returns list of event dicts ready to insert into DB.
    Only returns events with fecha_inicio >= now - 7 days.
    """
    now_co = datetime.utcnow() - timedelta(hours=5)
    nombre = lugar.get("nombre", "")
    municipio = lugar.get("municipio", "medellin")
    categoria = lugar.get("categoria_principal", "otro")
    lugar_id = lugar.get("id")

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers=_HEADERS)
            resp.raise_for_status()
            raw_xml = resp.text
    except Exception as e:
        print(f"  [RSS] Error fetching {feed_url}: {e}")
        return []

    try:
        soup = BeautifulSoup(raw_xml, "xml")
    except Exception:
        try:
            soup = BeautifulSoup(raw_xml, "lxml-xml")
        except Exception:
            soup = BeautifulSoup(raw_xml, "html.parser")

    # Detect RSS vs Atom
    items = soup.find_all("item")      # RSS
    if not items:
        items = soup.find_all("entry")  # Atom

    if not items:
        print(f"  [RSS] No items found in feed: {feed_url}")
        return []

    events = []
    for item in items[:30]:  # max 30 items per feed
        try:
            # Title
            title_tag = item.find("title")
            titulo = _strip_html(title_tag.get_text() if title_tag else "").strip()
            if not titulo or len(titulo) < 3:
                continue

            # Date — RSS: pubDate, Atom: published/updated
            date_tag = (
                item.find("pubDate")
                or item.find("published")
                or item.find("updated")
                or item.find("dc:date")
            )
            date_str = date_tag.get_text().strip() if date_tag else ""
            fecha = _parse_rss_date(date_str)

            # If no date, skip
            if not fecha:
                continue

            # Filter: don't include events more than 7 days in the past
            if fecha < now_co - timedelta(days=7):
                continue
            # Don't include too far in future
            if fecha > now_co + timedelta(days=365):
                continue

            # Description
            desc_tag = (
                item.find("content:encoded")
                or item.find("description")
                or item.find("summary")
                or item.find("content")
            )
            desc_raw = desc_tag.get_text() if desc_tag else ""
            descripcion = _strip_html(desc_raw).strip()[:500] or None

            # URL
            link_tag = item.find("link")
            if link_tag:
                # Atom uses link[href], RSS uses link text
                fuente_url = link_tag.get("href") or link_tag.get_text().strip()
            else:
                guid_tag = item.find("guid")
                fuente_url = guid_tag.get_text().strip() if guid_tag else None

            # Image
            imagen_url = _extract_image_from_item(item)

            # Category from feed
            cat_tag = item.find("category")
            if cat_tag:
                cat_text = cat_tag.get_text().strip().lower()
                # Could map to known categories
                categoria_ev = cat_text if cat_text else categoria
            else:
                categoria_ev = categoria

            import unicodedata
            def _slugify(text: str) -> str:
                text = unicodedata.normalize("NFD", text.lower().strip())
                text = "".join(c for c in text if unicodedata.category(c) != "Mn")
                text = re.sub(r"[^a-z0-9]+", "-", text)
                return text.strip("-")[:250]

            events.append({
                "titulo": titulo[:200],
                "slug": _slugify(titulo),
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": None,
                "categorias": [categoria_ev],
                "categoria_principal": categoria_ev,
                "municipio": municipio,
                "barrio": lugar.get("barrio"),
                "nombre_lugar": nombre,
                "descripcion": descripcion,
                "imagen_url": imagen_url,
                "precio": "",
                "es_gratuito": False,
                "es_recurrente": False,
                "fuente": "worker_rss",
                "fuente_url": fuente_url,
                "verificado": False,
                "espacio_id": lugar_id,
            })

        except Exception as e:
            print(f"  [RSS] Error parsing item '{titulo if 'titulo' in dir() else '?'}': {e}")
            continue

    print(f"  [RSS] {len(events)} eventos de {feed_url[:60]}")
    return events


# ─── Sitios con RSS confirmado ──────────────────────────────────────────────────

# Cache de feeds ya descubiertos (en memoria, se resetea al reiniciar el worker)
_feed_cache: dict[str, Optional[str]] = {
    "https://festivaldepoesiademedellin.org": "https://festivaldepoesiademedellin.org/feed",
    "https://platohedro.org": "https://platohedro.org/feed",
    "https://tragaluzeditores.com": None,  # No tiene feed
}


async def get_or_discover_feed(site_url: str) -> Optional[str]:
    """Get cached feed URL or discover it for a site."""
    if site_url in _feed_cache:
        return _feed_cache[site_url]

    feed_url = await discover_rss_feed(site_url)
    _feed_cache[site_url] = feed_url  # cache result (even if None)
    return feed_url
