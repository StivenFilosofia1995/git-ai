from typing import List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import supabase

CO_TZ = ZoneInfo("America/Bogota")


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def _now_iso() -> str:
    return _now_co().strftime("%Y-%m-%dT%H:%M:%S")


def get_eventos(
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[dict]:
    query = supabase.table("eventos").select("*").gte("fecha_inicio", _now_iso())

    if fecha_desde:
        query = query.gte("fecha_inicio", fecha_desde.isoformat())
    if fecha_hasta:
        query = query.lte("fecha_inicio", fecha_hasta.isoformat())
    if municipio:
        query = query.eq("municipio", municipio)
    if barrio:
        query = query.ilike("barrio", f"%{barrio}%")
    if categoria:
        query = query.contains("categorias", [categoria])
    if es_gratuito is not None:
        query = query.eq("es_gratuito", es_gratuito)

    response = query.order("fecha_inicio").limit(limit).range(offset, offset + limit - 1).execute()
    return response.data


def get_eventos_hoy() -> List[dict]:
    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy_inicio.strftime("%Y-%m-%dT%H:%M:%S"))
        .lt("fecha_inicio", hoy_fin.strftime("%Y-%m-%dT%H:%M:%S"))
        .order("fecha_inicio")
        .execute()
    )
    return response.data


def get_eventos_semana() -> List[dict]:
    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    semana_fin = hoy_inicio + timedelta(days=7)
    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy_inicio.strftime("%Y-%m-%dT%H:%M:%S"))
        .lte("fecha_inicio", semana_fin.strftime("%Y-%m-%dT%H:%M:%S"))
        .order("fecha_inicio")
        .execute()
    )
    return response.data


def get_evento_by_slug(slug: str) -> dict:
    response = (
        supabase.table("eventos")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )
    return response.data


def get_eventos_by_espacio(espacio_id: str, limit: int = 10) -> List[dict]:
    response = (
        supabase.table("eventos")
        .select("*")
        .eq("espacio_id", espacio_id)
        .gte("fecha_inicio", _now_iso())
        .order("fecha_inicio")
        .limit(limit)
        .execute()
    )
    return response.data


def get_eventos_feed(limit: int = 20) -> List[dict]:
    """
    Smart feed: diverse mix of upcoming events across all categories.
    Ensures variety by limiting max events per category and shuffling.
    Shows a mix of free/paid, different municipios, and different categories.
    Used for non-logged-in users and the general home feed.
    """
    from collections import Counter
    import random

    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    proxima_semana = hoy_inicio + timedelta(days=14)

    # Fetch a larger pool to pick from
    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy_inicio.strftime("%Y-%m-%dT%H:%M:%S"))
        .lte("fecha_inicio", proxima_semana.strftime("%Y-%m-%dT%H:%M:%S"))
        .order("fecha_inicio")
        .limit(200)
        .execute()
    )
    pool = response.data
    if not pool:
        # Fallback: next 30 events whenever they are
        response = (
            supabase.table("eventos")
            .select("*")
            .gte("fecha_inicio", _now_iso())
            .order("fecha_inicio")
            .limit(30)
            .execute()
        )
        pool = response.data

    if len(pool) <= limit:
        return pool

    # Score diversity: prefer events with images, different categories, sooner dates
    cat_count: Counter = Counter()
    muni_count: Counter = Counter()
    result = []

    # Prioritize events with images
    with_img = [e for e in pool if e.get("imagen_url")]
    without_img = [e for e in pool if not e.get("imagen_url")]

    # Shuffle within groups for variety
    random.shuffle(with_img)
    random.shuffle(without_img)

    # Interleave: prefer with-image but include some without
    candidates = with_img + without_img

    for ev in candidates:
        cat = ev.get("categoria_principal", "otro")
        muni = ev.get("municipio", "medellin")

        # Max 3 per category
        if cat_count[cat] >= 3:
            continue
        # Max 6 per municipio (unless only one municipio has events)
        if muni_count[muni] >= 6 and len(muni_count) > 1:
            continue

        cat_count[cat] += 1
        muni_count[muni] += 1
        result.append(ev)

        if len(result) >= limit:
            break

    # Sort final result by date
    result.sort(key=lambda e: e.get("fecha_inicio", ""))
    return result