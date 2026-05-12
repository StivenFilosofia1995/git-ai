from fastapi import APIRouter, Query, HTTPException, Header
from typing import Annotated, List, Optional
from app.services import espacio_service
import time

router = APIRouter()

# Simple in-memory cache for stats (refreshes every 5 minutes)
_stats_cache: dict = {}
_STATS_TTL = 300  # seconds


@router.get("/")
def get_espacios(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    tipo: Optional[str] = None,
    nivel_actividad: Optional[str] = None,
    es_underground: Optional[bool] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return espacio_service.get_espacios(
        municipio, barrio, categoria, nivel_actividad, es_underground, limit, offset, tipo=tipo
    )


@router.get("/stats")
def get_stats():
    """Conteos rápidos para la página home — cacheados 5 minutos."""
    from app.database import supabase
    from app.services import zona_service

    now = time.time()
    if _stats_cache.get("ts") and now - _stats_cache["ts"] < _STATS_TTL:
        return _stats_cache["data"]

    espacios = supabase.table("lugares").select("id", count="exact").neq("nivel_actividad", "cerrado").execute()
    eventos = supabase.table("eventos").select("id", count="exact").execute()
    colectivos = supabase.table("lugares").select("id", count="exact").eq("tipo", "colectivo").execute()
    try:
        zonas = zona_service.get_zonas()
        n_zonas = len(zonas)
    except Exception:
        n_zonas = 0

    result = {
        "espacios": espacios.count or 0,
        "eventos": eventos.count or 0,
        "colectivos": colectivos.count or 0,
        "zonas": n_zonas,
    }
    _stats_cache["data"] = result
    _stats_cache["ts"] = now
    return result


@router.get("/colectivos-activos")
def get_colectivos_activos(limit: Annotated[int, Query(ge=1, le=50)] = 20):
    """
    Colectivos y espacios culturales con eventos en los próximos 21 días.
    Ordenados por cantidad de eventos próximos (más activos primero).
    Incluye instagram_handle para visibilidad directa.
    """
    from app.database import supabase
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    CO_TZ = ZoneInfo("America/Bogota")
    ahora = datetime.now(CO_TZ)
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hasta = hoy + timedelta(days=21)

    # Traer eventos próximos con espacio_id
    ev_resp = (
        supabase.table("eventos")
        .select("espacio_id,titulo,fecha_inicio")
        .gte("fecha_inicio", hoy.isoformat())
        .lte("fecha_inicio", hasta.isoformat())
        .not_.is_("espacio_id", "null")
        .limit(1000)
        .execute()
    )
    eventos = ev_resp.data or []

    # Contar eventos por espacio_id
    from collections import Counter
    conteo: Counter = Counter()
    for ev in eventos:
        eid = ev.get("espacio_id")
        if eid:
            conteo[eid] += 1

    if not conteo:
        return []

    # Traer los lugares más activos
    top_ids = [eid for eid, _ in conteo.most_common(limit * 2)]

    # Supabase IN query — batch
    lugares_resp = (
        supabase.table("lugares")
        .select("id,nombre,slug,tipo,categoria_principal,categorias,barrio,municipio,instagram_handle,sitio_web,descripcion_corta,imagen_url,nivel_actividad,es_underground")
        .in_("id", top_ids)
        .execute()
    )
    lugares = lugares_resp.data or []

    # Añadir conteo y ordenar
    for l in lugares:
        l["proximos_eventos"] = conteo.get(l["id"], 0)

    lugares.sort(key=lambda x: x["proximos_eventos"], reverse=True)
    return lugares[:limit]


@router.get("/cerca")
def get_espacios_cerca(
    lat: Annotated[float, Query(description="Latitud")],
    lng: Annotated[float, Query(description="Longitud")],
    radio_metros: Annotated[int, Query(ge=100, le=10000)] = 2000,
):
    return espacio_service.get_espacios_cerca(lat, lng, radio_metros)


@router.delete("/{espacio_id}")
def delete_espacio(
    espacio_id: str,
    x_scraper_key: str | None = Header(default=None, alias="X-Scraper-Key"),
):
    """Elimina un espacio/colectivo y sus eventos. Requiere X-Scraper-Key de admin."""
    from app.config import settings
    from app.database import supabase
    if x_scraper_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="No autorizado")
    # Delete associated events first
    supabase.table("eventos").delete().eq("espacio_id", espacio_id).execute()
    resp = supabase.table("lugares").delete().eq("id", espacio_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    return {"ok": True, "deleted": espacio_id}


@router.get("/{slug}")
def get_espacio(slug: str):
    try:
        return espacio_service.get_espacio_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Espacio no encontrado") from exc