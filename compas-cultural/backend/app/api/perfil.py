from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.schemas.perfil import PerfilCreate, PerfilUpdate, PerfilResponse, InteraccionCreate
from app.services import perfil_service

router = APIRouter()


def _get_user_id(authorization: Optional[str] = Header(None)) -> str:
    """Extrae el user_id del header. En producción usar JWT validation."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    # Esperamos "Bearer <user_id>" o simplemente el user_id
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido")
    return token


@router.post("/", response_model=PerfilResponse, status_code=201)
def crear_perfil(
    body: PerfilCreate,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)

    # Si ya existe, actualizamos el perfil en lugar de fallar con 409.
    existente = perfil_service.obtener_perfil(user_id)
    if existente:
        return perfil_service.actualizar_perfil(user_id, body.model_dump())

    return perfil_service.crear_perfil(user_id, body.model_dump())


@router.get("/me", response_model=PerfilResponse)
def obtener_mi_perfil(
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    perfil = perfil_service.obtener_perfil(user_id)
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return perfil


@router.patch("/me", response_model=PerfilResponse)
def actualizar_mi_perfil(
    body: PerfilUpdate,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    perfil = perfil_service.obtener_perfil(user_id)
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return perfil_service.actualizar_perfil(user_id, body.model_dump(exclude_unset=True))


@router.post("/interaccion", status_code=201)
def registrar_interaccion(
    body: InteraccionCreate,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    perfil_service.registrar_interaccion(user_id, body.tipo, body.item_id, body.categoria)
    return {"ok": True}


@router.post("/busqueda", status_code=201)
def registrar_busqueda(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    perfil_service.registrar_busqueda(user_id, body.get("query", ""), body.get("categorias", []))
    return {"ok": True}


@router.get("/recomendaciones")
def obtener_recomendaciones(
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    return perfil_service.obtener_recomendaciones(user_id, limit)
