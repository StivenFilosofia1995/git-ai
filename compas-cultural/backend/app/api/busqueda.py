from fastapi import APIRouter
from app.schemas import BusquedaRequest, BusquedaResponse
from app.services import busqueda_service

router = APIRouter()


@router.get("/", response_model=BusquedaResponse)
def buscar(
    q: str,
    tipo: str = "todo",
    municipio: str = None,
    categoria: str = None,
    limit: int = 20,
    offset: int = 0,
):
    request = BusquedaRequest(q=q, tipo=tipo, municipio=municipio, categoria=categoria, limit=limit, offset=offset)
    return busqueda_service.buscar(request)