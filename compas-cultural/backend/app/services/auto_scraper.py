"""
Auto-scraper: sistema automatico de scraping para todos los lugares registrados.
Extraccion por regex/HTML. Claude se usa como fallback para parsear captions de Instagram
cuando las fechas son informales ("este sabado", "mañana", etc.).
"""
import json
import re
import traceback
import asyncio
import unicodedata
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import anthropic
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase


# -- Helpers -------------------------------------------------------------------

def _slugify(text: str) -> str:
    # Normalize unicode: decompose accented chars then strip combining marks
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

# Categories we recognize
CATEGORY_KEYWORDS = {
    "teatro": ["teatro", "obra", "funcion", "monologos", "dramaturg", "actua"],
    "musica_en_vivo": ["concierto", "recital", "musica en vivo", "live music", "banda", "sinfoni"],
    "jazz": ["jazz", "bossa nova", "swing"],
    "hip_hop": ["hip hop", "hip-hop", "rap", "freestyle", "cypher", "batalla"],
    "electronica": ["electronica", "dj", "techno", "house", "rave", "club night"],
    "danza": ["danza", "baile", "ballet", "contemporanea", "salsa", "tango"],
    "cine": ["cine", "pelicula", "documental", "cortometraje", "cine foro", "proyeccion"],
    "galeria": ["exposicion", "galeria", "muestra", "inauguracion", "arte visual"],
    "arte_contemporaneo": ["arte contemporaneo", "instalacion", "performance art"],
    "libreria": ["libro", "lectura", "literatur", "biblioteca", "editorial"],
    "poesia": ["poesia", "poema", "recital poetico", "slam", "microfono abierto"],
    "fotografia": ["fotografia", "foto", "exposicion fotografica"],
    "festival": ["festival", "feria", "fiesta", "carnaval", "celebracion"],
    "taller": ["taller", "workshop", "clase", "curso", "formacion", "capacitacion"],
    "conferencia": ["conferencia", "charla", "conversatorio", "foro", "panel", "seminario"],
}


def _detect_category(text: str) -> str:
    """Detect event category from text using keyword matching."""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "otro"


# -- Date extraction with regex ------------------------------------------------

# Spanish months
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

DATE_PATTERNS = [
    # "18 de abril de 2026" or "18 de abril, 2026"
    re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})", re.I),
    # "abril 18, 2026"
    re.compile(r"(\w+)\s+(\d{1,2}),?\s*(\d{4})", re.I),
    # "2026-04-18" ISO format
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    # "18/04/2026" or "18-04-2026"
    re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
]

TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?")


def _parse_date_from_text(text: str, year_default: int) -> Optional[datetime]:
    """Try to extract a date from Spanish text."""
    for i, pattern in enumerate(DATE_PATTERNS):
        match = pattern.search(text)
        if not match:
            continue
        try:
            if i == 0:  # "18 de abril de 2026"
                day = int(match.group(1))
                month_str = match.group(2).lower()
                year = int(match.group(3))
                month = MESES.get(month_str)
                if not month:
                    continue
                return datetime(year, month, day, 19, 0)
            elif i == 1:  # "abril 18, 2026"
                month_str = match.group(1).lower()
                day = int(match.group(2))
                year = int(match.group(3))
                month = MESES.get(month_str)
                if not month:
                    continue
                return datetime(year, month, day, 19, 0)
            elif i == 2:  # ISO "2026-04-18"
                return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), 19, 0)
            elif i == 3:  # "18/04/2026"
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day, 19, 0)
        except (ValueError, TypeError):
            continue

    # Try to find just day + month without year
    month_match = re.search(r"(\d{1,2})\s+de\s+(\w+)", text, re.I)
    if month_match:
        try:
            day = int(month_match.group(1))
            month = MESES.get(month_match.group(2).lower())
            if month and 1 <= day <= 31:
                return datetime(year_default, month, day, 19, 0)
        except (ValueError, TypeError):
            pass

    return None


def _extract_time(text: str) -> tuple:
    """Extract hour and minute from text."""
    match = TIME_PATTERN.search(text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        return hour, minute
    return 19, 0  # default 7pm


def _is_price_free(text: str) -> bool:
    """Check if an event is free."""
    free_keywords = ["entrada libre", "gratuito", "gratis", "sin costo", "free", "libre"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in free_keywords)


# -- Web fetchers (async, no AI) -----------------------------------------------

async def _fetch_website(url: str) -> Optional[str]:
    """Fetch and extract text from a website."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

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
        print(f"  [WARN] Error fetching {url}: {e}")
        return None


async def _fetch_website_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetch and return BeautifulSoup object for structured extraction."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [WARN] Error fetching {url}: {e}")
        return None


async def _fetch_instagram_meta_api(handle: str) -> Optional[str]:
    """Fetch Instagram posts via Meta Graph API Business Discovery (primary method).
    
    IMPORTANT: The username MUST be embedded inside the fields parameter using
    .username(target) syntax — NOT as a separate query parameter.
    Meta changed this circa 2025; the old &username=X format returns error #100.
    """
    if not settings.meta_access_token or not settings.meta_ig_business_account_id:
        return None
    clean = handle.lstrip("@").strip().split("/")[0]
    # Username is embedded in the fields expansion — this is the ONLY format that works
    fields = (
        "business_discovery.fields(username,biography,"
        "media.limit(20){caption,timestamp,media_url,permalink,media_type})"
        f".username({clean})"
    )
    url = (
        f"https://graph.facebook.com/v21.0/{settings.meta_ig_business_account_id}"
        f"?fields={fields}&access_token={settings.meta_access_token}"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                print(f"  [IG Meta API] {resp.status_code} for @{clean}: {resp.text[:200]}")
                return None
            data = resp.json()
            bd = data.get("business_discovery", {})
            bio = bd.get("biography", "")
            media = bd.get("media", {}).get("data", [])
            if not media:
                return None
            parts = []
            if bio:
                parts.append(f"BIO: {bio}")
            for m in media:
                caption = m.get("caption", "").strip()
                permalink = m.get("permalink", "")
                img = m.get("media_url", "")
                if caption:
                    block = caption
                    if img:
                        block += f"\n[IMAGE_URL: {img}]"
                    if permalink:
                        block += f"\n[PERMALINK: {permalink}]"
                    parts.append(block)
            content = "\n---\n".join(parts)
            if len(content) > 200:
                print(f"  [IG Meta API] ✓ {len(media)} posts para @{clean}")
                return content[:8000]
    except Exception as e:
        print(f"  [IG Meta API] Error para @{clean}: {e}")
    return None


IG_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

IG_JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-CO,es;q=0.9",
    "X-IG-App-ID": "936619743392459",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.instagram.com/",
    "Origin": "https://www.instagram.com",
}


async def _fetch_instagram_direct(handle: str) -> Optional[str]:
    """Try to scrape Instagram directly using their internal JSON API."""
    clean = handle.lstrip("@").strip().split("/")[0]

    # Method 1: Instagram internal JSON endpoint (works without login sometimes)
    json_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={clean}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(json_url, headers=IG_JSON_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("data", {}).get("user", {})
                bio = user.get("biography", "")
                edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
                parts = []
                if bio:
                    parts.append(f"BIO: {bio}")
                for edge in edges[:20]:
                    node = edge.get("node", {})
                    caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                    caption = " ".join(e.get("node", {}).get("text", "") for e in caption_edges).strip()
                    shortcode = node.get("shortcode", "")
                    img = node.get("display_url", "")
                    if caption:
                        block = caption
                        if img:
                            block += f"\n[IMAGE_URL: {img}]"
                        if shortcode:
                            block += f"\n[PERMALINK: https://www.instagram.com/p/{shortcode}/]"
                        parts.append(block)
                content = "\n---\n".join(parts)
                if len(content) > 200:
                    print(f"  [IG direct JSON] ✓ {len(edges)} posts para @{clean}")
                    return content[:8000]
    except Exception as e:
        print(f"  [IG direct JSON] error @{clean}: {e}")

    # Method 2: Mobile page scrape (returns more readable HTML)
    profile_url = f"https://www.instagram.com/{clean}/"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(profile_url, headers=IG_MOBILE_HEADERS)
            if resp.status_code == 200 and "window._sharedData" in resp.text:
                # Extract shared data JSON embedded in page
                match = re.search(r"window\._sharedData\s*=\s*(\{.+?\});</script>", resp.text, re.S)
                if match:
                    shared = json.loads(match.group(1))
                    try:
                        edges = (
                            shared["entry_data"]["ProfilePage"][0]
                            ["graphql"]["user"]["edge_owner_to_timeline_media"]["edges"]
                        )
                        parts = []
                        for edge in edges[:20]:
                            node = edge.get("node", {})
                            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                            caption = " ".join(e.get("node", {}).get("text", "") for e in caption_edges).strip()
                            shortcode = node.get("shortcode", "")
                            if caption:
                                block = caption
                                if shortcode:
                                    block += f"\n[PERMALINK: https://www.instagram.com/p/{shortcode}/]"
                                parts.append(block)
                        content = "\n---\n".join(parts)
                        if len(content) > 200:
                            print(f"  [IG mobile sharedData] ✓ {len(edges)} posts para @{clean}")
                            return content[:8000]
                    except (KeyError, IndexError, json.JSONDecodeError):
                        pass
    except Exception as e:
        print(f"  [IG mobile] error @{clean}: {e}")

    return None


async def _fetch_instagram_public_scraper(handle: str) -> Optional[str]:
    """Fetch Instagram profile via public third-party scrapers (last resort)."""
    clean = handle.lstrip("@").strip().split("/")[0]

    # Try working mirrors/proxies — these change frequently
    scrapers = [
        ("picuki",    f"https://www.picuki.com/profile/{clean}"),
        ("imginn",    f"https://imginn.com/{clean}/"),
        ("gramhir",   f"https://gramhir.com/profile/{clean}/0"),
        ("instanavigation", f"https://instanavigation.com/profile/{clean}"),
        ("pixwox",    f"https://www.pixwox.com/profile/{clean}/"),
        ("bibliogram", f"https://bibliogram.art/u/{clean}"),
    ]

    for name, url in scrapers:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code != 200:
                    continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
                tag.decompose()

            text_parts = []
            bio = soup.find(class_=re.compile(r"bio|description|profile-desc|profile-info", re.I))
            if bio:
                text_parts.append(f"BIO: {bio.get_text(strip=True)}")

            captions = soup.find_all(class_=re.compile(
                r"caption|photo-description|post-text|post-caption|item-description", re.I
            ))
            for cap in captions[:20]:
                text = cap.get_text(strip=True)
                if text and len(text) > 10:
                    text_parts.append(text)

            if not text_parts:
                raw = soup.get_text(separator="\n", strip=True)
                # Skip if it's a login/block page
                raw_lower = raw.lower()
                if any(kw in raw_lower for kw in ["log in", "sign up", "blocked", "not found"]):
                    continue
                if raw:
                    text_parts.append(raw)

            content = "\n---\n".join(text_parts)
            if len(content) > 200:
                print(f"  [IG {name}] ✓ contenido de @{clean}")
                return content[:8000]
        except Exception:
            continue

    return None


async def _search_google_events(nombre: str, municipio: str, ig_handle: str = "") -> Optional[str]:
    """Search Google for events when Instagram fails (personal accounts, etc.).
    Includes IG-specific searches and cultural event platforms."""
    clean_handle = ig_handle.lstrip("@").strip().split("/")[0] if ig_handle else ""
    queries = [
        f"{nombre} eventos {municipio} 2026",
        f"{nombre} agenda cultural {municipio}",
    ]
    # If we have an IG handle, search for their posts via Google cache
    if clean_handle:
        queries.insert(0, f"site:instagram.com {clean_handle} evento")
        queries.append(f'"{clean_handle}" eventos medellin')
    all_text = []
    for q in queries[:4]:  # Limit to 4 queries to avoid rate limiting
        url = f"https://www.google.com/search?q={urllib.parse.quote(q)}&hl=es&gl=co&num=5"
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "es-CO,es;q=0.9",
                })
                if resp.status_code != 200:
                    continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "svg", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            if text:
                all_text.append(text[:3000])
        except Exception as e:
            print(f"  [Google] Error buscando '{q}': {e}")
            continue

    # Also try scraping event listing sites directly
    event_sites = [
        f"https://www.meetup.com/find/?keywords={urllib.parse.quote(nombre)}&location=co--medell%C3%ADn",
    ]
    for url in event_sites:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "svg", "noscript"]):
                        tag.decompose()
                    text = soup.get_text(separator="\n", strip=True)
                    if text and len(text) > 100:
                        all_text.append(text[:3000])
        except Exception:
            continue

    combined = "\n---\n".join(all_text)
    if len(combined) > 200:
        print(f"  [Google] ✓ Contenido encontrado para '{nombre}'")
        return combined[:8000]
    return None


async def _fetch_instagram_profile(handle: str) -> Optional[str]:
    """Fetch Instagram profile using multiple methods in priority order:
    1. Meta Graph API   (best, requires META_ACCESS_TOKEN in Railway env)
    2. Direct IG JSON   (works without credentials, often succeeds)
    3. Public scrapers  (last resort, frequently blocked)
    """
    # 1. Meta Graph API
    content = await _fetch_instagram_meta_api(handle)
    if content:
        return content

    # 2. Direct Instagram JSON/mobile endpoint
    content = await _fetch_instagram_direct(handle)
    if content:
        return content

    # 3. Public third-party scrapers
    content = await _fetch_instagram_public_scraper(handle)
    return content


# -- Code-based event extraction (NO Claude) -----------------------------------

# Event-like keywords to identify event blocks in HTML
EVENT_KEYWORDS = [
    "evento", "event", "concierto", "concert", "taller", "workshop",
    "exposicion", "exhibition", "funcion", "show", "festival",
    "presentacion", "inauguracion", "charla", "foro", "clase",
    "recital", "proyeccion", "lanzamiento", "encuentro", "jam",
]


def _extract_events_from_html(soup: BeautifulSoup, lugar: dict, source_url: str) -> list[dict]:
    """Extract events from HTML using structured patterns (NO AI).
    
    Looks for:
    1. Schema.org Event structured data (JSON-LD)
    2. Common event card patterns (h2/h3 + date + description)
    3. Date + title patterns in text
    """
    events = []
    now_co = datetime.utcnow() - timedelta(hours=5)
    year = now_co.year
    nombre = lugar["nombre"]
    categoria = lugar.get("categoria_principal", "otro")
    municipio = lugar.get("municipio", "medellin")

    # 1. JSON-LD structured data (best quality)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Event":
                    titulo = item.get("name", "")
                    if not titulo:
                        continue
                    fecha_str = item.get("startDate", "")
                    try:
                        fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00").split("+")[0])
                    except (ValueError, TypeError):
                        fecha = _parse_date_from_text(fecha_str, year)
                    
                    if not fecha or fecha < now_co:
                        continue

                    events.append({
                        "titulo": titulo[:200],
                        "fecha_inicio": fecha.isoformat(),
                        "fecha_fin": item.get("endDate"),
                        "descripcion": (item.get("description") or "")[:500],
                        "precio": item.get("offers", {}).get("price", ""),
                        "es_gratuito": item.get("isAccessibleForFree", False),
                        "imagen_url": item.get("image"),
                        "nombre_lugar": item.get("location", {}).get("name", nombre),
                        "categoria_principal": _detect_category(titulo),
                        "categorias": [_detect_category(titulo)],
                        "municipio": municipio,
                        "barrio": lugar.get("barrio"),
                        "fuente": "auto_scraper_jsonld",
                        "fuente_url": source_url,
                    })
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # 2. Common HTML event patterns
    # Look for containers that might hold events
    event_containers = soup.find_all(class_=re.compile(
        r"event|evento|agenda|programa|calendar|actividad", re.I
    ))
    
    for container in event_containers[:20]:
        # Find title
        title_tag = container.find(["h1", "h2", "h3", "h4", "a"])
        if not title_tag:
            continue
        titulo = title_tag.get_text(strip=True)
        if len(titulo) < 5 or len(titulo) > 300:
            continue

        # Find date in the container
        container_text = container.get_text(separator=" ", strip=True)
        fecha = _parse_date_from_text(container_text, year)
        if not fecha or fecha < now_co:
            continue

        # Extract time if present
        hour, minute = _extract_time(container_text)
        fecha = fecha.replace(hour=hour, minute=minute)

        # Description
        desc_tag = container.find(["p", "span", "div"], class_=re.compile(r"desc|detail|content|texto", re.I))
        descripcion = desc_tag.get_text(strip=True)[:500] if desc_tag else ""

        # Image
        img_tag = container.find("img")
        imagen_url = img_tag.get("src") if img_tag else None

        # Price
        price_text = container_text
        es_gratuito = _is_price_free(price_text)

        events.append({
            "titulo": titulo[:200],
            "fecha_inicio": fecha.isoformat(),
            "fecha_fin": None,
            "descripcion": descripcion,
            "precio": "Entrada libre" if es_gratuito else "",
            "es_gratuito": es_gratuito,
            "imagen_url": imagen_url,
            "nombre_lugar": nombre,
            "categoria_principal": _detect_category(titulo + " " + descripcion),
            "categorias": [_detect_category(titulo + " " + descripcion)],
            "municipio": municipio,
            "barrio": lugar.get("barrio"),
            "fuente": "auto_scraper_html",
            "fuente_url": source_url,
        })

    return events


def _extract_events_from_text(text: str, lugar: dict, source_url: str) -> list[dict]:
    """Extract events from plain text using regex patterns (fallback).
    
    Looks for patterns like:
    - Title + date
    - Date + title + description blocks
    """
    events = []
    now_co = datetime.utcnow() - timedelta(hours=5)
    year = now_co.year
    nombre = lugar["nombre"]
    categoria = lugar.get("categoria_principal", "otro")
    municipio = lugar.get("municipio", "medellin")

    # Split text into paragraphs/blocks
    blocks = re.split(r"\n{2,}", text)

    for block in blocks:
        block = block.strip()
        if len(block) < 20:
            continue

        # Check if block contains event-like keywords
        block_lower = block.lower()
        has_event_keyword = any(kw in block_lower for kw in EVENT_KEYWORDS)
        if not has_event_keyword:
            continue

        # Try to extract a date
        fecha = _parse_date_from_text(block, year)
        if not fecha or fecha < now_co:
            continue

        # Extract time
        hour, minute = _extract_time(block)
        fecha = fecha.replace(hour=hour, minute=minute)

        # The first line is likely the title
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        titulo = lines[0][:200] if lines else "Evento"
        descripcion = " ".join(lines[1:3])[:500] if len(lines) > 1 else ""

        es_gratuito = _is_price_free(block)

        events.append({
            "titulo": titulo,
            "fecha_inicio": fecha.isoformat(),
            "fecha_fin": None,
            "descripcion": descripcion,
            "precio": "Entrada libre" if es_gratuito else "",
            "es_gratuito": es_gratuito,
            "imagen_url": None,
            "nombre_lugar": nombre,
            "categoria_principal": _detect_category(block),
            "categorias": [_detect_category(block)],
            "municipio": municipio,
            "barrio": lugar.get("barrio"),
            "fuente": "auto_scraper_text",
            "fuente_url": source_url,
        })

    return events


def _extract_events_from_ig_text(text: str, lugar: dict) -> list[dict]:
    """Extract events from Instagram caption text using regex."""
    events = []
    now_co = datetime.utcnow() - timedelta(hours=5)
    year = now_co.year
    nombre = lugar["nombre"]
    categoria = lugar.get("categoria_principal", "otro")
    municipio = lugar.get("municipio", "medellin")
    ig_handle = lugar.get("instagram_handle", "")

    # Split by post separators
    posts = re.split(r"---+", text)

    for post in posts:
        post = post.strip()
        if len(post) < 30:
            continue

        post_lower = post.lower()
        has_event_keyword = any(kw in post_lower for kw in EVENT_KEYWORDS)
        if not has_event_keyword:
            continue

        fecha = _parse_date_from_text(post, year)
        if not fecha or fecha < now_co:
            continue

        hour, minute = _extract_time(post)
        fecha = fecha.replace(hour=hour, minute=minute)

        # First meaningful line as title
        lines = [l.strip() for l in post.split("\n") if l.strip() and not l.startswith("BIO:")]
        titulo = lines[0][:200] if lines else "Evento"
        # Clean IG artifacts from title
        titulo = re.sub(r"^\[POST.*?\]\s*", "", titulo)
        titulo = re.sub(r"\[IMAGE_URL:.*?\]\s*", "", titulo)
        titulo = re.sub(r"\[PERMALINK:.*?\]\s*", "", titulo)
        titulo = titulo.strip()
        if not titulo or len(titulo) < 5:
            continue

        descripcion = " ".join(lines[1:3])[:500] if len(lines) > 1 else ""
        es_gratuito = _is_price_free(post)

        events.append({
            "titulo": titulo,
            "fecha_inicio": fecha.isoformat(),
            "fecha_fin": None,
            "descripcion": descripcion,
            "precio": "Entrada libre" if es_gratuito else "",
            "es_gratuito": es_gratuito,
            "imagen_url": None,
            "nombre_lugar": nombre,
            "categoria_principal": _detect_category(post),
            "categorias": [_detect_category(post)],
            "municipio": municipio,
            "barrio": lugar.get("barrio"),
            "fuente": "auto_scraper_instagram",
            "fuente_url": f"https://instagram.com/{ig_handle.lstrip('@')}",
        })

    return events


async def _extract_events_from_ig_with_claude(ig_text: str, lugar: dict) -> list[dict]:
    """Fallback: usa Claude para parsear captions de Instagram cuando el regex no encuentra fechas.
    Solo se invoca si _extract_events_from_ig_text retorna 0 eventos.
    """
    if not settings.anthropic_api_key:
        return []

    now_co = datetime.utcnow() - timedelta(hours=5)
    fecha_hoy = now_co.strftime("%Y-%m-%d")
    nombre = lugar["nombre"]
    municipio = lugar.get("municipio", "medellin")
    ig_handle = lugar.get("instagram_handle", "")

    prompt = f"""Hoy es {fecha_hoy}. Analiza los siguientes posts de Instagram del colectivo/espacio cultural "{nombre}" (municipio: {municipio}).

Extrae TODOS los eventos, actividades culturales, presentaciones, tocadas, conciertos, exposiciones, talleres, foros, charlas, jams, open mics, fiestas, lanzamientos, proyecciones, o cualquier actividad con fecha futura o de hoy.

IMPORTANTE:
- "Este sábado", "mañana", "este viernes" = calcula la fecha real desde hoy {fecha_hoy}
- "Todos los jueves" = próximo jueves desde hoy
- Si un post menciona una actividad cultural con alguna referencia temporal, inclúyelo
- Si ves precios como "$20.000", "20k", "entrada libre", extráelos
- Ignora posts que claramente son solo fotos del pasado sin fecha futura

Para cada evento encontrado, devuelve un JSON array con objetos de este formato exacto:
{{
  "titulo": "nombre del evento (máx 200 chars)",
  "fecha_iso": "YYYY-MM-DDTHH:MM:SS (si no hay hora usa 19:00:00)",
  "descripcion": "breve descripción (máx 300 chars)",
  "es_gratuito": true/false,
  "precio": "precio si se menciona, o null",
  "imagen_url": "URL de imagen si aparece [IMAGE_URL:...], si no null",
  "permalink": "URL del post si aparece [PERMALINK:...], si no null"
}}

Responde ÚNICAMENTE con el JSON array (puede ser [] si no hay eventos futuros). Sin texto adicional.

POSTS:
---
{ig_text[:6000]}
"""

    # Strip very long image URLs to save tokens and prevent JSON truncation
    prompt = re.sub(
        r"\[IMAGE_URL: https?://[^\]]{200,}\]",
        "[IMAGE_URL: (url removed for brevity)]",
        prompt,
    )

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = (settings.anthropic_model or "claude-3-5-haiku-20241022").strip() or "claude-3-5-haiku-20241022"
        response = client.messages.create(
            model=model,
            max_tokens=2500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip() if response.content else "[]"
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
    except Exception as e:
        print(f"  [IG Claude] Error parseando IG con Claude: {e}")
        return []

    events = []
    for item in parsed:
        titulo = (item.get("titulo") or "").strip()[:200]
        if not titulo:
            continue
        fecha_str = item.get("fecha_iso", "")
        try:
            fecha = datetime.fromisoformat(fecha_str)
            if fecha < now_co:
                continue
        except (ValueError, TypeError):
            continue

        es_gratuito = bool(item.get("es_gratuito", False))
        precio_raw = item.get("precio") or ""
        if not precio_raw and es_gratuito:
            precio_raw = "Entrada libre"
        events.append({
            "titulo": titulo,
            "fecha_inicio": fecha.isoformat(),
            "fecha_fin": None,
            "descripcion": (item.get("descripcion") or "")[:500],
            "precio": precio_raw or ("Entrada libre" if es_gratuito else ""),
            "es_gratuito": es_gratuito,
            "imagen_url": item.get("imagen_url"),
            "nombre_lugar": nombre,
            "categoria_principal": _detect_category(titulo + " " + (item.get("descripcion") or "")),
            "categorias": [_detect_category(titulo + " " + (item.get("descripcion") or ""))],
            "municipio": municipio,
            "barrio": lugar.get("barrio"),
            "fuente": "auto_scraper_ig_claude",
            "fuente_url": item.get("permalink") or f"https://instagram.com/{ig_handle.lstrip('@')}",
        })

    if events:
        print(f"  [IG Claude] ✓ {len(events)} evento(s) extraídos por Claude")
    return events


# -- Core: scrape a single lugar -----------------------------------------------

async def _scrape_lugar(lugar: dict) -> dict:
    """Scrape website + Instagram for a single lugar using CODE (no AI)."""
    lugar_id = lugar["id"]
    nombre = lugar["nombre"]
    all_events = []

    # 1. Scrape website (structured HTML extraction)
    sitio = lugar.get("sitio_web")
    if sitio:
        print(f"  [WEB] {sitio}")
        soup = await _fetch_website_soup(sitio)
        if soup:
            events = _extract_events_from_html(soup, lugar, sitio)
            if not events:
                # Fallback: try text-based extraction
                text = soup.get_text(separator="\n", strip=True)
                if text and len(text) > 100:
                    events = _extract_events_from_text(text, lugar, sitio)
            all_events.extend(events)
            if events:
                print(f"    [OK] {len(events)} evento(s) encontrados via codigo")

    # 2. Scrape Instagram
    ig_handle = lugar.get("instagram_handle")
    ig_content = None  # Save raw content for Claude fallback
    if ig_handle:
        print(f"  [IG] {ig_handle}")
        ig_content = await _fetch_instagram_profile(ig_handle)
        if ig_content and len(ig_content) > 100:
            events = _extract_events_from_ig_text(ig_content, lugar)
            if events:
                all_events.extend(events)
                print(f"    [OK] {len(events)} evento(s) de Instagram (regex)")
            else:
                # Fallback: use Claude to parse informal dates ("este sábado", "mañana", etc.)
                print(f"  [IG] Regex no encontró fechas, intentando con Claude...")
                events = await _extract_events_from_ig_with_claude(ig_content, lugar)
                all_events.extend(events)
                if events:
                    print(f"    [OK] {len(events)} evento(s) de Instagram (Claude)")

    # 3. Google search fallback (when IG fails or isn't available)
    if not all_events:
        print(f"  [Google] Buscando eventos en Google para '{nombre}'...")
        google_text = await _search_google_events(nombre, lugar.get("municipio", "medellin"), ig_handle or "")
        if google_text and len(google_text) > 200:
            events = _extract_events_from_text(google_text, lugar, "https://google.com")
            if not events and settings.anthropic_api_key:
                # Use Claude to parse Google results
                events = await _extract_events_from_ig_with_claude(google_text, lugar)
            all_events.extend(events)
            if events:
                print(f"    [OK] {len(events)} evento(s) via Google")

    # 4. Insert events into DB
    stats = {"nuevos": 0, "duplicados": 0, "errores": 0}
    now_co = datetime.utcnow() - timedelta(hours=5)

    for ev in all_events:
        try:
            titulo = ev.get("titulo")
            if not titulo:
                continue

            fecha_str = ev.get("fecha_inicio")
            if not fecha_str:
                continue

            try:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha < now_co:
                    continue
            except (ValueError, TypeError):
                continue

            slug = _slugify(titulo)

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
                "categorias": ev.get("categorias", ["otro"]),
                "categoria_principal": ev.get("categoria_principal", "otro"),
                "municipio": ev.get("municipio", "medellin"),
                "barrio": ev.get("barrio"),
                "nombre_lugar": nombre,
                "descripcion": ev.get("descripcion"),
                "precio": ev.get("precio"),
                "es_gratuito": ev.get("es_gratuito", False),
                "es_recurrente": ev.get("es_recurrente", False),
                "imagen_url": ev.get("imagen_url"),
                "fuente": ev.get("fuente", "auto_scraper_code"),
                "fuente_url": ev.get("fuente_url"),
                "verificado": False,
            }
            supabase.table("eventos").insert(evento_data).execute()
            stats["nuevos"] += 1
            print(f"    [NEW] {titulo[:60]}")

        except Exception as e:
            stats["errores"] += 1
            print(f"    [ERR] Error insertando evento: {e}")

    return stats


# -- Logging -------------------------------------------------------------------

def _log_scraping(fuente: str, registros_nuevos: int, errores: int, detalle: dict, duracion: float = 0):
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
        print(f"  [WARN] Error logging: {e}")


# -- Main entry points ---------------------------------------------------------

async def run_auto_scraper(limit: Optional[int] = None) -> dict:
    """Scrape all active lugares with code-based extraction (NO Claude)."""
    print("\n[SCRAPER] ================================================")
    print("   AUTO-SCRAPER iniciando (Meta API + scrapers + Claude fallback)")
    print("==========================================================")

    query = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    )
    result = query.execute()
    lugares = [
        l for l in result.data
        if l.get("instagram_handle") or l.get("sitio_web")
    ]

    if limit:
        lugares = lugares[:limit]

    total_stats = {"lugares_procesados": 0, "eventos_nuevos": 0, "duplicados": 0, "errores": 0}
    start_time = datetime.utcnow() - timedelta(hours=5)

    for i, lugar in enumerate(lugares):
        print(f"\n[{i+1}/{len(lugares)}] {lugar['nombre']}")
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

            await asyncio.sleep(1)

        except Exception as e:
            total_stats["errores"] += 1
            print(f"  [ERR] Error general: {e}")

    elapsed = ((datetime.utcnow() - timedelta(hours=5)) - start_time).total_seconds()
    total_stats["duracion_segundos"] = round(elapsed, 1)

    print(f"\n[SCRAPER] Completado en {elapsed:.0f}s")
    print(f"   Lugares: {total_stats['lugares_procesados']}")
    print(f"   Eventos nuevos: {total_stats['eventos_nuevos']}")
    print(f"   Duplicados: {total_stats['duplicados']}")
    print(f"   Errores: {total_stats['errores']}")

    return total_stats


async def scrape_single_lugar(lugar_id: str) -> dict:
    """Scrape a single lugar by ID."""
    resp = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    ).eq("id", lugar_id).single().execute()

    if not resp.data:
        return {"error": "Lugar no encontrado"}

    lugar = resp.data
    print(f"\n[SCRAPE] Individual: {lugar['nombre']}")
    stats = await _scrape_lugar(lugar)

    _log_scraping(
        fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "manual"),
        registros_nuevos=stats["nuevos"],
        errores=stats["errores"],
        detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"], "tipo": "manual"},
    )

    return {"lugar": lugar["nombre"], **stats}


async def scrape_zona(municipio: str, limit: int = 20) -> dict:
    """Scrape all spaces in a municipio/zona."""
    print(f"\n[ZONA] Scraping: {municipio} (limit={limit})")

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
            await asyncio.sleep(1)
        except Exception as e:
            total_stats["errores"] += 1
            print(f"    [ERR] {e}")

    _log_scraping(
        fuente=f"zona_{municipio}",
        registros_nuevos=total_stats["eventos_nuevos"],
        errores=total_stats["errores"],
        detalle=total_stats,
    )

    return total_stats


async def enrich_event_images() -> dict:
    """Scan eventos without imagen_url and try to fetch og:image."""
    print("\n[IMAGES] Enriqueciendo imagenes de eventos...")
    result = supabase.table("eventos").select(
        "id,titulo,fuente_url,espacio_id,imagen_url"
    ).is_("imagen_url", "null").limit(100).execute()

    eventos = result.data or []
    print(f"  {len(eventos)} eventos sin imagen")
    updated = 0
    og_cache = {}

    async def _get_og_image(url: str) -> Optional[str]:
        if url in og_cache:
            return og_cache[url]
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=12) as client:
                resp = await client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    tag = soup.find("meta", property="og:image")
                    if tag and tag.get("content"):
                        og_cache[url] = tag["content"]
                        return tag["content"]
        except Exception:
            pass
        og_cache[url] = None
        return None

    for ev in eventos:
        fuente = ev.get("fuente_url")
        if not fuente and ev.get("espacio_id"):
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
            except Exception:
                pass

        await asyncio.sleep(0.5)

    print(f"  [OK] {updated} eventos actualizados con imagen")
    return {"total_sin_imagen": len(eventos), "actualizados": updated}


# -- Alternative agenda sources (code-based) -----------------------------------

AGENDA_SOURCES = [
    {
        "nombre": "Vivir en el Poblado",
        "url": "https://vivirenelpoblado.com/agenda-cultural/",
        "categoria_default": "festival",
        "municipio": "medellin",
    },
    {
        "nombre": "Tu Cultura Medellin",
        "url": "https://tucultura.medellin.gov.co/",
        "categoria_default": "casa_cultura",
        "municipio": "medellin",
    },
]


async def scrape_agenda_sources() -> dict:
    """Scrape independent agenda websites using code-based extraction."""
    print("\n[AGENDA] Scraping fuentes externas (code-based)...")

    now_co = datetime.utcnow() - timedelta(hours=5)
    total = {"fuentes": 0, "eventos_nuevos": 0, "duplicados": 0, "errores": 0}

    for src in AGENDA_SOURCES:
        print(f"\n  [{src['nombre']}] {src['url']}")
        try:
            soup = await _fetch_website_soup(src["url"])
            if not soup:
                continue

            lugar_dummy = {
                "id": None,
                "nombre": src["nombre"],
                "categoria_principal": src["categoria_default"],
                "municipio": src["municipio"],
                "barrio": None,
            }

            events = _extract_events_from_html(soup, lugar_dummy, src["url"])
            if not events:
                text = soup.get_text(separator="\n", strip=True)
                if text:
                    events = _extract_events_from_text(text, lugar_dummy, src["url"])

            total["fuentes"] += 1

            for ev in events:
                try:
                    titulo = ev.get("titulo")
                    if not titulo:
                        continue
                    
                    slug = _slugify(titulo)
                    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
                    if existing.data:
                        total["duplicados"] += 1
                        continue

                    evento_data = {
                        "titulo": titulo,
                        "slug": slug,
                        "fecha_inicio": ev.get("fecha_inicio"),
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
                    print(f"    [NEW] {titulo[:60]}")

                except Exception as e:
                    total["errores"] += 1

            await asyncio.sleep(2)

        except Exception as e:
            total["errores"] += 1
            print(f"  [ERR] {src['nombre']}: {e}")

    print(f"\n[AGENDA] Completado: {total['eventos_nuevos']} nuevos, {total['duplicados']} duplicados")
    return total