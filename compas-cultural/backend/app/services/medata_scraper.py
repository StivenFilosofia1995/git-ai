# -*- coding: utf-8 -*-
"""
MEData Scraper — Datos Abiertos Alcaldía de Medellín (medata.gov.co)
CKAN API — completamente gratuito, sin registro, sin API key.

Portal:   https://medata.gov.co/
API base: https://medata.gov.co/api/3/action/
"""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.database import supabase

MEDATA_BASE = "https://medata.gov.co/api/3/action"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CulturaEtereaScraper/1.0)",
    "Accept": "application/json",
}

_SEARCH_TERMS = [
    "agenda cultural medellin",
    "eventos culturales medellin",
    "programacion cultural",
    "cultura ciudadana medellin",
]

# CKAN column name → schema field
_FIELD_MAP = {
    # Title
    "titulo": "titulo", "nombre_evento": "titulo", "nombre": "titulo",
    "evento": "titulo", "actividad": "titulo", "nombre_actividad": "titulo",
    # Date
    "fecha_inicio": "fecha_inicio", "fecha_evento": "fecha_inicio",
    "fecha": "fecha_inicio", "fecha_inicio_evento": "fecha_inicio",
    "fecha_programacion": "fecha_inicio",
    # End date
    "fecha_fin": "fecha_fin", "fecha_finalizacion": "fecha_fin",
    "fecha_fin_evento": "fecha_fin",
    # Time
    "hora_inicio": "hora_inicio", "hora": "hora_inicio",
    "hora_inicio_evento": "hora_inicio",
    # Description
    "descripcion": "descripcion", "descripcion_evento": "descripcion",
    "resumen": "descripcion", "sinopsis": "descripcion",
    # Location
    "nombre_lugar": "nombre_lugar", "lugar": "nombre_lugar",
    "espacio": "nombre_lugar", "equipamiento": "nombre_lugar",
    "nombre_equipamiento": "nombre_lugar", "salon": "nombre_lugar",
    "direccion": "direccion", "direccion_evento": "direccion",
    # Barrio / commune
    "barrio": "barrio", "nombre_barrio": "barrio",
    "comuna": "barrio", "nombre_comuna": "barrio",
    # Category
    "tipo_evento": "categoria", "categoria": "categoria",
    "tipo": "categoria", "linea_programatica": "categoria",
    "linea": "categoria", "genero": "categoria",
    # URL / image
    "url": "fuente_url", "enlace": "fuente_url", "link": "fuente_url",
    "url_evento": "fuente_url",
    "imagen": "imagen_url", "imagen_url": "imagen_url", "foto": "imagen_url",
    "url_imagen": "imagen_url",
    # Price
    "precio": "precio", "valor": "precio", "costo": "precio",
    "valor_boletin": "precio",
}

_CATEGORIA_MAP = {
    "teatro": "teatro", "danza": "danza",
    "música": "musica_en_vivo", "musica": "musica_en_vivo",
    "cine": "cine", "literatura": "literatura",
    "artes visuales": "galeria", "arte": "arte_contemporaneo",
    "galería": "galeria", "galeria": "galeria",
    "festival": "festival", "taller": "taller",
    "conferencia": "conferencia", "circo": "circo",
    "hip hop": "hip_hop", "electronica": "electronica",
    "jazz": "jazz",
    "fotografía": "fotografia", "fotografia": "fotografia",
}

_GRATUITO_KEYWORDS = {"gratis", "gratuito", "libre", "sin costo", "entrada libre", "0", "$0", ""}


def _slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:200]


def _parse_date(value) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})$", s)
    if m:
        return f"20{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _map_categoria(raw: str) -> str:
    if not raw:
        return "otro"
    clean = raw.lower().strip()
    for key, cat in _CATEGORIA_MAP.items():
        if key in clean:
            return cat
    return "otro"


def _sanitize(payload: dict) -> dict:
    clean = {}
    for k, v in payload.items():
        if isinstance(v, str):
            try:
                v = v.encode("utf-8", "replace").decode("utf-8")
            except Exception:
                v = ""
        clean[k] = v
    return clean


async def _search_datasets(term: str) -> list[dict]:
    url = f"{MEDATA_BASE}/package_search"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, params={"q": term, "rows": 5}, headers=_HEADERS)
            resp.raise_for_status()
            return resp.json().get("result", {}).get("results", [])
    except Exception as e:
        print(f"  [MEData] Error buscando '{term}': {e}")
        return []


async def _fetch_resource_records(resource_id: str, limit: int = 500) -> list[dict]:
    url = f"{MEDATA_BASE}/datastore_search"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                url, params={"resource_id": resource_id, "limit": limit}, headers=_HEADERS
            )
            resp.raise_for_status()
            return resp.json().get("result", {}).get("records", [])
    except Exception as e:
        print(f"  [MEData] Error leyendo resource {resource_id[:12]}: {e}")
        return []


def _row_to_event(row: dict, dataset_name: str, resource_url: str) -> Optional[dict]:
    norm = {k.lower().strip(): str(v).strip() for k, v in row.items() if v not in (None, "", "null")}

    mapped: dict = {}
    for ckan_key, our_key in _FIELD_MAP.items():
        if ckan_key in norm:
            mapped.setdefault(our_key, norm[ckan_key])

    titulo = mapped.get("titulo") or dataset_name
    if not titulo or len(titulo.strip()) < 3:
        return None

    fecha = _parse_date(mapped.get("fecha_inicio"))
    if not fecha:
        return None

    now_co = datetime.utcnow() - timedelta(hours=5)
    try:
        event_dt = datetime.fromisoformat(fecha)
        if event_dt < now_co - timedelta(days=7):
            return None
        if event_dt > now_co + timedelta(days=365):
            return None
    except Exception:
        return None

    hora = mapped.get("hora_inicio", "")
    if hora and re.match(r"\d{1,2}:\d{2}", hora):
        fecha = f"{fecha}T{hora.zfill(5)}:00"

    fecha_fin = _parse_date(mapped.get("fecha_fin"))
    categoria = _map_categoria(mapped.get("categoria", ""))
    nombre_lugar = mapped.get("nombre_lugar") or "Medellín"
    barrio = mapped.get("barrio") or None
    precio = mapped.get("precio") or ""
    es_gratuito = precio.lower().strip() in _GRATUITO_KEYWORDS
    descripcion = (mapped.get("descripcion") or "")[:500] or None
    fuente_url = mapped.get("fuente_url") or resource_url
    imagen_url = mapped.get("imagen_url") or None
    fecha_slug = fecha[:10] if len(fecha) >= 10 else fecha
    slug = f"{_slugify(titulo)}-{fecha_slug}"

    return {
        "titulo": titulo[:200],
        "slug": slug,
        "fecha_inicio": fecha,
        "fecha_fin": fecha_fin,
        "categorias": [categoria],
        "categoria_principal": categoria,
        "municipio": "medellin",
        "barrio": barrio,
        "nombre_lugar": nombre_lugar[:200],
        "descripcion": descripcion,
        "imagen_url": imagen_url,
        "precio": precio[:100] if precio else None,
        "es_gratuito": es_gratuito,
        "es_recurrente": False,
        "fuente": "medata_medellin",
        "fuente_url": fuente_url,
        "verificado": True,
        "espacio_id": None,
    }


def _is_event_resource(resource: dict) -> bool:
    name = (resource.get("name") or "").lower()
    desc = (resource.get("description") or "").lower()
    fmt = (resource.get("format") or "").lower()
    combined = name + " " + desc
    keywords = {"agenda", "evento", "programac", "cultural", "actividad", "calendario"}
    return (
        fmt in ("csv", "json", "xlsx", "xls", "")
        and any(kw in combined for kw in keywords)
        and resource.get("datastore_active", False)
    )


async def run_medata_scraper() -> dict:
    """
    Busca datasets culturales en MEData (CKAN Alcaldía de Medellín) e ingesta eventos.
    Sin API key — completamente gratuito.
    """
    print("\n🏛️  MEData — Datos Abiertos Alcaldía de Medellín...")

    seen_datasets: set = set()
    all_events: list[dict] = []

    for term in _SEARCH_TERMS:
        datasets = await _search_datasets(term)
        for dataset in datasets:
            ds_id = dataset.get("id", "")
            if ds_id in seen_datasets:
                continue
            seen_datasets.add(ds_id)

            ds_name = dataset.get("title") or dataset.get("name", "Agenda Cultural")
            resources = dataset.get("resources", [])

            for resource in resources:
                if not _is_event_resource(resource):
                    continue
                resource_id = resource.get("id", "")
                if not resource_id:
                    continue
                resource_url = resource.get("url") or f"https://medata.gov.co/dataset/{ds_id}"
                print(f"  [MEData] {ds_name[:50]} | resource {resource_id[:12]}...")

                records = await _fetch_resource_records(resource_id)
                for row in records:
                    ev = _row_to_event(row, ds_name, resource_url)
                    if ev:
                        all_events.append(ev)

    if not all_events:
        print("  [MEData] Sin eventos en datasets CKAN")
        return {"nuevos": 0, "duplicados": 0, "errores": 0}

    print(f"  [MEData] {len(all_events)} candidatos — insertando...")

    nuevos = duplicados = errores = 0
    seen_slugs: set = set()

    for ev in all_events:
        slug = ev.get("slug", "")
        if slug in seen_slugs:
            duplicados += 1
            continue
        seen_slugs.add(slug)

        try:
            res = supabase.table("eventos").upsert(_sanitize(ev), on_conflict="slug").execute()
            if res.data:
                nuevos += 1
        except Exception as e:
            print(f"  [MEData] Insert error: {e}")
            errores += 1

    print(f"  [MEData] Listo — nuevos={nuevos} duplicados={duplicados} errores={errores}")
    return {"nuevos": nuevos, "duplicados": duplicados, "errores": errores}
