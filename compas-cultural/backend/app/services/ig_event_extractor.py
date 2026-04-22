"""
ig_event_extractor.py
=====================
Extractor de eventos de Instagram — CERO tokens de AI.

Recibe el resultado de instagram_pw_scraper.fetch_ig_profile() y extrae
eventos culturales usando únicamente expresiones regulares y lógica de fechas.

Estrategia por caption:
  1. Buscar patrones de fecha española/inglesa (parse_date reutilizado)
  2. Primera línea del caption como título del evento
  3. Detectar keywords de evento (concierto, taller, función, etc.)
  4. Extraer precio/gratuidad
  5. Filtrar solo eventos FUTUROS
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Reutilizamos el parser de fechas de html_event_extractor
from app.services.html_event_extractor import parse_date, MESES

CO_TZ = ZoneInfo("America/Bogota")

# ── Keywords que indican que un caption es un evento ─────────────────────
EVENT_KEYWORDS = re.compile(
    r'\b('
    r'concierto|función|funcion|presentaci[oó]n|lanzamiento|exposici[oó]n|'
    r'muestra|taller|workshop|charla|conversatorio|foro|festival|'
    r'espect[aá]culo|show|noche de|velada|apertura|clausura|'
    r'proyecci[oó]n|premiere|obra|performance|recital|'
    r'fiesta|rumba|baile|danza|teatro|cine|hip.hop|freestyle|'
    r'residencia|encuentro|feria|ma[rn]ifestaci[oó]n|happening'
    r')\b',
    re.I
)

# Palabras que indican que NO es evento (descarte rápido)
NOISE_KEYWORDS = re.compile(
    r'\b(gracias|feliz|cumple|navidad|amor|pa[ií]s|gente|familia|instagram|'
    r'foto|selfie|repost|follow|like|share|dm|info|whatsapp)\b',
    re.I
)

# Detectar entrada libre / gratuito
FREE_RE = re.compile(r'entrada\s+libre|gratis|gratuito|free|sin\s+costo', re.I)
PRICE_RE = re.compile(r'\$\s*[\d.,]+(?:\s*[kK])?|[\d.,]+\s*pesos', re.I)

# Extraer hora del caption
TIME_RE = re.compile(
    r'\b(\d{1,2})[:\.]?(\d{2})?\s*(?:hrs?|horas?)?\s*(a\.?m\.?|p\.?m\.?|am|pm|h)\b'
    r'|a\s+las\s+(\d{1,2})(?:[:\.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)?',
    re.I
)


def _now_co() -> datetime:
    return datetime.now(CO_TZ)


def _extract_hour(text: str) -> tuple[int, int]:
    """Extract hour:minute from any text. Defaults to 19:00."""
    m = TIME_RE.search(text)
    if not m:
        return 19, 0
    g = m.groups()
    # Pattern 1: "8:30pm" or "8pm" or "20h"
    if g[0]:
        h = int(g[0])
        mi = int(g[1]) if g[1] else 0
        mer = (g[2] or "").lower().replace(".", "")
    # Pattern 2: "a las 8:30 pm"
    elif g[3]:
        h = int(g[3])
        mi = int(g[4]) if g[4] else 0
        mer = (g[5] or "").lower().replace(".", "")
    else:
        return 19, 0

    if mer in ("pm", "p") and h < 12:
        h += 12
    elif mer in ("am", "a") and h == 12:
        h = 0
    if not (0 <= h <= 23):
        h = 19
    return h, mi


def _clean_title(line: str) -> str:
    """Remove emojis and extra punctuation from a caption title line."""
    # Remove common emoji ranges
    line = re.sub(r'[\U0001F300-\U0001FFFF\U00002600-\U000027BF]', '', line)
    # Remove hashtags and mentions
    line = re.sub(r'#\S+|@\S+', '', line)
    # Remove URLs
    line = re.sub(r'https?://\S+', '', line)
    # Normalize spaces
    line = re.sub(r'\s+', ' ', line).strip()
    # Strip trailing punctuation
    line = line.strip('.,;:!?-–—')
    return line


def _extract_price(caption: str) -> tuple[str, bool]:
    """Extract price info and is_free flag from caption text."""
    if FREE_RE.search(caption):
        return "Entrada libre", True
    m = PRICE_RE.search(caption)
    if m:
        return m.group(0).strip(), False
    return "Consultar", False


def _caption_to_event(
    caption: str,
    image_url: Optional[str],
    nombre_lugar: str,
    categoria: str,
    municipio: str,
    now: datetime,
) -> Optional[dict]:
    """
    Try to extract a single structured event from an Instagram caption.
    Returns None if no valid future event is found.
    """
    if not caption or len(caption) < 20:
        return None

    # Quick noise filter
    if NOISE_KEYWORDS.search(caption) and not EVENT_KEYWORDS.search(caption):
        return None

    # Must contain either an event keyword OR a clear date pattern
    has_event_kw = bool(EVENT_KEYWORDS.search(caption))

    # Find date
    fecha = parse_date(caption, now.year)
    if not fecha:
        # Try next year if months already passed
        fecha = parse_date(caption, now.year + 1)
    if not fecha:
        if not has_event_kw:
            return None
        # No date but has event keyword → skip (can't insert without date)
        return None

    # Must be in the future
    if fecha.date() < now.date():
        # Try bumping to next year if date already passed
        bumped = fecha.replace(year=now.year + 1)
        if bumped.date() >= now.date():
            fecha = bumped
        else:
            return None

    # Apply extracted hour
    h, mi = _extract_hour(caption)
    try:
        fecha = fecha.replace(hour=h, minute=mi, second=0, microsecond=0)
    except Exception:
        pass

    # Build title: use first non-empty line (cleaned)
    lines = [ln.strip() for ln in caption.split("\n") if ln.strip()]
    title_raw = lines[0] if lines else caption[:80]
    title = _clean_title(title_raw)

    # If title is empty or too short, use nombre_lugar + event keyword match
    if len(title) < 4:
        kw_m = EVENT_KEYWORDS.search(caption)
        title = f"{kw_m.group(0).capitalize()} en {nombre_lugar}" if kw_m else nombre_lugar

    # Title length guard
    title = title[:120]

    # Description: next 2 meaningful lines
    desc_lines = [_clean_title(ln) for ln in lines[1:4] if len(ln.strip()) > 10]
    desc = " | ".join(desc_lines)[:400] or None

    # Price
    precio, es_gratuito = _extract_price(caption)

    return {
        "titulo": title,
        "categoria_principal": categoria,
        "categorias": [categoria],
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": None,
        "descripcion": desc,
        "precio": precio,
        "es_gratuito": es_gratuito,
        "es_recurrente": False,
        "imagen_url": image_url,
        "_fuente": "instagram",
    }


def extract_events_from_ig_profile(
    profile: dict,
    nombre_lugar: str,
    categoria: str,
    municipio: str,
) -> list[dict]:
    """
    Extract structured events from an Instagram profile dict
    (as returned by instagram_pw_scraper.fetch_ig_profile).

    Returns a list of event dicts (may be empty).
    Zero AI tokens.
    """
    now = _now_co()
    events: list[dict] = []
    seen_titles: set[str] = set()

    captions: list[str] = profile.get("captions") or []
    image_urls: list[str] = profile.get("image_urls") or []

    for i, caption in enumerate(captions):
        img = image_urls[i] if i < len(image_urls) else None
        ev = _caption_to_event(caption, img, nombre_lugar, categoria, municipio, now)
        if ev and ev["titulo"].lower() not in seen_titles:
            seen_titles.add(ev["titulo"].lower())
            events.append(ev)

    return events
