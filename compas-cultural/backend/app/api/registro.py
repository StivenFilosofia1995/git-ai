from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from datetime import datetime

from app.database import supabase
from app.limiter import rate_limit
from app.schemas.registro import (
    RegistroURLRequest,
    RegistroURLResponse,
    RegistroEstadoResponse,
    RegistroManualRequest,
    RegistroManualResponse,
    detectar_tipo_url,
)

router = APIRouter()


def _slugify(text: str) -> str:
    import re
    value = (text or "").lower().strip()
    value = re.sub(r"[áàäâ]", "a", value)
    value = re.sub(r"[éèëê]", "e", value)
    value = re.sub(r"[íìïî]", "i", value)
    value = re.sub(r"[óòöô]", "o", value)
    value = re.sub(r"[úùüû]", "u", value)
    value = re.sub(r"[ñ]", "n", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:120]


@router.post(
    "/manual",
    response_model=RegistroManualResponse,
    status_code=201,
)
@rate_limit("8/hour")
def registrar_manual(
    body: RegistroManualRequest,
    request: Request,
):
    if not body.acepta_politica_datos:
        raise HTTPException(status_code=400, detail="Debes aceptar la política de protección de datos")

    slug_base = _slugify(body.nombre)
    slug = slug_base or "espacio-cultural"

    # Ensure unique slug
    for idx in range(0, 20):
        candidate = slug if idx == 0 else f"{slug}-{idx+1}"
        exists = supabase.table("lugares").select("id").eq("slug", candidate).limit(1).execute()
        if not exists.data:
            slug = candidate
            break

    ig = (body.instagram_handle or "").strip()
    if ig and not ig.startswith("@"):
        ig = f"@{ig}"

    row = {
        "nombre": body.nombre,
        "slug": slug,
        "tipo": body.tipo or "colectivo",
        "categorias": [body.categoria_principal] if body.categoria_principal else [],
        "categoria_principal": body.categoria_principal or "otro",
        "municipio": (body.municipio or "medellin").lower(),
        "barrio": body.barrio,
        "descripcion_corta": body.descripcion_corta,
        "email": body.email,
        "instagram_handle": ig or None,
        "sitio_web": (body.sitio_web or None),
        "fuente_datos": "registro_manual",
        "nivel_actividad": "activo",
    }

    inserted = supabase.table("lugares").insert(row).execute()
    if not inserted.data:
        raise HTTPException(status_code=500, detail="No se pudo crear el perfil manual")

    lugar_id = inserted.data[0]["id"]

    # Support system: add to scraping radar immediately.
    try:
        now_iso = datetime.now().isoformat()
        supabase.table("scraping_state").upsert(
            {
                "lugar_id": lugar_id,
                "last_scraped_at": now_iso,
                "events_found": 0,
                "consecutive_empty": 0,
            },
            on_conflict="lugar_id",
        ).execute()
    except Exception:
        pass

    return {
        "ok": True,
        "lugar_id": lugar_id,
        "slug": slug,
        "mensaje": "Perfil creado manualmente y agregado al radar de scraping.",
    }


@router.post(
    "/",
    response_model=RegistroURLResponse,
    status_code=201,
    responses={400: {"description": "Debe aceptar política de protección de datos"}},
)
@rate_limit("5/hour")
def registrar_por_url(
    body: RegistroURLRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    if not body.acepta_politica_datos:
        raise HTTPException(status_code=400, detail="Debes aceptar la política de protección de datos")

    tipo_url = detectar_tipo_url(body.url)

    row = {
        "url": body.url,
        "tipo_url": tipo_url,
        "estado": "pendiente",
        "mensaje": "Solicitud recibida. Iniciando extracción de datos…",
        "ip_solicitante": (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else None)
        ),
    }
    resp = supabase.table("solicitudes_registro").insert(row).execute()
    solicitud = resp.data[0]

    background_tasks.add_task(_ejecutar_scraping, solicitud["id"])
    return solicitud


@router.get(
    "/{solicitud_id}",
    response_model=RegistroEstadoResponse,
    responses={404: {"description": "Solicitud no encontrada"}},
)
def consultar_estado(solicitud_id: int):
    resp = (
        supabase.table("solicitudes_registro")
        .select("*")
        .eq("id", solicitud_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return resp.data[0]


async def _ejecutar_scraping(solicitud_id: int) -> None:
    from app.services.scraper_llm import procesar_solicitud_scraping
    await procesar_solicitud_scraping(solicitud_id)
