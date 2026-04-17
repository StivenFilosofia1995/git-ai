import math
from typing import List, Optional

from app.database import supabase


def get_espacios(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    nivel_actividad: Optional[str] = None,
    es_underground: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[dict]:
    query = supabase.table("lugares").select("*").neq("nivel_actividad", "cerrado")

    if municipio:
        query = query.eq("municipio", municipio)
    if barrio:
        query = query.ilike("barrio", f"%{barrio}%")
    if categoria:
        query = query.contains("categorias", [categoria])
    if nivel_actividad:
        query = query.eq("nivel_actividad", nivel_actividad)
    if es_underground is not None:
        query = query.eq("es_underground", es_underground)

    response = query.limit(limit).range(offset, offset + limit - 1).execute()
    return _add_coordenadas(response.data)


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
        d = _haversine(lat, lng, e["lat"], e["lng"])
        if d <= radio_metros:
            cerca.append({
                "nombre": e["nombre"],
                "slug": e["slug"],
                "categoria_principal": e["categoria_principal"],
                "barrio": e.get("barrio"),
                "direccion": e.get("direccion"),
                "distancia_metros": round(d),
            })
    cerca.sort(key=lambda x: x["distancia_metros"])
    return cerca[:20]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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