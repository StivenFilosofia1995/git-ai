"""
API /eventos
Fixes 2026-04:
- Añadidos filtros colectivo_slug y texto en GET /
- Nuevo endpoint GET /proximas-semanas?dias=21
- Resto se mantiene igual (hoy, feed, semana, espacio, slug, publicar).
"""
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
    colectivo_slug: Optional[str] = None,
    texto: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Listar eventos con filtros robustos."""
    return evento_service.get_eventos(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
        limit=limit,
        offset=offset,
        colectivo_slug=colectivo_slug,
        texto=texto,
    )


@router.post("/publicar")
async def publicar_evento(body: dict, request: Request):
    """Endpoint público para que colectivos/usuarios publiquen eventos.
    No requiere auth — cualquiera puede proponer un evento (queda sin verificar).
    
    Soporta campos completos: hora_inicio, hora_fin, aforo, sesion_numero, imagen_url_alternativa.
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
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=ZoneInfo("America/Bogota"))
    if fecha < now_co:
        raise HTTPException(status_code=400, detail="La fecha del evento debe ser futura")

    from datetime import timedelta
    if fecha > now_co + timedelta(days=365):
        raise HTTPException(
            status_code=400, detail="La fecha no puede ser mayor a 1 año en el futuro"
        )

    # Generate slug
    text = unicodedata.normalize("NFD", evento.titulo.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]

    # Check duplicate
    from app.database import supabase
    existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Ya existe un evento con ese nombre")

    # Eventos publicados manualmente tienen hora confirmada (el usuario la puso).
    evento_data = {
        "titulo": evento.titulo[:200],
        "slug": slug,
        "espacio_id": evento.espacio_id,
        "fecha_inicio": evento.fecha_inicio.isoformat(),
        "fecha_fin": evento.fecha_fin.isoformat() if evento.fecha_fin else None,
        "hora_inicio": evento.hora_inicio,  # HH:MM format
        "hora_fin": evento.hora_fin,        # HH:MM format
        "aforo": evento.aforo,              # Event capacity
        "sesion_numero": evento.sesion_numero,  # Session number
        "tiene_hora_confirmada": False,
        "categorias": [evento.categoria_principal],
        "categoria_principal": evento.categoria_principal,
        "municipio": evento.municipio,
        "barrio": evento.barrio,
        "nombre_lugar": evento.nombre_lugar,
        "descripcion": (evento.descripcion or "")[:1000],
        "precio": evento.precio,
        "es_gratuito": evento.es_gratuito,
        "imagen_url": evento.imagen_url,
        "imagen_url_principal": evento.imagen_url,  # Primary image
        "imagen_url_alternativa": evento.imagen_url_alternativa,  # Alternative
        "tiene_imagen_confirmada": bool(evento.imagen_url),
        "es_evento_registrado": True,  # Mark as user-registered
        "fuente": "colectivo_directo",
        "fuente_url": evento.contacto_instagram or evento.contacto_email,
        "verificado": False,
        "estado_moderacion": "pendiente",
    }

    try:
        resp = supabase.table("eventos").insert(evento_data).execute()
        new_evento = resp.data[0] if resp.data else None
        
        # If alternative image provided, add it to evento_imagenes table
        if evento.imagen_url_alternativa and new_evento:
            try:
                supabase.table("evento_imagenes").insert({
                    "evento_id": new_evento["id"],
                    "imagen_url": evento.imagen_url_alternativa,
                    "tipo": "galeria",
                    "es_principal": False,
                    "subida_por_usuario": True,
                }).execute()
            except Exception as e:
                print(f"[evento_publish] No se pudo guardar imagen alternativa: {e}")
        
        return {
            "ok": True,
            "mensaje": "✅ Evento recibido. Será revisado y publicado en la agenda en breve.",
            "evento": new_evento,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando evento: {e}")


@router.get("/hoy")
def get_eventos_hoy(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
):
    return evento_service.get_eventos_hoy(
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )


@router.get("/feed")
def get_eventos_feed(limit: Annotated[int, Query(ge=1, le=50)] = 20):
    """Smart diverse feed for the home page."""
    return evento_service.get_eventos_feed(limit)


@router.get("/semana")
def get_eventos_semana(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
):
    """Eventos hasta el domingo de la próxima semana (7–14 días)."""
    return evento_service.get_eventos_semana(
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )


@router.get("/proximas-semanas")
def get_eventos_proximas_semanas(
    dias: Annotated[int, Query(ge=1, le=90)] = 21,
    desde_dias: Annotated[int, Query(ge=0, le=60)] = 0,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
):
    """Eventos en ventana [desde_dias, dias] desde mañana (default 1..21)."""
    return evento_service.get_eventos_proximas_semanas(
        dias=dias,
        desde_dias=desde_dias,
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )


@router.get("/espacio/{espacio_id}")
def get_eventos_espacio(espacio_id: str, limit: int = 10):
    return evento_service.get_eventos_by_espacio(espacio_id, limit)


@router.get("/{slug}")
def get_evento(slug: str):
    try:
        return evento_service.get_evento_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado") from exc
