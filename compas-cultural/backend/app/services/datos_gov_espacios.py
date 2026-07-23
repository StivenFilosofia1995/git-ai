# -*- coding: utf-8 -*-
"""
datos.gov.co — Espacios de las Artes, las Culturas y los Saberes (PULEP/SINIC)
Dataset: te39-v28f
API: https://www.datos.gov.co/resource/te39-v28f.json (Socrata SODA, sin key para <1000 registros)

Importa venues culturales con coordenadas para enriquecer el mapa.
"""
import re
import unicodedata
from typing import Optional

import httpx

from app.database import supabase

SOCRATA_URL = "https://www.datos.gov.co/resource/te39-v28f.json"

_HEADERS = {
    "User-Agent": "CulturaEtereaScraper/1.0",
    "Accept": "application/json",
}

# Mapa tipo_lugar → categoria_principal de nuestra BD
_TIPO_TO_CAT: dict[str, str] = {
    "teatro":             "teatro",
    "sala de teatro":     "teatro",
    "sala teatro":        "teatro",
    "biblioteca":         "libreria",
    "biblioteca pública": "libreria",
    "casa de cultura":    "casa_cultura",
    "casa cultura":       "casa_cultura",
    "centro cultural":    "centro_cultural",
    "centro de creación": "arte_contemporaneo",
    "sala de exposición": "galeria",
    "galería":            "galeria",
    "galeria":            "galeria",
    "circo":              "circo",
    "carpa de circo":     "circo",
    "sala de cine":       "cine",
    "cine":               "cine",
    "sala de música":     "musica_en_vivo",
    "sala música":        "musica_en_vivo",
    "sala de danza":      "danza",
    "sala danza":         "danza",
}

MUNICIPIOS_VALLE = {
    "medellín", "medellin",
    "bello", "itagüí", "itagui", "envigado",
    "sabaneta", "la estrella", "caldas",
    "copacabana", "girardota", "barbosa",
}


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:250]


def _normalize_municipio(raw: str) -> str:
    t = unicodedata.normalize("NFD", raw.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").replace(" ", "_")


def _cat(tipo: Optional[str]) -> str:
    if not tipo:
        return "espacio_hibrido"
    key = tipo.lower().strip()
    return _TIPO_TO_CAT.get(key, "espacio_hibrido")


async def import_datos_gov_espacios(departamento: str = "Antioquia", limit: int = 500) -> dict:
    params = {
        "departamento": departamento,
        "$limit": limit,
        "$offset": 0,
    }

    stats = {"nuevos": 0, "existentes": 0, "sin_coords": 0, "errores": 0, "total": 0}

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30) as client:
        resp = await client.get(SOCRATA_URL, params=params)
        resp.raise_for_status()
        registros = resp.json()

    stats["total"] = len(registros)

    for r in registros:
        municipio_raw = r.get("municipio") or r.get("nom_mpio") or ""
        municipio_norm = _normalize_municipio(municipio_raw)

        # Solo municipios del Valle de Aburrá
        municipio_clean = municipio_raw.lower().strip()
        if not any(m in municipio_clean for m in MUNICIPIOS_VALLE):
            continue

        nombre = (r.get("nombre") or "").strip()
        if not nombre:
            continue

        lat = None
        lng = None
        # Try top-level lat/lng fields first
        try:
            lat = float(r.get("latitud") or r.get("lat") or 0) or None
            lng = float(r.get("longitud") or r.get("lng") or 0) or None
        except (ValueError, TypeError):
            pass

        # Try nested coordenadas field (GeoJSON point)
        if not lat:
            coords = r.get("coordenadas") or {}
            if isinstance(coords, dict) and coords.get("type") == "Point":
                coords_arr = coords.get("coordinates", [])
                if len(coords_arr) == 2:
                    try:
                        lng = float(coords_arr[0])
                        lat = float(coords_arr[1])
                    except (ValueError, TypeError):
                        pass

        if not lat or not lng:
            stats["sin_coords"] += 1
            continue

        slug = _slug(nombre)

        # Check if already exists
        existing = supabase.table("espacios").select("id").eq("slug", slug).execute()
        if existing.data:
            stats["existentes"] += 1
            continue

        cat = _cat(r.get("tipo_lugar"))
        descripcion = (r.get("descripcion") or r.get("observaciones") or "").strip()[:500]

        espacio_data = {
            "nombre": nombre[:200],
            "slug": slug,
            "categoria_principal": cat,
            "municipio": municipio_norm,
            "lat": lat,
            "lng": lng,
            "descripcion": descripcion or None,
            "fuente": "datos_gov_co_te39v28f",
            "es_equipamiento_publico": cat in {"libreria", "casa_cultura", "centro_cultural"},
            "verificado": False,
        }

        try:
            supabase.table("espacios").insert(espacio_data).execute()
            stats["nuevos"] += 1
        except Exception as e:
            print(f"[datos_gov] Error insertando {nombre}: {e}")
            stats["errores"] += 1

    return stats
