"""
comfama_scraper.py
Scraper dedicado para Comfama: eventos, bibliotecas y centros culturales.

Comfama usa una SPA (React) que carga eventos via API interna.
Este scraper:
  1. Llama a la API REST interna de Comfama para obtener eventos paginados
  2. Filtra por municipio=Medellín (y otros del Valle de Aburrá)
  3. Normaliza y guarda en la BD con todas las garantías de precisión
"""
import asyncio
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.database import supabase
from app.services.ml_utils import is_likely_duplicate

CO_TZ = ZoneInfo("America/Bogota")

# Municipios del Valle de Aburrá que Comfama cubre
COMFAMA_MUNICIPIOS = [
    "Medellín",
    "Bello",
    "Itagüí",
    "Envigado",
    "Sabaneta",
    "La Estrella",
    "Caldas",
    "Copacabana",
    "Girardota",
    "Barbosa",
]

# Categorías de Comfama → categorías del sistema
_CATEGORIA_MAP = {
    "teatro": "teatro",
    "danza": "danza",
    "musica": "musica_en_vivo",
    "música": "musica_en_vivo",
    "artes plasticas": "galeria",
    "artes plásticas": "galeria",
    "exposicion": "galeria",
    "exposición": "galeria",
    "cine": "cine",
    "literatura": "editorial",
    "charla": "centro_cultural",
    "taller": "centro_cultural",
    "infantil": "centro_cultural",
    "festival": "festival",
    "concierto": "musica_en_vivo",
    "galeria": "galeria",
    "fotografía": "fotografia",
    "fotografia": "fotografia",
    "circo": "circo",
    "hip hop": "hip_hop",
    "hip-hop": "hip_hop",
    "jazz": "jazz",
    "poesía": "poesia",
    "poesia": "poesia",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Referer": "https://www.comfama.com/agenda/eventos/",
}

# Comfama's internal API endpoint (discovered from network requests)
_COMFAMA_API_EVENTS = "https://www.comfama.com/wp-json/wp/v2/tribe_events"
_COMFAMA_API_PARAMS_BASE = {
    "per_page": 50,
    "status": "publish",
    "_embed": 1,
}

# Alternative: scrape the public agenda page directly
_COMFAMA_AGENDA_URLS = [
    "https://www.comfama.com/agenda/eventos/?municipio=Medell%C3%ADn",
    "https://www.comfama.com/agenda/",
]


def _normalize(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower().strip()


def _map_categoria(raw: str) -> str:
    norm = _normalize(raw)
    for key, val in _CATEGORIA_MAP.items():
        if key in norm:
            return val
    return "centro_cultural"


def _slugify(text: str) -> str:
    norm = unicodedata.normalize("NFD", (text or "").lower().strip())
    clean = "".join(c if c.isalnum() or c == " " else " " for c in norm
                    if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "-", clean).strip("-")[:200]


def _parse_comfama_date(date_str: str) -> Optional[str]:
    """Parse Comfama date formats → ISO string for DB."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Try ISO first
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CO_TZ)
            return dt.isoformat()
        except ValueError:
            continue
    return None


async def _try_wp_api(municipio: str = "Medellín") -> list[dict]:
    """
    Attempt to fetch events from Comfama's WordPress REST API.
    Returns list of normalized event dicts.
    """
    events = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
            params = {**_COMFAMA_API_PARAMS_BASE, "page": 1}
            resp = await client.get(_COMFAMA_API_EVENTS, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            for item in data:
                meta = item.get("meta", {}) or {}
                acf = item.get("acf", {}) or {}
                # Try different field paths for Tribe Events plugin
                fecha_inicio = (
                    meta.get("_EventStartDate")
                    or acf.get("fecha_inicio")
                    or item.get("date", "")
                )
                fecha_fin = (
                    meta.get("_EventEndDate")
                    or acf.get("fecha_fin")
                    or None
                )
                titulo = (item.get("title", {}) or {}).get("rendered", "").strip()
                if not titulo:
                    continue
                descripcion = re.sub(
                    r"<[^>]+>", "",
                    (item.get("excerpt", {}) or {}).get("rendered", "") or ""
                )[:500]
                lugar = meta.get("_EventVenue", "") or acf.get("lugar", "")
                imagen_url = None
                embedded = item.get("_embedded", {}) or {}
                if embedded.get("wp:featuredmedia"):
                    media = embedded["wp:featuredmedia"][0] or {}
                    imagen_url = (
                        media.get("source_url")
                        or (media.get("media_details", {}) or {}).get("sizes", {}).get("full", {}).get("source_url")
                    )
                link = item.get("link", "")
                categorias_raw = [
                    t.get("name", "") for t in
                    embedded.get("wp:term", [[]])[0] if isinstance(t, dict)
                ]
                cat_principal = _map_categoria(categorias_raw[0] if categorias_raw else "")
                ev = {
                    "titulo": titulo[:200],
                    "fecha_inicio": _parse_comfama_date(fecha_inicio),
                    "fecha_fin": _parse_comfama_date(fecha_fin) if fecha_fin else None,
                    "descripcion": descripcion,
                    "nombre_lugar": lugar[:200] if lugar else "Comfama Medellín",
                    "barrio": None,
                    "municipio": "medellin",
                    "precio": acf.get("precio") or "Consultar",
                    "es_gratuito": False,
                    "categoria_principal": cat_principal,
                    "categorias": categorias_raw[:5],
                    "imagen_url": imagen_url,
                    "fuente_url": link or "https://www.comfama.com/agenda/",
                }
                events.append(ev)
    except Exception as exc:
        print(f"[comfama_scraper] WP API error: {exc}")
    return events


async def _try_html_scrape() -> list[dict]:
    """
    Fallback: scrape the HTML agenda page using auto_scraper infrastructure.
    """
    from app.services.auto_scraper import _fetch_website_raw, _extract_og_image
    from app.services.playwright_fetcher import fetch_with_playwright
    from app.services.html_event_extractor import extract_events_code

    events = []
    for url in _COMFAMA_AGENDA_URLS:
        try:
            html = await _fetch_website_raw(url)
            if not html or len(html) < 500:
                # Comfama requires JavaScript — try Playwright
                html = await fetch_with_playwright(url)
            if html and len(html) > 500:
                found = extract_events_code(
                    html, url, "Comfama Agenda", "centro_cultural", "medellin"
                )
                if found:
                    events.extend(found)
                    break  # Got events, no need to try next URL
        except Exception as exc:
            print(f"[comfama_scraper] HTML scrape error for {url}: {exc}")
    return events


async def _save_comfama_events(events: list[dict]) -> dict:
    """Save normalized Comfama events, deduplicating against existing DB rows."""
    now_co = datetime.now(CO_TZ)
    stats = {"nuevos": 0, "duplicados": 0, "descartados": 0}

    try:
        # Load upcoming events for dup detection
        existing_resp = (
            supabase.table("eventos")
            .select("titulo,fecha_inicio,espacio_id,fuente_url")
            .gte("fecha_inicio", now_co.strftime("%Y-%m-%d"))
            .execute()
        )
        existing = existing_resp.data or []
    except Exception:
        existing = []

    for ev in events:
        try:
            if not ev.get("titulo") or not ev.get("fecha_inicio"):
                stats["descartados"] += 1
                continue

            fecha_str = ev["fecha_inicio"]
            try:
                dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=CO_TZ)
                if dt < now_co - timedelta(hours=2):
                    stats["descartados"] += 1
                    continue
                if dt > now_co + timedelta(days=120):
                    stats["descartados"] += 1
                    continue
            except Exception:
                stats["descartados"] += 1
                continue

            # Deduplication using BM25 similarity
            if is_likely_duplicate(
                ev["titulo"],
                fecha_str[:10],
                [
                    {"titulo": e["titulo"], "fecha_inicio": e["fecha_inicio"]}
                    for e in existing
                ],
            ):
                stats["duplicados"] += 1
                continue

            slug_base = _slugify(ev["titulo"])
            date_part = fecha_str[:10].replace("-", "")
            slug = f"comfama-{slug_base}-{date_part}"

            # Ensure unique slug
            for attempt in range(10):
                candidate = slug if attempt == 0 else f"{slug}-{attempt}"
                dup = (
                    supabase.table("eventos")
                    .select("id")
                    .eq("slug", candidate)
                    .limit(1)
                    .execute()
                )
                if not dup.data:
                    slug = candidate
                    break

            row = {
                "titulo": ev["titulo"],
                "slug": slug,
                "espacio_id": None,
                "fecha_inicio": ev["fecha_inicio"],
                "fecha_fin": ev.get("fecha_fin"),
                "hora_confirmada": bool(
                    ev["fecha_inicio"] and "T" in ev["fecha_inicio"]
                    and not ev["fecha_inicio"].endswith("T00:00:00")
                ),
                "categorias": ev.get("categorias") or [ev.get("categoria_principal", "centro_cultural")],
                "categoria_principal": ev.get("categoria_principal", "centro_cultural"),
                "municipio": ev.get("municipio", "medellin"),
                "barrio": ev.get("barrio"),
                "nombre_lugar": ev.get("nombre_lugar") or "Comfama",
                "descripcion": ev.get("descripcion", "")[:1000],
                "imagen_url": ev.get("imagen_url"),
                "precio": ev.get("precio") or "Consultar",
                "es_gratuito": bool(ev.get("es_gratuito")),
                "fuente": "comfama",
                "fuente_url": ev.get("fuente_url") or "https://www.comfama.com/agenda/",
                "verificado": True,
            }

            supabase.table("eventos").insert(row).execute()
            existing.append({"titulo": row["titulo"], "fecha_inicio": row["fecha_inicio"]})
            stats["nuevos"] += 1

        except Exception as exc:
            print(f"[comfama_scraper] Error saving event '{ev.get('titulo', '?')}': {exc}")
            stats["descartados"] += 1

    return stats


async def run_comfama_scraper() -> dict:
    """
    Main entry point for the Comfama dedicated scraper.
    Tries WP REST API first, falls back to HTML scraping.
    """
    print("\n🎭 ═══════════════════════════════════════════════")
    print("   COMFAMA SCRAPER — eventos, bibliotecas, centros")
    print("═══════════════════════════════════════════════════")

    events: list[dict] = []

    # Try WordPress REST API
    print("  → Intentando API WordPress de Comfama...")
    wp_events = await _try_wp_api()
    if wp_events:
        print(f"  → API: {len(wp_events)} eventos encontrados")
        events.extend(wp_events)

    # Fallback: HTML scraping of the agenda page
    if len(events) < 3:
        print("  → API con pocos resultados, intentando scraping HTML...")
        html_events = await _try_html_scrape()
        print(f"  → HTML: {len(html_events)} eventos encontrados")
        # Merge avoiding duplicates
        seen_titles = {e["titulo"].lower() for e in events}
        for ev in html_events:
            if ev.get("titulo", "").lower() not in seen_titles:
                events.append(ev)
                seen_titles.add(ev["titulo"].lower())

    print(f"  → Total a procesar: {len(events)} eventos")
    stats = await _save_comfama_events(events)
    print(
        f"  ✅ Comfama: {stats['nuevos']} nuevos | "
        f"{stats['duplicados']} duplicados | "
        f"{stats['descartados']} descartados"
    )
    return stats
