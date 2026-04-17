from typing import List, Optional
from datetime import datetime, timedelta

from app.database import supabase


def _now_co() -> datetime:
    """Current time in Colombia (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)


def _now_iso() -> str:
    return _now_co().isoformat()


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
    hoy = _now_co().date()
    manana = hoy + timedelta(days=1)
    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy.isoformat())
        .lt("fecha_inicio", manana.isoformat())
        .order("fecha_inicio")
        .execute()
    )
    return response.data


def get_eventos_semana() -> List[dict]:
    hoy = _now_co().date()
    semana = hoy + timedelta(days=7)
    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy.isoformat())
        .lte("fecha_inicio", semana.isoformat())
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