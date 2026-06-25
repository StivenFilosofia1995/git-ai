from datetime import datetime, timezone, timedelta
from typing import List

from app.database import supabase
from app.schemas.busqueda import BusquedaRequest, BusquedaResponse, ResultadoBusqueda
from app.services.ml_utils import (
    multi_field_bm25,
    tokenize,
    urgency_score,
    quality_score,
    activity_to_numeric,
    min_max_normalize,
)


def buscar(request: BusquedaRequest) -> BusquedaResponse:
    resultados: List[ResultadoBusqueda] = []

    if request.tipo in ("espacio", "todo"):
        resultados.extend(_buscar_espacios(request))

    if request.tipo in ("evento", "todo"):
        resultados.extend(_buscar_eventos(request))

    # Ordenar globalmente por similitud BM25 descendente antes de paginar
    resultados.sort(key=lambda r: r.similitud, reverse=True)

    return BusquedaResponse(
        resultados=resultados[: request.limit],
        total=len(resultados),
        query=request.q,
    )


def _buscar_espacios(request: BusquedaRequest) -> List[ResultadoBusqueda]:
    """
    Búsqueda de espacios con BM25 multi-campo.
    Campos ponderados:
      nombre            × 3.0  (identidad del lugar)
      categoria_principal × 2.0
      barrio            × 1.5  (zona)
      descripcion       × 1.0
    Bonus: activity_to_numeric(nivel_actividad) * 0.3
    """
    q = request.q
    query_tokens = tokenize(q)

    query = (
        supabase.table("lugares")
        .select("*")
        .neq("nivel_actividad", "cerrado")
        .or_(
            f"nombre.ilike.%{q}%,descripcion.ilike.%{q}%,barrio.ilike.%{q}%,"
            f"categoria_principal.ilike.%{q}%,municipio.ilike.%{q}%"
        )
        .limit(30)  # Traer más para que BM25 pueda reordenar bien
    )
    if request.municipio:
        query = query.eq("municipio", request.municipio)
    if request.categoria:
        query = query.contains("categorias", [request.categoria])

    response = query.execute()
    results = []
    for e in response.data:
        if e.get("lat") is not None and e.get("lng") is not None:
            e["coordenadas"] = {"lat": e["lat"], "lng": e["lng"]}
        else:
            e["coordenadas"] = None

        # BM25 multi-campo
        bm25 = multi_field_bm25(
            query_tokens,
            {
                "nombre":     (e.get("nombre") or "", 3.0),
                "categoria":  (e.get("categoria_principal") or "", 2.0),
                "barrio":     (e.get("barrio") or "", 1.5),
                "municipio":  (e.get("municipio") or "", 1.2),
                "descripcion":(e.get("descripcion") or e.get("descripcion_corta") or "", 1.0),
            },
        )
        # Bonus por nivel de actividad (espacios más activos suben en resultados)
        actividad_bonus = activity_to_numeric(e.get("nivel_actividad")) * 0.3

        similitud = bm25 + actividad_bonus
        results.append(ResultadoBusqueda(tipo="espacio", item=e, similitud=round(similitud, 4)))
    return results


def _buscar_eventos(request: BusquedaRequest) -> List[ResultadoBusqueda]:
    """
    Búsqueda de eventos con BM25 + urgency decay.

    Score final = BM25_multi_campo + urgency_score(días_hasta_evento) + quality_score

    Campos BM25:
      titulo       × 3.0
      nombre_lugar × 2.0
      barrio       × 1.5
      categoria    × 2.0
      descripcion  × 1.0
    """
    q = request.q
    query_tokens = tokenize(q)
    bogota_now = datetime.now(timezone(timedelta(hours=-5)))
    fecha_filtro = bogota_now.strftime("%Y-%m-%dT%H:%M:%S")

    query = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", fecha_filtro)
        .or_(
            f"titulo.ilike.%{q}%,descripcion.ilike.%{q}%,nombre_lugar.ilike.%{q}%,"
            f"categoria_principal.ilike.%{q}%,barrio.ilike.%{q}%,municipio.ilike.%{q}%"
        )
        .order("fecha_inicio")
        .limit(40)  # Traer más para reordenar con ML
    )
    if request.municipio:
        query = query.eq("municipio", request.municipio)
    if request.categoria:
        query = query.contains("categorias", [request.categoria])

    response = query.execute()
    results = []
    for e in response.data:
        # BM25 multi-campo
        bm25 = multi_field_bm25(
            query_tokens,
            {
                "titulo":       (e.get("titulo") or "", 3.0),
                "nombre_lugar": (e.get("nombre_lugar") or "", 2.0),
                "categoria":    (e.get("categoria_principal") or "", 2.0),
                "barrio":       (e.get("barrio") or "", 1.5),
                "descripcion":  (e.get("descripcion") or "", 1.0),
            },
        )
        # Urgencia: eventos de hoy/mañana aparecen primero si relevancia similar
        days_until = 0.0
        try:
            fecha_str = e.get("fecha_inicio") or ""
            if fecha_str:
                ev_dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                days_until = max(0.0, (ev_dt.replace(tzinfo=None) - bogota_now.replace(tzinfo=None)).total_seconds() / 86400)
        except Exception:
            pass
        urgencia = urgency_score(days_until, weight=1.5, decay=7.0)

        # Calidad: imagen, descripción, gratuito
        calidad = quality_score(e) * 0.2

        similitud = bm25 + urgencia + calidad
        results.append(ResultadoBusqueda(tipo="evento", item=e, similitud=round(similitud, 4)))
    return results
