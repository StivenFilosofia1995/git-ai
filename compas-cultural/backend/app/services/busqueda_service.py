from datetime import datetime, timezone, timedelta
from typing import List

from app.database import supabase
from app.schemas.busqueda import BusquedaRequest, BusquedaResponse, ResultadoBusqueda


def buscar(request: BusquedaRequest) -> BusquedaResponse:
    resultados: List[ResultadoBusqueda] = []

    if request.tipo in ("espacio", "todo"):
        resultados.extend(_buscar_espacios(request))

    if request.tipo in ("evento", "todo"):
        resultados.extend(_buscar_eventos(request))

    return BusquedaResponse(
        resultados=resultados[: request.limit],
        total=len(resultados),
        query=request.q,
    )


def _buscar_espacios(request: BusquedaRequest) -> List[ResultadoBusqueda]:
    q = request.q
    query = (
        supabase.table("lugares")
        .select("*")
        .neq("nivel_actividad", "cerrado")
        .or_(
            f"nombre.ilike.%{q}%,descripcion.ilike.%{q}%,barrio.ilike.%{q}%,categoria_principal.ilike.%{q}%"
        )
        .limit(10)
    )
    if request.municipio:
        query = query.eq("municipio", request.municipio)
    if request.categoria:
        query = query.contains("categorias", [request.categoria])

    response = query.execute()
    results = []
    for e in response.data:
        # Add coordenadas for frontend
        if e.get("lat") is not None and e.get("lng") is not None:
            e["coordenadas"] = {"lat": e["lat"], "lng": e["lng"]}
        else:
            e["coordenadas"] = None
        results.append(ResultadoBusqueda(tipo="espacio", item=e, similitud=0.8))
    return results


def _buscar_eventos(request: BusquedaRequest) -> List[ResultadoBusqueda]:
    q = request.q
    # Usar hora Colombia (UTC-5) para no filtrar eventos válidos
    bogota_now = datetime.now(timezone(timedelta(hours=-5)))
    fecha_filtro = bogota_now.strftime("%Y-%m-%dT%H:%M:%S")
    query = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", fecha_filtro)
        .or_(
            f"titulo.ilike.%{q}%,descripcion.ilike.%{q}%,nombre_lugar.ilike.%{q}%,categoria_principal.ilike.%{q}%,barrio.ilike.%{q}%,municipio.ilike.%{q}%"
        )
        .order("fecha_inicio")
        .limit(10)
    )
    if request.municipio:
        query = query.eq("municipio", request.municipio)
    if request.categoria:
        query = query.contains("categorias", [request.categoria])

    response = query.execute()
    return [
        ResultadoBusqueda(tipo="evento", item=e)
        for e in response.data
    ]
