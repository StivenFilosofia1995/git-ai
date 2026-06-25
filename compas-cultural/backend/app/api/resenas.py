from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional

from app.schemas.resena import ResenaCreate, ResenaUpdate
from app.services import resena_service

router = APIRouter()


def _get_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido")
    return token


@router.get("/{tipo}/{item_id}")
def obtener_resenas(
    tipo: str,
    item_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    if tipo not in ("evento", "espacio"):
        raise HTTPException(status_code=400, detail="Tipo debe ser 'evento' o 'espacio'")
    return resena_service.obtener_resenas(tipo, item_id, limit, offset)


@router.get("/{tipo}/{item_id}/stats")
def obtener_stats(tipo: str, item_id: str):
    if tipo not in ("evento", "espacio"):
        raise HTTPException(status_code=400, detail="Tipo debe ser 'evento' o 'espacio'")
    return resena_service.obtener_stats(tipo, item_id)


@router.get("/{tipo}/{item_id}/mi-resena")
def obtener_mi_resena(
    tipo: str,
    item_id: str,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    resena = resena_service.obtener_resena_usuario(user_id, tipo, item_id)
    if not resena:
        raise HTTPException(status_code=404, detail="No has reseñado este item")
    return resena


@router.post("/", status_code=201)
def crear_resena(
    body: ResenaCreate,
    authorization: Optional[str] = Header(None),
    x_user_nombre: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    existing = resena_service.obtener_resena_usuario(user_id, body.tipo, body.item_id)
    if existing:
        raise HTTPException(status_code=409, detail="Ya reseñaste este item. Podés editarla.")
    return resena_service.crear_resena(user_id, x_user_nombre, body.model_dump())


@router.put("/{resena_id}")
def actualizar_resena(
    resena_id: str,
    body: ResenaUpdate,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    try:
        return resena_service.actualizar_resena(resena_id, user_id, body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{resena_id}", status_code=204)
def eliminar_resena(
    resena_id: str,
    authorization: Optional[str] = Header(None),
):
    user_id = _get_user_id(authorization)
    if not resena_service.eliminar_resena(resena_id, user_id):
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
