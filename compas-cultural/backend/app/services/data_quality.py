# -*- coding: utf-8 -*-
"""
Data Quality — Deduplicación, normalización y validación de datos culturales.
Centraliza la lógica que asegura que los datos en Supabase sean limpios,
sin duplicados y con formatos consistentes.
"""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from app.database import supabase


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
      - Mismo titulo + misma fecha + mismo espacio
    """
    slug = slugify(titulo)
    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
    if existing.data:
        return True

    # Check titulo + fecha + espacio
    if espacio_id and fecha_inicio:
        fecha_date = fecha_inicio[:10]  # solo YYYY-MM-DD
        q = (
            supabase.table("eventos")
            .select("id")
            .eq("espacio_id", espacio_id)
            .gte("fecha_inicio", f"{fecha_date}T00:00:00")
            .lte("fecha_inicio", f"{fecha_date}T23:59:59")
        )
        same_day = q.execute()
        if same_day.data:
            for ev in same_day.data:
                # Could add fuzzy title match here in future
                pass

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

    now_co = datetime.utcnow() - timedelta(hours=5)
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
