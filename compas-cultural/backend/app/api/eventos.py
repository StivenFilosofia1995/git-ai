"""
API /eventos
Fixes 2026-04:
- Añadidos filtros colectivo_slug y texto en GET /
- Nuevo endpoint GET /proximas-semanas?dias=21
- Resto se mantiene igual (hoy, feed, semana, espacio, slug, publicar).
2026-05:
- GET  /para-ti          → feed algorítmico (Instagram-style, basado en vistas)
- POST /{id}/vista       → registrar vista de un evento
"""
import hashlib
from fastapi import APIRouter, Query, HTTPException, Request, Header
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

    # Solo columnas que existen en la tabla eventos
    evento_data = {
        "titulo": evento.titulo[:200],
        "slug": slug,
        "espacio_id": evento.espacio_id,
        "fecha_inicio": evento.fecha_inicio.isoformat(),
        "fecha_fin": evento.fecha_fin.isoformat() if evento.fecha_fin else None,
        "hora_confirmada": bool(evento.hora_inicio),
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
    desde_dias: Annotated[int, Query(ge=0, le=60)] = 1,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
):
    """Eventos en ventana [desde_dias, dias] desde hoy (default 1..21 = mañana a 3 semanas)."""
    return evento_service.get_eventos_proximas_semanas(
        dias=dias,
        desde_dias=desde_dias,
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )


@router.get("/destacados")
def get_eventos_destacados(limit: Annotated[int, Query(ge=1, le=10)] = 5):
    """Top eventos de los próximos 14 días para el panel 'Evento de la Semana'."""
    return evento_service.get_eventos_destacados(limit=limit)


@router.get("/espacio/{espacio_id}")
def get_eventos_espacio(espacio_id: str, limit: int = 10):
    return evento_service.get_eventos_by_espacio(espacio_id, limit)


@router.delete("/{evento_id}")
def delete_evento(
    evento_id: str,
    x_scraper_key: str | None = Header(default=None, alias="X-Scraper-Key"),
):
    """Elimina un evento. Requiere X-Scraper-Key de admin."""
    from app.config import settings
    from app.database import supabase
    if x_scraper_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="No autorizado")
    resp = supabase.table("eventos").delete().eq("id", evento_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return {"ok": True, "deleted": evento_id}


@router.post("/{evento_id}/reportar")
def reportar_evento(evento_id: str, body: dict = {}):
    """Marca un evento como reportado por la comunidad (duplicado, incorrecto, pasado)."""
    from app.database import supabase
    motivo = (body.get("motivo") or "incorrecto")[:100]
    resp = supabase.table("eventos").select("id").eq("id", evento_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    supabase.table("eventos").update({"reportado": True, "motivo_reporte": motivo}).eq("id", evento_id).execute()
    return {"ok": True, "message": "Reporte recibido. Gracias por ayudar a mantener la agenda limpia."}


@router.get("/para-ti")
def get_feed_para_ti(
    request: Request,
    municipio: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    authorization: Optional[str] = Header(default=None),
):
    """
    Feed algorítmico personalizado (Instagram-style).

    Rankea eventos por: urgencia + calidad + trending (vistas 24h) +
    popularidad acumulada + afinidad del usuario + proximidad geográfica.

    Para usuarios autenticados (Authorization: Bearer <jwt>) el algoritmo
    también considera las categorías que más han explorado históricamente.
    """
    user_id: Optional[str] = None
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        parts = token.split(".")
        if len(parts) == 3:
            import base64, json as _json
            try:
                padding = 4 - len(parts[1]) % 4
                payload = _json.loads(
                    base64.urlsafe_b64decode(parts[1] + "=" * padding)
                )
                sub = payload.get("sub", "")
                import re
                if sub and re.match(r"^[0-9a-f-]{36}$", sub, re.I):
                    user_id = sub
            except Exception:
                pass

    return evento_service.get_feed_para_ti(
        user_id=user_id,
        municipio=municipio,
        lat=lat,
        lng=lng,
        limit=limit,
        offset=offset,
    )


@router.post("/{evento_id}/vista")
def registrar_vista_evento(
    evento_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    """
    Registra una vista del evento. Idempotente: la misma sesión no cuenta dos veces.

    - Anónimo: se hashea la IP del cliente
    - Autenticado: se asocia al user_id del JWT
    """
    user_id: Optional[str] = None
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        parts = token.split(".")
        if len(parts) == 3:
            import base64, json as _json
            try:
                padding = 4 - len(parts[1]) % 4
                payload = _json.loads(
                    base64.urlsafe_b64decode(parts[1] + "=" * padding)
                )
                sub = payload.get("sub", "")
                import re
                if sub and re.match(r"^[0-9a-f-]{36}$", sub, re.I):
                    user_id = sub
            except Exception:
                pass

    # Hash the client IP for anonymous tracking (privacy-preserving)
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    inserted = evento_service.registrar_vista(
        evento_id=evento_id,
        user_id=user_id,
        ip_hash=ip_hash,
        session_id=x_session_id,
    )
    return {"ok": True, "nueva_vista": inserted}


@router.get("/{slug}")
def get_evento(slug: str):
    try:
        return evento_service.get_evento_by_slug(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado") from exc
