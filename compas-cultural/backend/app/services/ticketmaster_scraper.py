"""
Ticketmaster Discovery API — eventos en Colombia/Medellín.

API gratuita: 5 000 llamadas/día, sin tarjeta de crédito.
Registro: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/

Configura en .env:
  TICKETMASTER_API_KEY=tu_clave_aqui

Si la clave no está configurada, el scraper retorna [] sin errores.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.database import supabase
from app.services.auto_scraper import _slugify, _sanitize_payload, CO_TZ, _now_co

BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

CATEGORY_MAP: dict[str, str] = {
    "Music": "musica_en_vivo",
    "Arts & Theatre": "teatro",
    "Film": "cine",
    "Sports": "otro",
    "Family": "festival",
    "Miscellaneous": "otro",
    "Dance/Electronic": "electronica",
    "Classical": "musica_en_vivo",
    "Jazz": "jazz",
    "Hip-Hop/Rap": "hip_hop",
    "Rock": "rock",
    "Metal": "metal",
}

MEDELLIN_QUERIES = [
    {"city": "Medellín", "stateCode": "ANT", "countryCode": "CO"},
    {"city": "Medellin", "stateCode": "ANT", "countryCode": "CO"},
    {"city": "Envigado", "stateCode": "ANT", "countryCode": "CO"},
    {"city": "Bello", "stateCode": "ANT", "countryCode": "CO"},
]


def _get_api_key() -> Optional[str]:
    return getattr(settings, "ticketmaster_api_key", None) or None


def _map_category(segment: str, genre: str) -> str:
    if genre:
        for key, val in CATEGORY_MAP.items():
            if key.lower() in genre.lower():
                return val
    if segment:
        for key, val in CATEGORY_MAP.items():
            if key.lower() in segment.lower():
                return val
    return "festival"


async def _fetch_events_page(params: dict) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(BASE_URL, params=params)
            if resp.status_code != 200:
                print(f"  [TM] HTTP {resp.status_code}: {resp.text[:200]}")
                return []
            data = resp.json()
            return data.get("_embedded", {}).get("events", [])
    except Exception as e:
        print(f"  [TM] Fetch error: {e}")
        return []


def _parse_tm_event(item: dict, municipio: str) -> Optional[dict]:
    nombre = (item.get("name") or "").strip()
    if not nombre:
        return None

    dates = item.get("dates", {})
    start = dates.get("start", {})
    date_str = start.get("dateTime") or start.get("localDate")
    if not date_str:
        return None

    try:
        if "T" in date_str:
            fecha = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            fecha = datetime.fromisoformat(date_str)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=CO_TZ)
        else:
            fecha = fecha.astimezone(CO_TZ)
    except (ValueError, TypeError):
        return None

    now_co = _now_co()
    if fecha < now_co:
        return None

    hora_confirmada = bool(start.get("dateTime"))

    classifications = item.get("classifications", [{}])
    segment = (classifications[0].get("segment", {}) or {}).get("name", "")
    genre = (classifications[0].get("genre", {}) or {}).get("name", "")
    categoria = _map_category(segment, genre)

    venues = item.get("_embedded", {}).get("venues", [{}])
    venue = venues[0] if venues else {}
    nombre_lugar = (venue.get("name") or "").strip() or nombre
    barrio = None
    city = (venue.get("city", {}) or {}).get("name", municipio)

    images = item.get("images", [])
    imagen_url = None
    for img in images:
        if img.get("ratio") == "16_9" and img.get("width", 0) >= 640:
            imagen_url = img.get("url")
            break
    if not imagen_url and images:
        imagen_url = images[0].get("url")

    url = item.get("url", "")
    price_ranges = item.get("priceRanges", [])
    precio_str = None
    es_gratuito = False
    if price_ranges:
        pr = price_ranges[0]
        mn = pr.get("min", 0)
        mx = pr.get("max", 0)
        currency = pr.get("currency", "COP")
        if mn == 0 and mx == 0:
            es_gratuito = True
            precio_str = "Entrada libre"
        else:
            precio_str = f"{currency} {int(mn):,}–{int(mx):,}"

    descripcion = f"Evento en {nombre_lugar}"
    slug = f"{_slugify(nombre)}-{fecha.strftime('%Y-%m-%d')}"

    return _sanitize_payload({
        "titulo": nombre[:200],
        "slug": slug,
        "espacio_id": None,
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": None,
        "hora_confirmada": hora_confirmada,
        "categorias": [categoria],
        "categoria_principal": categoria,
        "municipio": city.lower() if city else municipio,
        "barrio": barrio,
        "nombre_lugar": nombre_lugar[:150],
        "descripcion": descripcion,
        "precio": precio_str,
        "es_gratuito": es_gratuito,
        "es_recurrente": False,
        "imagen_url": imagen_url,
        "fuente": "ticketmaster_api",
        "fuente_url": url or None,
        "verificado": False,
    })


async def run_ticketmaster_scraper(days_ahead: int = 60) -> dict:
    """Obtiene eventos de Ticketmaster para el Valle de Aburrá.

    Retorna stats: {nuevos, duplicados, errores}
    """
    api_key = _get_api_key()
    if not api_key:
        print("  [TM] TICKETMASTER_API_KEY no configurada — saltando")
        return {"nuevos": 0, "duplicados": 0, "errores": 0, "omitido": True}

    now_co = _now_co()
    start_dt = now_co.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_dt = (now_co + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {"nuevos": 0, "duplicados": 0, "errores": 0}

    for location in MEDELLIN_QUERIES:
        params = {
            "apikey": api_key,
            "startDateTime": start_dt,
            "endDateTime": end_dt,
            "size": 50,
            "locale": "es",
            **location,
        }
        municipio = location["city"].lower().replace("í", "i")
        events_raw = await _fetch_events_page(params)
        print(f"  [TM] {location['city']}: {len(events_raw)} eventos en bruto")

        for item in events_raw:
            try:
                evento = _parse_tm_event(item, municipio)
                if not evento:
                    continue

                slug = evento["slug"]
                existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
                if existing.data:
                    stats["duplicados"] += 1
                    continue

                supabase.table("eventos").insert(evento).execute()
                stats["nuevos"] += 1
                print(f"    ✅ [TM] {evento['titulo']}")
            except Exception as e:
                stats["errores"] += 1
                print(f"    ❌ [TM] Error: {e}")

        await asyncio.sleep(1)

    print(
        f"  [TM] Completado — nuevos: {stats['nuevos']} | "
        f"duplicados: {stats['duplicados']} | errores: {stats['errores']}"
    )
    return stats
