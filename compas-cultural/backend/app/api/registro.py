from fastapi import APIRouter, HTTPException, BackgroundTasks, Request

from app.database import supabase
from app.schemas.registro import (
    RegistroURLRequest,
    RegistroURLResponse,
    RegistroEstadoResponse,
    detectar_tipo_url,
)

router = APIRouter()


@router.post("/", response_model=RegistroURLResponse, status_code=201)
def registrar_por_url(
    body: RegistroURLRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    tipo_url = detectar_tipo_url(body.url)

    row = {
        "url": body.url,
        "tipo_url": tipo_url,
        "estado": "pendiente",
        "mensaje": "Solicitud recibida. Iniciando extracción de datos…",
        "ip_solicitante": request.client.host if request.client else None,
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
