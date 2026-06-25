"""
Bandsintown API — conciertos y música en vivo en Colombia/Medellín.

API completamente gratuita, sin registro, sin tarjeta.
Documentación: https://app.bandsintown.com/api

Busca eventos por artista. Para la agenda general de Medellín,
usa una lista curada de artistas colombianos/locales activos.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.database import supabase
from app.services.auto_scraper import _slugify, _sanitize_payload, CO_TZ, _now_co

BASE_URL = "https://rest.bandsintown.com"
APP_ID = "cultura-eterea"

# Artistas colombianos frecuentes en Medellín (búsqueda complementaria)
ARTISTAS_CO = [
    "Systema Solar", "ChocQuibTown", "Bomba Estéreo", "Monsieur Periné",
    "Sidestepper", "Meridian Brothers", "The Mills", "Aterciopelados",
    "Carlos Vives", "Shakira", "Maluma", "J Balvin", "Karol G",
    "Diamante Eléctrico", "Kraken", "Don Tetto", "Los Pirañas",
    "Dani Boom", "Herencia de Timbiqui", "La Perla",
    "Ondatrópica", "Curupira", "Mechato",
    "Telecom Folie", "El Diablo Suelto", "Tribu Baharú",
    "Teto Ocampo", "Jacobo Vélez", "Velvet Underground Medellín",
    "Bloque Depresivo", "Ekhymosis",
]


async def _fetch_artist_events(artist: str, date_from: str, date_to: str) -> list[dict]:
    artist_encoded = artist.replace(" ", "%20").replace("/", "%2F")
    url = f"{BASE_URL}/artists/{artist_encoded}/events"
    params = {
        "app_id": APP_ID,
        "date": f"{date_from},{date_to}",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            if resp.status_code in (404, 400):
                return []
            if resp.status_code != 200:
                print(f"  [BIT] HTTP {resp.status_code} para {artist}")
                return []
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                return []
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  [BIT] Error fetching {artist}: {e}")
        return []


def _is_colombia_event(item: dict) -> tuple[bool, str]:
    """Retorna (es_colombia, municipio)."""
    venue = item.get("venue") or {}
    country = (venue.get("country") or "").strip()
    city = (venue.get("city") or "").strip()

    if not country:
        return False, ""

    if country.lower() not in ("colombia", "co"):
        return False, ""

    city_lower = city.lower()
    if any(m in city_lower for m in ["medell", "enviga", "itagui", "bello", "sabaneta"]):
        for mun in ["medellin", "envigado", "itagui", "bello", "sabaneta"]:
            if mun[:5] in city_lower:
                return True, mun
        return True, "medellin"

    return True, city.lower()


def _parse_bit_event(item: dict, artist_name: str) -> Optional[dict]:
    title = (item.get("title") or "").strip()
    if not title:
        title = f"{artist_name} en vivo"

    date_str = item.get("datetime") or item.get("starts_at")
    if not date_str:
        return None

    try:
        if "Z" in date_str:
            fecha = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(CO_TZ)
        elif "+" in date_str:
            fecha = datetime.fromisoformat(date_str).astimezone(CO_TZ)
        else:
            fecha = datetime.fromisoformat(date_str).replace(tzinfo=CO_TZ)
    except (ValueError, TypeError):
        return None

    now_co = _now_co()
    if fecha < now_co:
        return None

    venue = item.get("venue") or {}
    venue_name = (venue.get("name") or "").strip() or "Por confirmar"
    city = (venue.get("city") or "medellin").lower()

    offers = item.get("offers") or []
    url = ""
    es_gratuito = True
    precio_str = "Entrada libre"
    for offer in offers:
        if offer.get("url"):
            url = offer["url"]
        if offer.get("type") == "Tickets":
            es_gratuito = False
            precio_str = "Boletas disponibles"
            break

    lineup = item.get("lineup") or [artist_name]
    artistas_str = ", ".join(lineup[:5])
    descripcion = f"{artistas_str} en {venue_name}"
    if len(descripcion) > 300:
        descripcion = descripcion[:297] + "…"

    slug = f"{_slugify(title)}-{fecha.strftime('%Y-%m-%d')}"

    return _sanitize_payload({
        "titulo": title[:200],
        "slug": slug,
        "espacio_id": None,
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": None,
        "hora_confirmada": True,
        "categorias": ["musica_en_vivo"],
        "categoria_principal": "musica_en_vivo",
        "municipio": city,
        "barrio": None,
        "nombre_lugar": venue_name[:150],
        "descripcion": descripcion,
        "precio": precio_str,
        "es_gratuito": es_gratuito,
        "es_recurrente": False,
        "imagen_url": item.get("image_url"),
        "fuente": "bandsintown_api",
        "fuente_url": url or f"https://bandsintown.com/e/{item.get('id', '')}",
        "verificado": False,
    })


async def run_bandsintown_scraper(days_ahead: int = 90) -> dict:
    """Obtiene conciertos de Bandsintown para artistas activos en Colombia.

    Completamente gratuito, sin API key.
    Retorna stats: {nuevos, duplicados, errores}
    """
    now_co = _now_co()
    date_from = now_co.strftime("%Y-%m-%d")
    date_to = (now_co + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    stats = {"nuevos": 0, "duplicados": 0, "errores": 0}

    for artist in ARTISTAS_CO:
        events_raw = await _fetch_artist_events(artist, date_from, date_to)
        if not events_raw:
            await asyncio.sleep(0.3)
            continue

        for item in events_raw:
            try:
                is_co, municipio = _is_colombia_event(item)
                if not is_co:
                    continue

                evento = _parse_bit_event(item, artist)
                if not evento:
                    continue

                slug = evento["slug"]
                existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
                if existing.data:
                    stats["duplicados"] += 1
                    continue

                supabase.table("eventos").insert(evento).execute()
                stats["nuevos"] += 1
                print(f"    ✅ [BIT] {evento['titulo']} — {municipio}")
            except Exception as e:
                stats["errores"] += 1
                print(f"    ❌ [BIT] Error ({artist}): {e}")

        await asyncio.sleep(0.5)

    print(
        f"  [BIT] Completado — nuevos: {stats['nuevos']} | "
        f"duplicados: {stats['duplicados']} | errores: {stats['errores']}"
    )
    return stats
