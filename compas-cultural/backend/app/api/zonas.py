from fastapi import APIRouter, HTTPException
from typing import List
from app.services import zona_service
from app.services.perfil_service import obtener_eventos_zona_hoy

router = APIRouter()


@router.get("/")
def get_zonas():
    return zona_service.get_zonas()


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