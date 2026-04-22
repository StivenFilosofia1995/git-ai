"""
html_event_extractor.py
=======================
Code-first event extractor — ZERO AI tokens consumed.

Strategy (in order):
  1. JSON-LD  schema.org/Event  → best quality, modern sites
  2. Site-specific CSS parsers  → reliable for known cultural sites
  3. <time> tag extraction      → semantic HTML
  4. Microdata itemtype=Event   → alternative schema markup
  5. Generic heading + date     → fallback for any site

Supports Spanish date patterns:
  "21 de abril de 2026", "21 ABRIL - 8:00 P.M.",
  "Martes 22 de abril", ISO "2026-04-21T20:00:00"
"""
import json
import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

CO_TZ = ZoneInfo("America/Bogota")

# ── Resolve relative image URLs to absolute ───────────────────────────────
def _to_absolute(base_url: str, src: Optional[str]) -> Optional[str]:
    """Convert a relative image src to an absolute URL using the page's base URL."""
    if not src:
        return None
    src = src.strip()
    if not src or src.startswith("data:"):
        return None
    if src.startswith("http://") or src.startswith("https://"):
        return src
    from urllib.parse import urljoin
    return urljoin(base_url, src)


# ── Resolve relative image URLs to absolute ───────────────────────────────
def _to_absolute(base_url: str, src: Optional[str]) -> Optional[str]:
    """Convert a relative image src to an absolute URL using the page's base URL."""
    if not src:
        return None
    src = src.strip()
    if not src or src.startswith("data:"):
        return None
    if src.startswith("http://") or src.startswith("https://"):
        return src
    from urllib.parse import urljoin
    return urljoin(base_url, src)


# ── Spanish / English month names ─────────────────────────────────────────
MESES: dict[str, int] = {
    "enero": 1, "ene": 1, "january": 1, "jan": 1,
    "febrero": 2, "feb": 2, "february": 2,
    "marzo": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6, "june": 6,
    "julio": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "septiembre": 9, "sep": 9, "sept": 9, "september": 9,
    "octubre": 10, "oct": 10, "october": 10,
    "noviembre": 11, "nov": 11, "november": 11,
    "diciembre": 12, "dic": 12, "december": 12, "dec": 12,
}

_DATE_RE = re.compile(
    r'(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)[\s,]*'
    r'(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?'
    r'|(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?'
    r'|(\d{1,2})\s+(\w+)\s+(\d{4})'
    r'|(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2}))?',
    re.I
)
_TIME_RE = re.compile(r'(\d{1,2})[:\.](\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm)?', re.I)


# ── Date helpers ──────────────────────────────────────────────────────────
def _parse_time_str(text: str) -> tuple[int, int, bool]:
    m = _TIME_RE.search(text)
    if not m:
        return 0, 0, False
    h, mi = int(m.group(1)), int(m.group(2))
    mer = (m.group(3) or "").lower().replace(".", "")
    if mer in ("pm", "p") and h < 12:
        h += 12
    elif mer in ("am", "a") and h == 12:
        h = 0
    if h > 23:
        return 0, 0, False
    return h, mi, True


def parse_date(text: str, year: int = 0) -> Optional[datetime]:
    """Parse a Spanish/English date string into a timezone-aware datetime."""
    if not text:
        return None
    tl = text.lower().strip()
    yr = year or datetime.now(CO_TZ).year

    for m in _DATE_RE.finditer(tl):
        g = m.groups()
        # Pattern 1: weekday + "21 de abril de 2026"
        if g[0] and g[1]:
            day, month_str = int(g[0]), g[1]
            month = MESES.get(month_str, 0)
            if g[2]:
                yr = int(g[2])
        # Pattern 2: "21 de abril de 2026" (no weekday)
        elif g[3] and g[4]:
            day, month_str = int(g[3]), g[4]
            month = MESES.get(month_str, 0)
            if g[5]:
                yr = int(g[5])
        # Pattern 3: "21 abril 2026"
        elif g[6] and g[7] and g[8]:
            day, month_str, yr = int(g[6]), g[7], int(g[8])
            month = MESES.get(month_str, 0)
        # Pattern 4: ISO "2026-04-21"
        elif g[9] and g[10] and g[11]:
            try:
                yr2, mo2, da2 = int(g[9]), int(g[10]), int(g[11])
                h = int(g[12]) if g[12] else 0
                mi = int(g[13]) if g[13] else 0
                return datetime(yr2, mo2, da2, h, mi, tzinfo=CO_TZ)
            except ValueError:
                continue
        else:
            continue

        if not month or not (1 <= day <= 31):
            continue
        h, mi, _ = _parse_time_str(text)
        try:
            return datetime(yr, month, day, h, mi, tzinfo=CO_TZ)
        except ValueError:
            continue

    return None


def _now() -> datetime:
    return datetime.now(CO_TZ)


def _make_event(
    titulo: str,
    fecha: datetime,
    categoria: str,
    nombre_lugar: str,
    source: str,
    precio: str = "Consultar",
    gratuito: bool = False,
    desc: Optional[str] = None,
    img: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict:
    return {
        "titulo": titulo.strip()[:200],
        "categoria_principal": categoria,
        "categorias": [categoria],
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": fecha_fin,
        "descripcion": (desc or "")[:400] or None,
        "nombre_lugar": nombre_lugar,
        "precio": precio,
        "es_gratuito": gratuito,
        "es_recurrente": False,
        "imagen_url": img,
        "_source": source,
    }


# ── 1. JSON-LD schema.org/Event ───────────────────────────────────────────
_EVENT_TYPES = {
    "Event", "TheaterEvent", "MusicEvent", "VisualArtsEvent",
    "SocialEvent", "FoodEvent", "ExhibitionEvent", "Festival",
    "DanceEvent", "ComedyEvent", "ScreeningEvent", "LiteraryEvent",
    "SaleEvent", "ChildrensEvent", "CourseInstance",
}


def _extract_jsonld(soup: BeautifulSoup, nombre_lugar: str, categoria: str, now: datetime, base_url: str = "") -> list[dict]:
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            if not script.string:
                continue
            raw = json.loads(script.string)
            items = raw if isinstance(raw, list) else [raw]
            # Flatten @graph
            expanded = []
            for item in items:
                if isinstance(item, dict) and item.get("@graph"):
                    expanded.extend(item["@graph"])
                else:
                    expanded.append(item)

            for item in expanded:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") not in _EVENT_TYPES:
                    continue
                name = (item.get("name") or "").strip()
                if not name or len(name) < 3:
                    continue
                start = item.get("startDate") or item.get("doorTime") or ""
                fecha = parse_date(str(start), now.year)
                if not fecha or fecha.date() < now.date():
                    continue
                end = item.get("endDate")
                loc = item.get("location", {})
                loc_name = (loc.get("name") if isinstance(loc, dict) else None) or nombre_lugar
                img = item.get("image")
                if isinstance(img, list):
                    img = img[0] if img else None
                if isinstance(img, dict):
                    img = img.get("url")
                img = _to_absolute(base_url, img) if isinstance(img, str) else img
                offers = item.get("offers", {})
                precio, gratuito = "Consultar", False
                for o in ([offers] if isinstance(offers, dict) else offers if isinstance(offers, list) else []):
                    p = str(o.get("price", ""))
                    if p in ("0", "0.0", ""):
                        precio, gratuito = "Entrada libre", True
                    elif p:
                        precio = f"${p}"
                    break
                events.append(_make_event(
                    name, fecha, categoria, loc_name, "jsonld",
                    precio, gratuito,
                    desc=item.get("description", "")[:400],
                    img=img, fecha_fin=str(end) if end else None,
                ))
        except Exception:
            continue
    return events


# ── 2. <time> datetime attribute ──────────────────────────────────────────
def _extract_time_tags(soup: BeautifulSoup, nombre_lugar: str, categoria: str, now: datetime, base_url: str = "") -> list[dict]:
    events = []
    for tag in soup.find_all("time", attrs={"datetime": True}):
        dt = tag.get("datetime", "")
        fecha = parse_date(str(dt), now.year)
        if not fecha or fecha.date() < now.date():
            continue
        # Walk up to find a heading or link
        title = None
        node = tag.parent
        for _ in range(7):
            if not node:
                break
            for el in node.find_all(["h2", "h3", "h4", "h5"]):
                t = el.get_text(strip=True)
                if t and len(t) > 5:
                    title = t
                    break
            if title:
                break
            # Also check anchor
            a = node.find("a")
            if a:
                t = a.get_text(strip=True)
                if t and len(t) > 5:
                    title = t
                    break
            node = node.parent
        if not title or len(title) < 4:
            continue
        img = None
        if node:
            im = node.find("img")
            if im:
                img = _to_absolute(base_url, im.get("src") or im.get("data-src") or im.get("data-lazy-src"))
        events.append(_make_event(title, fecha, categoria, nombre_lugar, "time_tag", img=img))
    return events


# ── 3. Microdata schema.org ───────────────────────────────────────────────
def _extract_microdata(soup: BeautifulSoup, nombre_lugar: str, categoria: str, now: datetime, base_url: str = "") -> list[dict]:
    events = []
    for el in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/(Event|MusicEvent|TheaterEvent)", re.I)}):
        name_el = el.find(attrs={"itemprop": "name"})
        date_el = el.find(attrs={"itemprop": re.compile(r"startDate|doorTime")})
        if not name_el or not date_el:
            continue
        name = name_el.get_text(strip=True)
        dt = date_el.get("content", "") or date_el.get("datetime", "") or date_el.get_text(strip=True)
        fecha = parse_date(str(dt), now.year)
        if not fecha or fecha.date() < now.date() or not name:
            continue
        img_el = el.find(attrs={"itemprop": "image"})
        img_raw = (img_el.get("src") or img_el.get("content")) if img_el else None
        img = _to_absolute(base_url, img_raw)
        events.append(_make_event(name, fecha, categoria, nombre_lugar, "microdata", img=img))
    return events


# ── 4. Site-specific parsers ──────────────────────────────────────────────
def _parse_pablo_tobon(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """teatropablotobon.com — div.card structure: weekday | date | time | cat | price | Title."""
    events = []
    # Each event is a div.card (12 cards = 12 events)
    cards = soup.find_all("div", class_="card")
    for card in cards:
        # Must have a link to /evento/ to be confirmed as event
        link = card.find("a", href=re.compile(r"/evento/"))
        if not link:
            continue
        # Title: last heading inside card
        heading = card.find(["h2", "h3", "h4", "h5"])
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title or len(title) < 4:
            continue
        # Date: full card text has "21 de abril de 2026"
        card_text = card.get_text(" ", strip=True)
        fecha = parse_date(card_text, now.year)
        if not fecha or fecha.date() < now.date():
            continue
        # Price from card text
        ct = card_text.lower()
        if "libre" in ct:
            precio, gratuito = "Entrada libre", True
        elif "voluntario" in ct:
            precio, gratuito = "Aporte voluntario", True
        elif "costo" in ct:
            precio, gratuito = "Entrada con costo", False
        else:
            precio, gratuito = "Consultar", False
        # Category from card text
        cat = "teatro"
        if any(w in ct for w in ["música", "concierto", "music"]):
            cat = "musica_en_vivo"
        elif "danza" in ct or "ballet" in ct:
            cat = "danza"
        elif "circo" in ct:
            cat = "otro"
        # Image
        img_tag = card.find("img")
        img_url = _to_absolute("https://www.teatropablotobon.com", (img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")) if img_tag else None)
        events.append(_make_event(title, fecha, cat, "Teatro Pablo Tobón Uribe",
                                  "pablo_tobon_parser", precio, gratuito, img=img_url))
    return events


def _parse_piloto(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """bibliotecapiloto.gov.co/agenda — day numbers + month text + event title."""
    events = []
    year = now.year
    body = soup.find("main") or soup.find(id=re.compile(r"main|content|agenda", re.I)) or soup.body
    if not body:
        return events
    # Strategy: find standalone day numbers (1-31) then look for adjacent month
    for el in body.find_all(string=re.compile(r'^\s*\d{1,2}\s*$')):
        try:
            day = int(el.strip())
        except ValueError:
            continue
        if not (1 <= day <= 31):
            continue
        parent = el.parent
        if not parent:
            continue
        container = parent.parent or parent
        full_text = container.get_text(" ", strip=True)
        # Find month in surrounding text
        month_m = re.search(r'\b(' + '|'.join(MESES.keys()) + r')\b', full_text, re.I)
        if not month_m:
            continue
        month = MESES.get(month_m.group(1).lower(), 0)
        if not month:
            continue
        h, mi = _parse_time_str(full_text)
        try:
            fecha = datetime(year, month, day, h, mi, tzinfo=CO_TZ)
        except ValueError:
            continue
        if fecha.date() < now.date():
            continue
        # Title: heading inside container
        heading = container.find(["h2", "h3", "h4", "strong", "b"])
        title = heading.get_text(strip=True) if heading else None
        if not title or len(title) < 5:
            # Build from non-date text lines
            lines = [ln.strip() for ln in full_text.split('\n')
                     if len(ln.strip()) > 8
                     and not re.match(r'^\d{1,2}$', ln.strip())
                     and not re.match(r'^(enero|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)', ln.strip(), re.I)]
            title = lines[0] if lines else None
        if not title or len(title) < 5:
            continue
        sede_m = re.search(r'(sede\s+\w+|filial\s+\w+|biblioteca\s+\w+)', full_text, re.I)
        desc = sede_m.group(0) if sede_m else None
        events.append(_make_event(title, fecha, "casa_cultura", "Biblioteca Pública Piloto",
                                  "piloto_parser", "Entrada libre", True, desc=desc))
    return events[:30]


def _parse_comfenalco(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """comfenalcoantioquia.com.co — extract event titles from links."""
    events = []
    year = now.year
    seen = set()
    links = soup.find_all("a", href=re.compile(r"eventos.contenidos|/\d{4}/\w+/", re.I))
    if not links:
        # Fallback: links inside event section container
        section = soup.find(id=re.compile(r"event|program|plan|agenda", re.I))
        if section:
            links = section.find_all("a", href=True)
    for link in links:
        title = link.get_text(strip=True)
        if not title or title in seen or len(title) < 5 or len(title) > 200:
            continue
        seen.add(title)
        # Date: scan up container
        fecha = None
        node = link.parent
        for _ in range(5):
            if not node:
                break
            text = node.get_text(" ")
            fecha = parse_date(text, year)
            if fecha:
                break
            node = node.parent
        if not fecha:
            # Try URL: /2026/abril/nombre+del+evento
            href = link.get("href", "")
            fecha = parse_date(href.replace("+", " ").replace("-", " "), year)
        if not fecha or fecha.date() < now.date():
            # Sin fecha parseable → descartar. No inventamos.
            continue
        # Image
        img_tag = link.find_previous("img") or (link.parent.find("img") if link.parent else None)
        img_url = _to_absolute("https://www.comfenalcoantioquia.com.co", (img_tag.get("src") or img_tag.get("data-src")) if img_tag else None)
        events.append(_make_event(title, fecha, "centro_cultural", "Comfenalco Antioquia",
                                  "comfenalco_parser", "Consultar", False, img=img_url))
    return events[:25]


# Day-of-week names to skip as titles in Spanish pages
_DAY_NAMES = {"lunes", "martes", "miércoles", "miercoles", "jueves",
              "viernes", "sábado", "sabado", "domingo"}

# Regex to strip "DayName DD de Month HH:MM am/pm" prefix from text
_DAY_TIME_PREFIX_RE = re.compile(
    r'^(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+'
    r'\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
    r'septiembre|octubre|noviembre|diciembre)\s*(?:de\s+\d{4})?\s*'
    r'(?:\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?))?\s*',
    re.IGNORECASE
)


def _parse_matacandelas(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """matacandelas.com — text blocks: 'Viernes 10 de abril 8:00 p.m. TITLE De: author...' """
    events = []
    year = now.year
    seen_titles: set[str] = set()
    for section in soup.find_all(["section", "article", "div", "li", "p"]):
        # Skip containers too big (layout elements) or too small
        direct_text = section.get_text(" ", strip=True)
        if len(direct_text) < 20 or len(direct_text) > 2000:
            continue
        fecha = parse_date(direct_text, year)
        if not fecha or fecha.date() < now.date():
            continue
        # Strip date+time prefix → remaining text starts with the actual title
        remaining = _DAY_TIME_PREFIX_RE.sub("", direct_text).strip()
        if not remaining or len(remaining) < 5:
            continue
        # Title = text up to first " De:" or " Valor:" or " Lugar:"
        title = re.split(r'\s+(?:De:|Valor:|Lugar:|Artistas:|Dirección:)', remaining, maxsplit=1)[0].strip()
        # Skip day-name-only headings and pure metadata
        if not title or title.lower() in _DAY_NAMES or len(title) < 5:
            continue
        # Deduplicate
        key = title.lower()[:60]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        img = section.find("img")
        img_url = None
        if img:
            src = img.get("src") or img.get("data-src") or ""
            img_url = src if src.startswith("http") else f"https://www.matacandelas.com/{src.lstrip('/')}"
        events.append(_make_event(title, fecha, "teatro", "Teatro Matacandelas",
                                  "matacandelas_parser", img=img_url))
    return events[:20]


def _parse_perpetuo_socorro(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """elperpetuosocorro.org — events in sections/articles."""
    events = []
    year = now.year
    for el in soup.find_all(["article", "section", "div", "li"]):
        text = el.get_text(" ", strip=True)
        if len(text) < 20 or len(text) > 2000:
            continue
        if not _DATE_RE.search(text.lower()):
            continue
        fecha = parse_date(text, year)
        if not fecha or fecha.date() < now.date():
            continue
        heading = el.find(["h2", "h3", "h4", "a", "strong"])
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        events.append(_make_event(title, fecha, "teatro", "Teatro El Perpetuo Socorro",
                                  "perpetuo_parser", "Consultar", False))
    return events[:15]


def _parse_comfama(soup: BeautifulSoup, now: datetime) -> list[dict]:
    """comfama.com — event cards."""
    events = []
    year = now.year
    for card in soup.find_all(class_=re.compile(r"card|evento|item|activity", re.I)):
        text = card.get_text(" ", strip=True)
        if len(text) < 20:
            continue
        fecha = parse_date(text, year)
        if not fecha or fecha.date() < now.date():
            continue
        heading = card.find(["h2", "h3", "h4", "a"])
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        img_tag = card.find("img")
        img_url = _to_absolute("https://comfama.com", (img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")) if img_tag else None)
        events.append(_make_event(title, fecha, "centro_cultural", "Comfama",
                                  "comfama_parser", "Consultar", False, img=img_url))
    return events[:20]


# ── 5. Generic heading + date fallback ────────────────────────────────────
def _extract_generic(soup: BeautifulSoup, nombre_lugar: str, categoria: str, now: datetime, base_url: str = "") -> list[dict]:
    """Generic: find small containers that have BOTH a heading AND a date."""
    events = []
    year = now.year
    seen_titles: set[str] = set()

    for el in soup.find_all(["article", "li", "div", "section"], limit=300):
        children = list(el.children)
        if len(children) > 40:  # skip layout wrappers
            continue
        text = el.get_text(" ", strip=True)
        if len(text) < 15 or len(text) > 1200:
            continue
        if not _DATE_RE.search(text.lower()):
            continue
        fecha = parse_date(text, year)
        if not fecha or fecha.date() < now.date():
            continue
        heading = el.find(["h2", "h3", "h4"])
        if not heading:
            heading = el.find("a")
        if not heading:
            continue
        title = heading.get_text(strip=True)
        if not title or len(title) < 5 or len(title) > 200:
            continue
        tkey = title.lower()[:60]
        if tkey in seen_titles:
            continue
        seen_titles.add(tkey)
        img = el.find("img")
        img_raw = (img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")) if img else None
        img_url = _to_absolute(base_url, img_raw)
        events.append(_make_event(title, fecha, categoria, nombre_lugar, "generic", img=img_url))

    return events[:20]


# ── Dedup ─────────────────────────────────────────────────────────────────
def _dedup(events: list[dict]) -> list[dict]:
    seen, result = set(), []
    for ev in events:
        key = (ev["titulo"].lower()[:60], (ev["fecha_inicio"] or "")[:10])
        if key not in seen:
            seen.add(key)
            result.append(ev)
    return result


# ── Main entry point ──────────────────────────────────────────────────────
def extract_events_code(
    html: str,
    url: str,
    nombre_lugar: str,
    categoria: str,
    municipio: str,
) -> list[dict]:
    """
    Extract cultural events from raw HTML using pure code (zero AI tokens).
    Returns list of event dicts compatible with auto_scraper format.
    """
    if not html or len(html) < 100:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    now = _now()

    # 1. JSON-LD (highest quality — works for most modern cultural sites)
    events = _extract_jsonld(soup, nombre_lugar, categoria, now, url)
    if events:
        print(f"    📐 JSON-LD: {len(events)} evento(s)")
        return _dedup(events)

    # 2. Microdata schema.org
    events = _extract_microdata(soup, nombre_lugar, categoria, now, url)
    if events:
        print(f"    📐 Microdata: {len(events)} evento(s)")
        return _dedup(events)

    # 3. Site-specific parsers
    if "teatropablotobon.com" in url:
        events = _parse_pablo_tobon(soup, now)
    elif "bibliotecapiloto.gov.co" in url:
        events = _parse_piloto(soup, now)
    elif "comfenalcoantioquia.com.co" in url:
        events = _parse_comfenalco(soup, now)
    elif "matacandelas.com" in url:
        events = _parse_matacandelas(soup, now)
    elif "elperpetuosocorro.org" in url:
        events = _parse_perpetuo_socorro(soup, now)
    elif "comfama.com" in url:
        events = _parse_comfama(soup, now)
    if events:
        print(f"    🎯 Parser específico: {len(events)} evento(s)")
        return _dedup(events)

    # 4. <time> datetime tags
    events = _extract_time_tags(soup, nombre_lugar, categoria, now, url)
    if events:
        print(f"    🕐 <time> tags: {len(events)} evento(s)")
        return _dedup(events)

    # 5. Generic heading + date
    events = _extract_generic(soup, nombre_lugar, categoria, now, url)
    if events:
        print(f"    🔍 Genérico: {len(events)} evento(s)")
        return _dedup(events)

    return []
