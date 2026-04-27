from fastapi import APIRouter, HTTPException, Query
from typing import Annotated
from app.services import zona_service
from app.services.perfil_service import obtener_eventos_zona_hoy

router = APIRouter()


@router.get("/")
def get_zonas():
    return zona_service.get_zonas()


@router.get("/calientes/mapa")
def get_zonas_calientes(
    k: Annotated[int, Query(ge=2, le=20)] = 7,
    dias: Annotated[int, Query(ge=1, le=30)] = 14,
):
    """
    Clusters K-means de eventos próximos sobre el mapa.
    Útil para visualizar zonas con alta concentración cultural.
    Retorna lista de clusters con centroide (lat/lng), conteo y eventos.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app.database import supabase
    from app.services.ml_utils import kmeans_geo

    CO_TZ = ZoneInfo("America/Bogota")
    ahora = datetime.now(CO_TZ)
    hasta = (ahora + timedelta(days=dias)).isoformat()

    resp = (
        supabase.table("eventos")
        .select("id,titulo,lat,lng,fecha_inicio,categoria_principal,nombre_lugar")
        .gte("fecha_inicio", ahora.isoformat())
        .lte("fecha_inicio", hasta)
        .neq("estado_moderacion", "rechazado")
        .not_.is_("lat", "null")
        .not_.is_("lng", "null")
        .limit(500)
        .execute()
    )
    eventos = [e for e in (resp.data or []) if e.get("lat") and e.get("lng")]
    if not eventos:
        return []

    points = [(float(e["lat"]), float(e["lng"])) for e in eventos]
    clusters = kmeans_geo(points, k=k)

    result = []
    for cluster in clusters:
        eventos_cluster = [eventos[i] for i in cluster["indices"]]
        result.append({
            "lat": round(cluster["lat"], 6),
            "lng": round(cluster["lng"], 6),
            "count": cluster["count"],
            "eventos": eventos_cluster[:5],  # Muestra hasta 5 por cluster
        })
    return result


@router.get("/{slug}")
def get_zona(slug: str):
    try:
        return zona_service.get_zona_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Zona no encontrada") from exc


@router.get("/{slug}/cultura-hoy")
def get_cultura_zona_hoy(slug: str):
    """Obtiene eventos y espacios activos hoy en una zona."""
    try:
        zona = zona_service.get_zona_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Zona no encontrada") from exc
    return obtener_eventos_zona_hoy(zona["id"])