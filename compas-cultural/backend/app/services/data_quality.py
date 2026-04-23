# -*- coding: utf-8 -*-
"""
Data Quality — Deduplicación, normalización y validación de datos culturales.
Centraliza la lógica que asegura que los datos en Supabase sean limpios,
sin duplicados y con formatos consistentes.
"""
import re
import json
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.database import supabase
from app.services.ollama_client import ollama_chat


# ═══════════════════════════════════════════════════════════════
# CATEGORÍAS VÁLIDAS
# ═══════════════════════════════════════════════════════════════

CATEGORIAS_VALIDAS = {
    "teatro", "musica_en_vivo", "rock", "jazz", "hip_hop", "electronica",
    "danza", "cine", "galeria", "arte_contemporaneo", "libreria", "poesia",
    "fotografia", "festival", "taller", "conferencia", "filosofia",
    "circo", "mural", "editorial", "otro",
}

MUNICIPIOS_VALIDOS = {
    "medellin", "bello", "itagui", "envigado", "sabaneta",
    "caldas", "la_estrella", "copacabana", "girardota", "barbosa",
}

MUNICIPIO_ALIAS = {
    "medellín": "medellin", "medellin": "medellin",
    "itagüí": "itagui", "itaguí": "itagui", "itagui": "itagui",
    "envigado": "envigado",
    "sabaneta": "sabaneta",
    "bello": "bello",
    "caldas": "caldas",
    "la estrella": "la_estrella", "la_estrella": "la_estrella",
    "copacabana": "copacabana",
    "girardota": "girardota",
    "barbosa": "barbosa",
}


EVENT_POSITIVE_TERMS = {
    "evento", "agenda", "programacion", "programación", "concierto", "recital", "obra",
    "funcion", "función", "festival", "muestra", "taller", "charla", "conversatorio",
    "foro", "exposicion", "exposición", "cine", "danza", "performance", "boletas",
    "boleteria", "boletería", "entradas", "inscripcion", "inscripción", "cupos", "aforo",
}

EVENT_NEGATIVE_TERMS = {
    "equipo", "presentamos al", "bienvenida", "feliz cumple", "cumpleanos", "cumpleaños",
    "comunicado", "pronunciamiento", "vacante", "convocatoria laboral", "hiring", "casting",
    "donacion", "donación", "manifiesto", "biografia", "biografía", "perfil del equipo",
}

EVENT_SOURCE_HINTS = ("/event", "/agenda", "/programacion", "/programación", "tuboleta", "eventbrite")
_EVENT_VALIDATION_CACHE: dict[str, bool] = {}


def _normalize_for_match(text: str) -> str:
    if not text:
        return ""
    lowered = unicodedata.normalize("NFD", text.lower())
    lowered = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _has_date_or_time_signal(text: str) -> bool:
    if not text:
        return False
    month_or_weekday = re.search(
        r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|"
        r"lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)\b",
        text,
    )
    day_num = re.search(r"\b([12]?\d|3[01])\b", text)
    time_like = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*([ap]m)?\b", text)
    am_pm = re.search(r"\b\d{1,2}\s*(am|pm|a\.m\.|p\.m\.)\b", text)
    return bool((month_or_weekday and day_num) or time_like or am_pm)


def _parse_bool_json(text: str) -> Optional[bool]:
    if not text:
        return None
    try:
        return bool(json.loads(text).get("is_event"))
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return bool(json.loads(m.group(0)).get("is_event"))
    except Exception:
        return None


def _validate_event_with_local_ai(title: str, description: str, source_url: str) -> Optional[bool]:
    model = (settings.ollama_model or "").strip()
    if not model:
        return None
    prompt = (
        "Clasifica si este contenido describe un evento cultural real y programado. "
        "Devuelve solo JSON: {\"is_event\": true|false, \"confidence\": 0-1}."
    )
    user_payload = {
        "titulo": (title or "")[:180],
        "descripcion": (description or "")[:550],
        "source_url": (source_url or "")[:180],
    }
    raw = ollama_chat(
        system_prompt=prompt,
        messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        max_tokens=120,
        temperature=0.0,
    )
    return _parse_bool_json(raw or "")


def is_likely_cultural_event(
    titulo: Optional[str],
    descripcion: Optional[str],
    *,
    fuente_url: Optional[str] = None,
    categoria: Optional[str] = None,
) -> bool:
    """Hybrid classifier for scraper candidates.

    Uses deterministic rules first. If ambiguous, optionally asks local Ollama.
    Conservative default: reject weak signals to avoid publishing non-events.
    """
    title_n = _normalize_for_match(titulo or "")
    desc_n = _normalize_for_match(descripcion or "")
    url_n = _normalize_for_match(fuente_url or "")
    cat_n = _normalize_for_match(categoria or "")

    if len(title_n) < 5:
        return False

    cache_key = f"{title_n}|{desc_n[:180]}|{url_n[:80]}"
    if cache_key in _EVENT_VALIDATION_CACHE:
        return _EVENT_VALIDATION_CACHE[cache_key]

    body = f"{title_n} {desc_n}".strip()
    positives = sum(1 for term in EVENT_POSITIVE_TERMS if term in body)
    negatives = sum(1 for term in EVENT_NEGATIVE_TERMS if term in body)
    has_datetime_signal = _has_date_or_time_signal(body)
    has_source_signal = any(hint in url_n for hint in EVENT_SOURCE_HINTS)
    has_category_signal = cat_n in {
        "teatro", "musica_en_vivo", "danza", "cine", "festival", "taller", "conferencia", "galeria", "otro"
    }

    score = positives + (2 if has_datetime_signal else 0) + (1 if has_source_signal else 0) + (1 if has_category_signal else 0)
    if negatives >= 2 and score <= 2:
        _EVENT_VALIDATION_CACHE[cache_key] = False
        return False
    if score >= 3:
        _EVENT_VALIDATION_CACHE[cache_key] = True
        return True
    if score <= 0:
        _EVENT_VALIDATION_CACHE[cache_key] = False
        return False

    ai_result = _validate_event_with_local_ai(title_n, desc_n, url_n)
    final = bool(ai_result) if ai_result is not None else False
    _EVENT_VALIDATION_CACHE[cache_key] = final
    return final


# ═══════════════════════════════════════════════════════════════
# SLUGIFY
# ═══════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    """Generate URL-safe slug from text."""
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


# ═══════════════════════════════════════════════════════════════
# DEDUPLICACIÓN
# ═══════════════════════════════════════════════════════════════

async def es_duplicado_evento(titulo: str, fecha_inicio: str, espacio_id: str = None) -> bool:
    """
    Verifica si un evento ya existe en BD.
    Duplicado si:
      - Mismo slug
      - Mismo titulo (primeros 60 chars normalizados) + misma fecha (día)
    """
    slug = slugify(titulo)
    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
    if existing.data:
        return True

    # Deduplicación cruzada: mismo título truncado + mismo día
    if fecha_inicio:
        fecha_date = fecha_inicio[:10]  # YYYY-MM-DD
        titulo_prefix = slug[:60]  # slug de los primeros ~60 chars del título
        q = (
            supabase.table("eventos")
            .select("id, slug")
            .gte("fecha_inicio", f"{fecha_date}T00:00:00")
            .lte("fecha_inicio", f"{fecha_date}T23:59:59")
        )
        same_day = q.execute()
        if same_day.data:
            for ev in same_day.data:
                ev_slug_prefix = (ev.get("slug") or "")[:60]
                # Si comparten los primeros 60 chars del slug → duplicado
                if ev_slug_prefix and titulo_prefix and ev_slug_prefix == titulo_prefix:
                    return True

    return False


async def es_duplicado_lugar(nombre: str, instagram_handle: str = None) -> bool:
    """
    Verifica si un lugar/colectivo ya existe.
    Duplicado si:
      - Mismo slug
      - Mismo instagram_handle
    """
    slug = slugify(nombre)
    existing = supabase.table("lugares").select("id").eq("slug", slug).execute()
    if existing.data:
        return True

    if instagram_handle:
        handle_clean = instagram_handle.lstrip("@").lower()
        resp = supabase.table("lugares").select("id").eq("instagram_handle", f"@{handle_clean}").execute()
        if resp.data:
            return True
        # Also check without @
        resp2 = supabase.table("lugares").select("id").eq("instagram_handle", handle_clean).execute()
        if resp2.data:
            return True

    return False


# ═══════════════════════════════════════════════════════════════
# NORMALIZACIÓN
# ═══════════════════════════════════════════════════════════════

def normalizar_municipio(raw: str) -> str:
    """Normaliza un nombre de municipio al slug correcto."""
    if not raw:
        return "medellin"
    clean = raw.lower().strip()
    if clean in MUNICIPIO_ALIAS:
        return MUNICIPIO_ALIAS[clean]
    # Try without accents
    normalized = unicodedata.normalize("NFD", clean)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    if normalized in MUNICIPIO_ALIAS:
        return MUNICIPIO_ALIAS[normalized]
    return "medellin"


def normalizar_categoria(raw: str) -> str:
    """Normaliza una categoría al enum válido."""
    if not raw:
        return "otro"
    clean = raw.lower().strip().replace(" ", "_").replace("-", "_")
    if clean in CATEGORIAS_VALIDAS:
        return clean
    # Common aliases
    aliases = {
        "musica": "musica_en_vivo", "música": "musica_en_vivo",
        "concierto": "musica_en_vivo", "conciertos": "musica_en_vivo",
        "exposicion": "galeria", "exposición": "galeria",
        "workshop": "taller", "curso": "taller",
        "charla": "conferencia", "conversatorio": "conferencia",
        "foro": "conferencia", "panel": "conferencia",
        "documental": "cine", "pelicula": "cine",
        "danza_contemporanea": "danza", "ballet": "danza",
        "rap": "hip_hop", "freestyle": "hip_hop",
        "techno": "electronica", "house": "electronica",
        "metal": "rock", "punk": "rock", "heavy_metal": "rock",
        "poema": "poesia", "literatura": "libreria",
    }
    if clean in aliases:
        return aliases[clean]
    return "otro"


def normalizar_instagram(handle: str) -> Optional[str]:
    """Limpia un handle de Instagram a formato @handle."""
    if not handle:
        return None
    # Remove URLs
    if "instagram.com" in handle:
        match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", handle)
        if match:
            return f"@{match.group(1).lower()}"
    # Clean @ and spaces
    clean = handle.strip().lstrip("@").split("/")[0].split("?")[0].lower()
    if clean and re.match(r"^[a-z0-9_.]+$", clean):
        return f"@{clean}"
    return None


def normalizar_precio(precio_raw: str) -> tuple[str, bool]:
    """Returns (precio_str, es_gratuito)."""
    if not precio_raw:
        return ("", False)
    lower = precio_raw.lower().strip()
    if any(kw in lower for kw in ["gratis", "gratuito", "libre", "free", "sin costo", "entrada libre"]):
        return ("Entrada libre", True)
    if lower in ("no especificado", "no disponible", ""):
        return ("", False)
    return (precio_raw.strip(), False)


def normalizar_evento(raw: dict) -> Optional[dict]:
    """
    Normaliza un evento raw antes de insertar en BD.
    Returns None si el evento debe descartarse (fecha inválida, etc.)
    """
    titulo = (raw.get("titulo") or "").strip()
    if not titulo or len(titulo) < 3:
        return None

    # Fecha validation
    fecha_str = raw.get("fecha_inicio")
    if not fecha_str:
        return None

    try:
        if isinstance(fecha_str, str):
            fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00").split("+")[0])
        else:
            fecha = fecha_str
    except (ValueError, TypeError):
        return None

    from zoneinfo import ZoneInfo
    now_co = datetime.now(ZoneInfo("America/Bogota"))
    # Discard if more than 7 days in the past
    if fecha < now_co - timedelta(days=7):
        return None
    # Discard if more than 1 year in the future
    if fecha > now_co + timedelta(days=365):
        return None

    # If year is missing/wrong, fix it
    if fecha.year < now_co.year:
        fecha = fecha.replace(year=now_co.year)
        if fecha < now_co - timedelta(days=7):
            fecha = fecha.replace(year=now_co.year + 1)

    # Normalize fields
    slug = slugify(titulo)
    municipio = normalizar_municipio(raw.get("municipio"))
    categoria = normalizar_categoria(raw.get("categoria_principal"))
    categorias = [normalizar_categoria(c) for c in (raw.get("categorias") or [])]
    categorias = [c for c in categorias if c != "otro"] or [categoria]
    precio_str, es_gratuito = normalizar_precio(raw.get("precio"))
    instagram = normalizar_instagram(raw.get("instagram_handle"))

    return {
        "titulo": titulo[:200],
        "slug": slug,
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": raw.get("fecha_fin"),
        "categorias": categorias,
        "categoria_principal": categoria,
        "municipio": municipio,
        "barrio": raw.get("barrio"),
        "nombre_lugar": raw.get("nombre_lugar"),
        "descripcion": (raw.get("descripcion") or "")[:500] or None,
        "imagen_url": raw.get("imagen_url"),
        "precio": precio_str,
        "es_gratuito": raw.get("es_gratuito", es_gratuito),
        "es_recurrente": raw.get("es_recurrente", False),
        "fuente": raw.get("fuente", "scraping"),
        "fuente_url": raw.get("fuente_url"),
        "lat": raw.get("lat"),
        "lng": raw.get("lng"),
        "verificado": raw.get("verificado", False),
    }


def normalizar_lugar(raw: dict) -> Optional[dict]:
    """Normaliza un lugar/colectivo raw antes de insertar en BD."""
    nombre = (raw.get("nombre") or "").strip()
    if not nombre or len(nombre) < 2:
        return None

    slug = slugify(nombre)
    municipio = normalizar_municipio(raw.get("municipio"))
    instagram = normalizar_instagram(raw.get("instagram_handle"))

    return {
        "nombre": nombre[:200],
        "slug": slug,
        "tipo": raw.get("tipo", "colectivo"),
        "categorias": [normalizar_categoria(c) for c in (raw.get("categorias") or [])],
        "categoria_principal": normalizar_categoria(raw.get("categoria_principal")),
        "municipio": municipio,
        "barrio": raw.get("barrio"),
        "direccion": raw.get("direccion"),
        "lat": raw.get("lat"),
        "lng": raw.get("lng"),
        "descripcion_corta": (raw.get("descripcion_corta") or "")[:300] or None,
        "descripcion": raw.get("descripcion"),
        "instagram_handle": instagram,
        "sitio_web": raw.get("sitio_web"),
        "telefono": raw.get("telefono"),
        "email": raw.get("email"),
        "es_underground": raw.get("es_underground", False),
        "es_institucional": raw.get("es_institucional", False),
        "fuente_datos": raw.get("fuente_datos", "scraping"),
        "nivel_actividad": raw.get("nivel_actividad", "activo"),
    }


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

def log_scraping(fuente: str, registros_nuevos: int, errores: int, detalle: dict = None):
    """Log scraping results to scraping_log table."""
    try:
        supabase.table("scraping_log").insert({
            "fuente": fuente,
            "registros_nuevos": registros_nuevos,
            "errores": errores,
            "detalle": detalle or {},
        }).execute()
    except Exception as e:
        print(f"  [WARN] Could not log to scraping_log: {e}")


if __name__ == "__main__":
    # Quick test
    print("Testing normalización...")
    assert slugify("Teatro Matacandelas — Obra nueva!") == "teatro-matacandelas-obra-nueva"
    assert normalizar_municipio("Medellín") == "medellin"
    assert normalizar_municipio("Itagüí") == "itagui"
    assert normalizar_categoria("concierto") == "musica_en_vivo"
    assert normalizar_categoria("punk") == "rock"
    assert normalizar_instagram("https://instagram.com/teatromatacandelas/") == "@teatromatacandelas"
    assert normalizar_precio("Entrada libre")[1] is True
    assert normalizar_precio("$50,000")[1] is False

    ev = normalizar_evento({
        "titulo": "Concierto de jazz",
        "fecha_inicio": "2026-04-25T19:00:00",
        "municipio": "Medellín",
        "categoria_principal": "jazz",
    })
    assert ev is not None
    assert ev["municipio"] == "medellin"
    print("✓ All tests passed")
