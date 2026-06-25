"""
Eventbrite API v3 — eventos culturales en Colombia/Medellín.

API gratuita para eventos públicos.
Registro: https://www.eventbrite.com/platform/api

Configura en .env:
  EVENTBRITE_TOKEN=tu_token_aqui

Si el token no está configurado, el scraper retorna [] sin errores.

Cubre: talleres, charlas, festivales, teatro, música en vivo, exposiciones, etc.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.database import supabase
from app.services.auto_scraper import _slugify, _sanitize_payload, CO_TZ, _now_co

BASE_URL = "https://www.eventbriteapi.com/v3"

CATEGORY_MAP: dict[str, str] = {
    "103": "musica_en_vivo",
    "101": "negocio",
    "110": "comida",
    "113": "comunidad",
    "105": "artes",
    "107": "cine",
    "108": "conferencia",
    "109": "festival",
    "111": "gobierno",
    "114": "salud",
    "115": "bienestar",
    "116": "taller",
    "117": "religión",
    "118": "deporte",
    "199": "otro",
}

FORMAT_MAP: dict[str, str] = {
    "2": "taller",
    "3": "conferencia",
    "4": "festival",
    "5": "exhibicion",
    "6": "concierto",
    "7": "conferencia",
    "8": "screening",
    "9": "gala",
    "10": "carrera",
    "11": "party",
    "100": "otro",
}

MEDELLIN_LOCATIONS = [
    "Medellín,Colombia",
    "Envigado,Colombia",
    "Bello,Colombia",
    "Itagüí,Colombia",
    "Sabaneta,Colombia",
]


def _get_token() -> Optional[str]:
    return getattr(settings, "eventbrite_token", None) or None


def _resolve_category(cat_id: str, fmt_id: str) -> str:
    if cat_id in CATEGORY_MAP:
        return CATEGORY_MAP[cat_id]
    if fmt_id in FORMAT_MAP:
        return FORMAT_MAP[fmt_id]
    return "festival"


async def _fetch_events(token: str, location: str, start_date: str, end_date: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "location.address": location,
        "location.within": "30km",
        "start_date.range_start": start_date,
        "start_date.range_end": end_date,
        "expand": "venue,organizer,category,format",
        "page_size": 50,
    }
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(f"{BASE_URL}/events/search/", headers=headers, params=params)
            if resp.status_code == 401:
                print("  [EB] Token inválido o expirado")
                return []
            if resp.status_code != 200:
                print(f"  [EB] HTTP {resp.status_code}: {resp.text[:200]}")
                return []
            return resp.json().get("events", [])
    except Exception as e:
        print(f"  [EB] Fetch error for {location}: {e}")
        return []


def _parse_eb_event(item: dict, municipio: str) -> Optional[dict]:
    nombre = (item.get("name", {}) or {}).get("text", "").strip()
    if not nombre:
        return None

    start_info = item.get("start", {}) or {}
    date_str = start_info.get("utc") or start_info.get("local")
    if not date_str:
        return None

    try:
        if "Z" in date_str:
            fecha = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(CO_TZ)
        elif "+" in date_str or (len(date_str) > 19 and date_str[19] == "-"):
            fecha = datetime.fromisoformat(date_str).astimezone(CO_TZ)
        else:
            fecha = datetime.fromisoformat(date_str).replace(tzinfo=CO_TZ)
    except (ValueError, TypeError):
        return None

    now_co = _now_co()
    if fecha < now_co:
        return None

    end_info = item.get("end", {}) or {}
    fecha_fin = None
    end_str = end_info.get("utc") or end_info.get("local")
    if end_str:
        try:
            if "Z" in end_str:
                fecha_fin = datetime.fromisoformat(end_str.replace("Z", "+00:00")).astimezone(CO_TZ)
            elif "+" in end_str:
                fecha_fin = datetime.fromisoformat(end_str).astimezone(CO_TZ)
            else:
                fecha_fin = datetime.fromisoformat(end_str).replace(tzinfo=CO_TZ)
        except (ValueError, TypeError):
            fecha_fin = None

    cat_id = str((item.get("category") or {}).get("id", ""))
    fmt_id = str((item.get("format") or {}).get("id", ""))
    categoria = _resolve_category(cat_id, fmt_id)

    venue = item.get("venue") or {}
    venue_name = (venue.get("name") or "").strip() or nombre
    address = venue.get("address") or {}
    city = (address.get("city") or "").strip()

    logo = item.get("logo") or {}
    imagen_url = (logo.get("original") or {}).get("url") or (logo.get("url"))

    url = item.get("url", "")
    is_free = bool(item.get("is_free"))
    ticket_info = item.get("ticket_availability") or {}
    min_price = ticket_info.get("minimum_ticket_price") or {}
    precio_str = None
    if is_free:
        precio_str = "Entrada libre"
    elif min_price.get("major_value"):
        currency = min_price.get("currency", "COP")
        precio_str = f"{currency} {min_price['major_value']}"

    descripcion = (item.get("description", {}) or {}).get("text") or f"Evento en {venue_name}"
    if len(descripcion) > 500:
        descripcion = descripcion[:497] + "…"

    slug = f"{_slugify(nombre)}-{fecha.strftime('%Y-%m-%d')}"

    return _sanitize_payload({
        "titulo": nombre[:200],
        "slug": slug,
        "espacio_id": None,
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
        "hora_confirmada": True,
        "categorias": [categoria],
        "categoria_principal": categoria,
        "municipio": (city or municipio).lower(),
        "barrio": None,
        "nombre_lugar": venue_name[:150],
        "descripcion": descripcion,
        "precio": precio_str,
        "es_gratuito": is_free,
        "es_recurrente": False,
        "imagen_url": imagen_url,
        "fuente": "eventbrite_api",
        "fuente_url": url or None,
        "verificado": False,
    })


async def run_eventbrite_scraper(days_ahead: int = 60) -> dict:
    """Obtiene eventos de Eventbrite para el Valle de Aburrá.

    Retorna stats: {nuevos, duplicados, errores}
    """
    token = _get_token()
    if not token:
        print("  [EB] EVENTBRITE_TOKEN no configurado — saltando")
        return {"nuevos": 0, "duplicados": 0, "errores": 0, "omitido": True}

    now_co = _now_co()
    start_date = now_co.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = (now_co + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {"nuevos": 0, "duplicados": 0, "errores": 0}

    for location in MEDELLIN_LOCATIONS:
        municipio = location.split(",")[0].lower()
        municipio = municipio.replace("í", "i").replace("ü", "u")

        events_raw = await _fetch_events(token, location, start_date, end_date)
        print(f"  [EB] {location}: {len(events_raw)} eventos en bruto")

        for item in events_raw:
            try:
                evento = _parse_eb_event(item, municipio)
                if not evento:
                    continue

                slug = evento["slug"]
                existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
                if existing.data:
                    stats["duplicados"] += 1
                    continue

                supabase.table("eventos").insert(evento).execute()
                stats["nuevos"] += 1
                print(f"    ✅ [EB] {evento['titulo']}")
            except Exception as e:
                stats["errores"] += 1
                print(f"    ❌ [EB] Error: {e}")

        await asyncio.sleep(1)

    print(
        f"  [EB] Completado — nuevos: {stats['nuevos']} | "
        f"duplicados: {stats['duplicados']} | errores: {stats['errores']}"
    )
    return stats
