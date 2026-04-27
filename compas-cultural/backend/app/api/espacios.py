from fastapi import APIRouter, Query, HTTPException
from typing import Annotated, List, Optional
from app.services import espacio_service

router = APIRouter()


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
    """Conteos rápidos para la página home."""
    from app.database import supabase
    from app.services import zona_service
    espacios = supabase.table("lugares").select("id", count="exact").neq("nivel_actividad", "cerrado").execute()
    eventos = supabase.table("eventos").select("id", count="exact").neq("estado_moderacion", "rechazado").execute()
    colectivos = supabase.table("lugares").select("id", count="exact").eq("tipo", "colectivo").execute()
    try:
        zonas = zona_service.get_zonas()
        n_zonas = len(zonas)
    except Exception:
        n_zonas = 0
    return {
        "espacios": espacios.count or 0,
        "eventos": eventos.count or 0,
        "colectivos": colectivos.count or 0,
        "zonas": n_zonas,
    }


@router.get("/cerca")
def get_espacios_cerca(
    lat: Annotated[float, Query(description="Latitud")],
    lng: Annotated[float, Query(description="Longitud")],
    radio_metros: Annotated[int, Query(ge=100, le=10000)] = 2000,
):
    return espacio_service.get_espacios_cerca(lat, lng, radio_metros)


@router.get("/{slug}")
def get_espacio(slug: str):
    try:
        return espacio_service.get_espacio_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Espacio no encontrado") from exc