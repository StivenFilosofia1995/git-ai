from fastapi import APIRouter, Query, HTTPException
from typing import Annotated, List, Optional
from datetime import datetime
from app.services import evento_service

router = APIRouter()


@router.get("/")
def get_eventos(
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return evento_service.get_eventos(
        fecha_desde, fecha_hasta, municipio, barrio, categoria, es_gratuito, limit, offset
    )


@router.get("/hoy")
def get_eventos_hoy():
    return evento_service.get_eventos_hoy()


@router.get("/feed")
def get_eventos_feed(limit: Annotated[int, Query(ge=1, le=50)] = 20):
    """Smart diverse feed for the home page."""
    return evento_service.get_eventos_feed(limit)


@router.get("/semana")
def get_eventos_semana():
    return evento_service.get_eventos_semana()


@router.get("/espacio/{espacio_id}")
def get_eventos_espacio(espacio_id: str, limit: int = 10):
    return evento_service.get_eventos_by_espacio(espacio_id, limit)


@router.get("/{slug}")
def get_evento(slug: str):
    try:
        return evento_service.get_evento_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado") from exc