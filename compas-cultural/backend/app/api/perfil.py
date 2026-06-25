import re
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.schemas.perfil import PerfilCreate, PerfilUpdate, PerfilResponse, InteraccionCreate
from app.services import perfil_service

router = APIRouter()

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _get_user_id(authorization: Optional[str] = Header(None)) -> str:
    """Extrae el user_id del JWT de Supabase Auth.
    Supabase envía 'Bearer <jwt>' — el sub del JWT es el user UUID.
    Para simplificar sin verificar firma: extraemos el payload y validamos el sub.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido")

    # Intentar decodificar el payload del JWT (sin verificar firma — Supabase ya lo valida)
    parts = token.split(".")
    if len(parts) == 3:
        import base64, json as _json
        try:
            padding = 4 - len(parts[1]) % 4
            payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
            payload = _json.loads(payload_bytes)
            sub = payload.get("sub", "")
            if sub and _UUID_RE.match(sub):
                return sub
        except Exception:
            pass

    # Fallback: el token completo es el user_id (compatibilidad con clientes viejos)
    if _UUID_RE.match(token):
        return token

    raise HTTPException(status_code=401, detail="Token inválido o no es un UUID de usuario")


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
