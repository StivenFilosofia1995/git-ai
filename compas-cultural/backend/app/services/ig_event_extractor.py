"""
ig_event_extractor.py
=====================
Extractor de eventos de Instagram — CERO tokens de AI.

Recibe el resultado de instagram_pw_scraper.fetch_ig_profile() y extrae
eventos culturales usando únicamente expresiones regulares y lógica de fechas.

Estrategia por caption:
  1. Buscar fecha explícita (parse_date)
  2. Buscar fecha relativa ("este sábado", "mañana", "hoy", "el viernes")
  3. Buscar día-de-semana + hora ("viernes 8pm", "sáb 25 | 8PM")
  4. Detectar keywords de evento (concierto, taller, función, etc.)
  5. Extraer precio/gratuidad
  6. Filtrar solo eventos FUTUROS (o próximos 60 días)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.services.html_event_extractor import parse_date, MESES

CO_TZ = ZoneInfo("America/Bogota")

# ── Días de semana en español ──────────────────────────────────────────────
DIAS: dict[str, int] = {
    "lunes": 0, "lun": 0,
    "martes": 1, "mar": 1,
    "miércoles": 2, "miercoles": 2, "mié": 2, "mie": 2,
    "jueves": 3, "jue": 3,
    "viernes": 4, "vie": 4,
    "sábado": 5, "sabado": 5, "sáb": 5, "sab": 5,
    "domingo": 6, "dom": 6,
}

# ── Keywords que indican que un caption es un evento ─────────────────────
EVENT_KEYWORDS = re.compile(
    r'\b('
    r'concierto|función|funcion|presentaci[oó]n|lanzamiento|exposici[oó]n|'
    r'muestra|taller|workshop|charla|conversatorio|foro|festival|'
    r'espect[aá]culo|show|noche de|velada|apertura|clausura|'
    r'proyecci[oó]n|premiere|obra|performance|recital|'
    r'fiesta|rumba|baile|danza|teatro|cine|hip.?hop|freestyle|'
    r'residencia|encuentro|feria|manifestaci[oó]n|happening|'
    r'open\s*mic|jam|ciclo|temporada|gira|tour|convocat|'
    r'invita[mn]|te\s+espera|te\s+invita|los\s+espera|'
    r'gratis|entrada\s+libre|boletería|boletas|taquilla|'
    r'inauguraci[oó]n|clausura|vernissage|finissage|'
    r'slam|spoken\s*word|breakdance|grafiti|mural|'
    r'cumbia|vallenato|salsa|reggaeton|electr[oó]nica|'
    r'circo|malabares|acrobacia|magia|zancos'
    r')\b',
    re.I
)

# Descarte rápido — posts que claramente no son eventos
NOISE_KEYWORDS = re.compile(
    r'\b(gracias\s+por|feliz\s+cumplea|navidad|día\s+de\s+la\s+madre|'
    r'selfie|repost|follow|#repost|patrocin|sponsor)\b',
    re.I
)

# Entrada libre / gratuito
FREE_RE = re.compile(r'entrada\s+libre|gratis|gratuito|free|sin\s+costo|sin\s+cober', re.I)
PRICE_RE = re.compile(r'\$\s*[\d.,]+(?:\s*[kK])?|[\d.,]+\s*pesos', re.I)

# Hora del caption
TIME_RE = re.compile(
    r'\b(\d{1,2})[:\.](\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm|h)?\b'
    r'|\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?|am|pm|h)\b'
    r'|a\s+las\s+(\d{1,2})(?:[:\.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)?',
    re.I
)

# Fecha con día-de-semana + número: "Sáb 25", "viernes 7 de mayo", "sáb 25 | 8PM"
DAYNUM_RE = re.compile(
    r'\b(lunes?|lun|martes?|mar|mi[eé]rcoles?|mi[eé]?|jueves?|jue|viernes?|vie|s[aá]bados?|s[aá]b|domingos?|dom)\s+'
    r'(\d{1,2})'
    r'(?:\s+(?:de\s+)?(' + '|'.join(MESES.keys()) + r'))?',
    re.I
)

# Fechas cortas: "25/04", "25-04", "25.04"
SHORT_DATE_RE = re.compile(r'\b(\d{1,2})[/\-\.](\d{1,2})(?:[/\-\.](\d{2,4}))?\b')

# Fechas relativas
RELATIVE_RE = re.compile(
    r'\b(hoy|mañana|ma[nñ]ana|pasado\s+ma[nñ]ana|'
    r'este\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)|'
    r'el\s+(?:pr[oó]ximo\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)|'
    r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+(?:pr[oó]ximo|que\s+viene))\b',
    re.I
)


def _now_co() -> datetime:
    return datetime.now(CO_TZ)


def _next_weekday(now: datetime, target_weekday: int) -> datetime:
    """Return next occurrence of target_weekday (0=Mon, 6=Sun) from now."""
    days_ahead = target_weekday - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return now + timedelta(days=days_ahead)


def _resolve_relative_date(text: str, now: datetime) -> Optional[datetime]:
    """Parse relative date references like 'este sábado', 'mañana', 'el viernes'."""
    m = RELATIVE_RE.search(text)
    if not m:
        return None
    token = m.group(0).lower().strip()
    if "hoy" in token:
        return now
    if "mañana" in token or "manana" in token:
        return now + timedelta(days=1)
    if "pasado" in token:
        return now + timedelta(days=2)
    # Find the day name in the token
    for name, idx in DIAS.items():
        if name in token:
            return _next_weekday(now, idx)
    return None


def _resolve_daynum_date(text: str, now: datetime) -> Optional[datetime]:
    """Parse 'Sáb 25', 'Sab 25', 'viernes 7 de mayo', 'Vie 25 | 8PM', etc."""
    m = DAYNUM_RE.search(text)
    if not m:
        return None
    raw_day = m.group(1).lower().rstrip('s')  # strip plural 's' (sabados→sabado)
    day_num = int(m.group(2))
    month_name = (m.group(3) or "").lower()

    # Find weekday index: exact match first, then prefix match
    wd = DIAS.get(raw_day)
    if wd is None:
        for key, idx in DIAS.items():
            if raw_day.startswith(key) or key.startswith(raw_day[:3]):
                wd = idx
                break

    month = MESES.get(month_name) if month_name else None
    year = now.year

    if month:
        try:
            dt = datetime(year, month, day_num, 19, 0, tzinfo=CO_TZ)
            if dt.date() < now.date():
                dt = dt.replace(year=year + 1)
            return dt
        except ValueError:
            pass

    # No month — find next occurrence of that day number within 14 days
    for delta in range(0, 14):
        d = now + timedelta(days=delta)
        if d.day == day_num:
            return d.replace(hour=19, minute=0, second=0, microsecond=0, tzinfo=CO_TZ)

    # Fallback: next occurrence of that weekday
    if wd is not None:
        return _next_weekday(now, wd).replace(hour=19, minute=0, second=0, microsecond=0)
    return None


def _resolve_short_date(text: str, now: datetime) -> Optional[datetime]:
    """Parse '25/04', '25-04-2026', '7.5' style dates."""
    for m in SHORT_DATE_RE.finditer(text):
        try:
            d, mo = int(m.group(1)), int(m.group(2))
            y_raw = m.group(3)
            if y_raw:
                y = int(y_raw)
                if y < 100:
                    y += 2000
            else:
                y = now.year
            # Validate ranges
            if not (1 <= d <= 31 and 1 <= mo <= 12):
                continue
            dt = datetime(y, mo, d, 19, 0, tzinfo=CO_TZ)
            if dt.date() < now.date():
                dt = dt.replace(year=y + 1)
            if (dt - now).days <= 180:  # within 6 months
                return dt
        except (ValueError, OverflowError):
            continue
    return None


def _extract_hour(text: str) -> tuple[int, int]:
    """Extract hour:minute from any text. Defaults to 19:00."""
    m = TIME_RE.search(text)
    if not m:
        return 19, 0
    g = m.groups()
    # "8:30pm" or "8:30"
    if g[0] and g[1]:
        h, mi, mer = int(g[0]), int(g[1]), (g[2] or "").lower().replace(".", "")
    # "8pm" or "8h"
    elif g[3] and g[4]:
        h, mi, mer = int(g[3]), 0, g[4].lower().replace(".", "")
    # "a las 8:30pm"
    elif g[5]:
        h, mi, mer = int(g[5]), int(g[6]) if g[6] else 0, (g[7] or "").lower().replace(".", "")
    else:
        return 19, 0

    if mer in ("pm", "p") and h < 12:
        h += 12
    elif mer in ("am", "a") and h == 12:
        h = 0
    elif not mer and 1 <= h <= 11:
        h += 12  # No meridiem: cultural events are almost always evening
    if not (0 <= h <= 23):
        h = 19
    return h, mi


def _clean_title(line: str) -> str:
    """Remove emojis and extra punctuation from a caption title line."""
    line = re.sub(r'[\U0001F300-\U0001FFFF\U00002600-\U000027BF\u2300-\u23FF]', '', line)
    line = re.sub(r'#\S+|@\S+', '', line)
    line = re.sub(r'https?://\S+', '', line)
    line = re.sub(r'\s+', ' ', line).strip()
    line = line.strip('.,;:!?-–—◆▸▹►▻▼▽△▲◀▶★☆✦✧✨✩✪✫✬✭✮✯✰❋●○◉◎◌◍')
    return line.strip()


def _extract_price(caption: str) -> tuple[str, bool]:
    """Extract price info and is_free flag from caption text."""
    if FREE_RE.search(caption):
        return "Entrada libre", True
    m = PRICE_RE.search(caption)
    if m:
        return m.group(0).strip(), False
    return "Consultar", False


def _find_date(caption: str, now: datetime) -> Optional[datetime]:
    """Try all date resolution strategies on a caption."""
    # 1. parse_date (full Spanish date patterns)
    fecha = parse_date(caption, now.year)
    if fecha:
        if fecha.date() < now.date():
            bumped = fecha.replace(year=now.year + 1)
            if bumped.date() >= now.date():
                return bumped
        return fecha

    # 2. Relative date
    fecha = _resolve_relative_date(caption, now)
    if fecha and fecha.date() >= now.date():
        return fecha

    # 3. Day + number (Sáb 25)
    fecha = _resolve_daynum_date(caption, now)
    if fecha and fecha.date() >= now.date():
        return fecha

    # 4. Short date 25/04
    fecha = _resolve_short_date(caption, now)
    if fecha and fecha.date() >= now.date():
        return fecha

    # 5. Try next year for explicit dates already passed
    fecha = parse_date(caption, now.year + 1)
    if fecha and fecha.date() >= now.date():
        return fecha

    return None


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
    Returns None if caption is clearly not an event.
    """
    if not caption or len(caption) < 15:
        return None

    # Hard noise filter
    if NOISE_KEYWORDS.search(caption):
        return None

    has_event_kw = bool(EVENT_KEYWORDS.search(caption))
    fecha = _find_date(caption, now)

    # Need at least: (event keyword) OR (explicit date)
    if not fecha and not has_event_kw:
        return None

    # If there's a date but no keyword, still include (date alone is strong signal for IG posts)
    # If there's a keyword but no date, skip (can't insert without date)
    if not fecha:
        return None

    # Apply extracted hour
    h, mi = _extract_hour(caption)
    try:
        fecha = fecha.replace(hour=h, minute=mi, second=0, microsecond=0)
    except Exception:
        pass

    # Build title: first non-empty line (cleaned)
    lines = [ln.strip() for ln in caption.split("\n") if ln.strip()]
    title_raw = lines[0] if lines else caption[:80]
    title = _clean_title(title_raw)

    if len(title) < 4:
        kw_m = EVENT_KEYWORDS.search(caption)
        title = f"{kw_m.group(0).capitalize()} en {nombre_lugar}" if kw_m else nombre_lugar

    title = title[:120]

    # Description: next meaningful lines
    desc_lines = [_clean_title(ln) for ln in lines[1:4] if len(ln.strip()) > 10]
    desc = " | ".join(desc_lines)[:400] or None

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
    permalink_urls: list[str] = profile.get("permalink_urls") or []

    for i, caption in enumerate(captions):
        img = image_urls[i] if i < len(image_urls) else None
        permalink = permalink_urls[i] if i < len(permalink_urls) else None
        ev = _caption_to_event(caption, img, nombre_lugar, categoria, municipio, now)
        if ev:
            title_key = ev["titulo"].lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                if permalink:
                    ev["_permalink"] = permalink
                events.append(ev)

    return events


# ── Keywords que indican que un caption es un evento ─────────────────────