from fastapi import APIRouter, Query, HTTPException, Request
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


@router.post("/publicar")
async def publicar_evento(body: dict, request: Request):
    """Endpoint público para que colectivos/usuarios publiquen eventos.
    No requiere auth — cualquiera puede proponer un evento (queda sin verificar).
    """
    from app.schemas.evento import EventoPublicoCreate
    import re
    import unicodedata

    try:
        evento = EventoPublicoCreate(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Datos inválidos: {e}")

    # Validate future date (timezone-aware)
    from zoneinfo import ZoneInfo
    now_co = datetime.now(ZoneInfo("America/Bogota"))
    fecha = evento.fecha_inicio
    # Make naive datetimes timezone-aware (assume Bogotá)
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=ZoneInfo("America/Bogota"))
    if fecha < now_co:
        raise HTTPException(status_code=400, detail="La fecha del evento debe ser futura")
    # Reject dates more than 1 year in the future (likely errors)
    from datetime import timedelta
    if fecha > now_co + timedelta(days=365):
        raise HTTPException(status_code=400, detail="La fecha no puede ser mayor a 1 año en el futuro")

    # Generate slug
    text = unicodedata.normalize("NFD", evento.titulo.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]

    # Check duplicate
    from app.database import supabase
    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Ya existe un evento con ese nombre")

    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )

    evento_data = {
        "titulo": evento.titulo[:200],
        "slug": slug,
        "espacio_id": evento.espacio_id,
        "fecha_inicio": evento.fecha_inicio.isoformat(),
        "fecha_fin": evento.fecha_fin.isoformat() if evento.fecha_fin else None,
        "categorias": [evento.categoria_principal],
        "categoria_principal": evento.categoria_principal,
        "municipio": evento.municipio,
        "barrio": evento.barrio,
        "nombre_lugar": evento.nombre_lugar,
        "descripcion": (evento.descripcion or "")[:1000],
        "precio": evento.precio,
        "es_gratuito": evento.es_gratuito,
        "imagen_url": evento.imagen_url,
        "fuente": "colectivo_directo",
        "fuente_url": evento.contacto_instagram or evento.contacto_email,
        "verificado": False,
    }

    try:
        resp = supabase.table("eventos").insert(evento_data).execute()
        return {
            "ok": True,
            "mensaje": "Evento publicado. Será visible en la agenda inmediatamente.",
            "evento": resp.data[0] if resp.data else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando evento: {e}")


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