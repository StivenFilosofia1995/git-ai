import math
from typing import List, Optional

from app.database import supabase
from app.services.ml_utils import (
    activity_to_numeric,
    quality_score,
    haversine_km,
    geo_score,
    multi_field_bm25,
    tokenize,
    log1p_score,
)


def _score_espacio_ml(
    espacio: dict,
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    categoria: Optional[str] = None,
    texto: Optional[str] = None,
) -> float:
    """
    Score ML compuesto para un espacio cultural.

    Componentes:
      f_actividad = activity_to_numeric(nivel) ∈ [0,4]
        muy_activo=4, activo=2.5, regular=1.5, inactivo=0.5
      f_geo       = 5 * e^(-dist_km / 5)  si lat/lng conocidos
      f_categoria = +2.0 si categoría coincide
      f_calidad   = quality_score(espacio) ∈ [0,4]
      f_texto     = BM25 multi-campo si hay query
      f_social    = +0.5 si tiene instagram o sitio web
    """
    f_actividad = activity_to_numeric(espacio.get("nivel_actividad"))

    f_geo = 0.0
    if lat is not None and lng is not None:
        e_lat = espacio.get("lat")
        e_lng = espacio.get("lng")
        if e_lat is not None and e_lng is not None:
            dist = haversine_km(lat, lng, float(e_lat), float(e_lng))
            f_geo = geo_score(dist, sigma_km=5.0, weight=5.0)

    f_categoria = 0.0
    if categoria:
        cat_norm = categoria.lower().replace("_", " ")
        if (espacio.get("categoria_principal") or "").lower().replace("_", " ") == cat_norm:
            f_categoria = 2.0
        elif categoria in (espacio.get("categorias") or []):
            f_categoria = 1.0

    f_calidad = quality_score(espacio)

    f_texto = 0.0
    if texto:
        f_texto = multi_field_bm25(
            tokenize(texto),
            {
                "nombre":     (espacio.get("nombre") or "", 3.0),
                "categoria":  (espacio.get("categoria_principal") or "", 2.0),
                "barrio":     (espacio.get("barrio") or "", 1.5),
                "descripcion":(espacio.get("descripcion") or espacio.get("descripcion_corta") or "", 1.0),
            },
        )

    f_social = 0.5 if (espacio.get("instagram_handle") or espacio.get("sitio_web")) else 0.0

    return f_actividad + f_geo + f_categoria + f_calidad + f_texto + f_social


def get_espacios(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    nivel_actividad: Optional[str] = None,
    es_underground: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    tipo: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    texto: Optional[str] = None,
) -> List[dict]:
    query = supabase.table("lugares").select("*").neq("nivel_actividad", "cerrado")

    if municipio:
        query = query.eq("municipio", municipio)
    if barrio:
        query = query.ilike("barrio", f"%{barrio}%")
    if categoria:
        # Match if categoria_principal equals OR categorias array contains the value
        query = query.or_(f"categoria_principal.eq.{categoria},categorias.cs.{{{categoria}}}")
    if tipo:
        query = query.eq("tipo", tipo)
    if nivel_actividad:
        query = query.eq("nivel_actividad", nivel_actividad)
    if es_underground is not None:
        query = query.eq("es_underground", es_underground)

    # Traer más para que ML pueda reordenar
    fetch_limit = min(limit * 3, 120)
    response = query.limit(fetch_limit).execute()
    espacios = _add_coordenadas(response.data)

    # ML post-ranking: ordenar por score compuesto
    espacios.sort(
        key=lambda e: _score_espacio_ml(e, lat=lat, lng=lng, categoria=categoria, texto=texto),
        reverse=True,
    )

    # Paginar después del ranking
    return espacios[offset: offset + limit]


def get_espacio_by_slug(slug: str) -> dict:
    response = (
        supabase.table("lugares")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )
    return _add_coord_single(response.data)


def get_espacios_cerca(
    lat: float,
    lng: float,
    radio_metros: int = 2000,
) -> List[dict]:
    response = (
        supabase.table("lugares")
        .select("*")
        .neq("nivel_actividad", "cerrado")
        .not_.is_("lat", "null")
        .not_.is_("lng", "null")
        .execute()
    )
    cerca = []
    for e in response.data:
        d_km = haversine_km(lat, lng, e["lat"], e["lng"])
        d_metros = d_km * 1000
        if d_metros <= radio_metros:
            cerca.append({
                "nombre": e["nombre"],
                "slug": e["slug"],
                "categoria_principal": e["categoria_principal"],
                "barrio": e.get("barrio"),
                "direccion": e.get("direccion"),
                "distancia_metros": round(d_metros),
                # ML: score combinado proximidad + actividad para ordenar
                "score_ml": geo_score(d_km, sigma_km=2.0) + activity_to_numeric(e.get("nivel_actividad")) * 0.5,
            })
    # Ordenar por score ML (proximidad + actividad), no solo por distancia plana
    cerca.sort(key=lambda x: x["score_ml"], reverse=True)
    for item in cerca:
        item.pop("score_ml", None)
    return cerca[:20]


def _add_coordenadas(rows: List[dict]) -> List[dict]:
    for r in rows:
        r["coordenadas"] = (
            {"lat": r["lat"], "lng": r["lng"]}
            if r.get("lat") is not None and r.get("lng") is not None
            else None
        )
    return rows


def _add_coord_single(row: dict) -> dict:
    row["coordenadas"] = (
        {"lat": row["lat"], "lng": row["lng"]}
        if row.get("lat") is not None and row.get("lng") is not None
        else None
    )
    return row