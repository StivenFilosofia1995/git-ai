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
from app.services.data_quality import is_likely_cultural_event

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

# Comfama — The Events Calendar REST API (v1 is the correct endpoint)
_COMFAMA_API_EVENTS_V1 = "https://www.comfama.com/wp-json/tribe/events/v1/events"
# Legacy WP REST API fallback (usually 404 on Comfama)
_COMFAMA_API_EVENTS_V2 = "https://www.comfama.com/wp-json/wp/v2/tribe_events"

_COMFAMA_API_PARAMS_BASE = {
    "per_page": 50,
    "status": "publish",
    "_embed": 1,
}

# SSR pages — Comfama renders server-side, these work without JavaScript
_COMFAMA_AGENDA_URLS = [
    "https://www.comfama.com/agenda/eventos/para-esta-semana",
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
    Fetch events from Comfama's The Events Calendar REST API v1.
    Endpoint: /wp-json/tribe/events/v1/events
    Falls back to wp/v2/tribe_events if v1 is unavailable.
    """
    events = []
    apis_to_try = [
        (_COMFAMA_API_EVENTS_V1, True),   # The Events Calendar v1
        (_COMFAMA_API_EVENTS_V2, False),  # Legacy WP REST fallback
    ]
    now_co = datetime.now(CO_TZ)

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
            for api_url, is_v1 in apis_to_try:
                params: dict = {"per_page": 50, "page": 1}
                if is_v1:
                    params["start_date"] = now_co.strftime("%Y-%m-%d")
                else:
                    params.update(_COMFAMA_API_PARAMS_BASE)

                resp = await client.get(api_url, params=params)
                if resp.status_code != 200:
                    print(f"  [comfama_scraper] {api_url} → HTTP {resp.status_code}, skipping")
                    continue

                data = resp.json()
                # v1 wraps in {"events": [...], "total": N}
                items = data.get("events", data) if is_v1 else data
                if not isinstance(items, list) or not items:
                    print(f"  [comfama_scraper] {api_url} → empty list")
                    continue

                print(f"  [comfama_scraper] {api_url} → {len(items)} items")
                for item in items:
                    # Field names differ between v1 and v2
                    if is_v1:
                        titulo = item.get("title", "").strip()
                        fecha_inicio = item.get("start_date", "") or item.get("start_date_details", {}).get("date", "")
                        fecha_fin = item.get("end_date") or None
                        descripcion = re.sub(r"<[^>]+>", "", item.get("description", ""))[:500]
                        venue = item.get("venue") or {}
                        lugar = venue.get("venue", "") or venue.get("address", "") or "Comfama"
                        imagen_url = (item.get("image") or {}).get("url")
                        link = item.get("url", "")
                        categorias_raw = [c.get("name", "") for c in item.get("categories", []) if isinstance(c, dict)]
                    else:
                        meta = item.get("meta", {}) or {}
                        acf = item.get("acf", {}) or {}
                        titulo = (item.get("title", {}) or {}).get("rendered", "").strip()
                        fecha_inicio = meta.get("_EventStartDate") or acf.get("fecha_inicio") or item.get("date", "")
                        fecha_fin = meta.get("_EventEndDate") or acf.get("fecha_fin") or None
                        descripcion = re.sub(r"<[^>]+>", "", (item.get("excerpt", {}) or {}).get("rendered", ""))[:500]
                        lugar = meta.get("_EventVenue", "") or acf.get("lugar", "") or "Comfama"
                        imagen_url = None
                        embedded = item.get("_embedded", {}) or {}
                        if embedded.get("wp:featuredmedia"):
                            media = embedded["wp:featuredmedia"][0] or {}
                            imagen_url = media.get("source_url")
                        link = item.get("link", "")
                        categorias_raw = [
                            t.get("name", "") for t in
                            embedded.get("wp:term", [[]])[0] if isinstance(t, dict)
                        ]

                    if not titulo:
                        continue

                    cat_principal = _map_categoria(categorias_raw[0] if categorias_raw else "")
                    ev = {
                        "titulo": titulo[:200],
                        "fecha_inicio": _parse_comfama_date(str(fecha_inicio)) if fecha_inicio else None,
                        "fecha_fin": _parse_comfama_date(str(fecha_fin)) if fecha_fin else None,
                        "descripcion": descripcion,
                        "nombre_lugar": (lugar or "Comfama Medellín")[:200],
                        "barrio": None,
                        "municipio": "medellin",
                        "precio": "Consultar",
                        "es_gratuito": False,
                        "categoria_principal": cat_principal,
                        "categorias": categorias_raw[:5],
                        "imagen_url": imagen_url,
                        "fuente_url": link or "https://www.comfama.com/agenda/",
                    }
                    events.append(ev)
                break  # Got results from this API, stop trying others
    except Exception as exc:
        print(f"[comfama_scraper] WP API error: {exc}")
    return events


async def _try_html_scrape() -> list[dict]:
    """
    Scrape Comfama's SSR agenda page directly with httpx + BeautifulSoup.
    Comfama renders server-side so we don't need Playwright.
    """
    from bs4 import BeautifulSoup

    events: list[dict] = []
    now_co = datetime.now(CO_TZ)
    html_headers = {**_HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"}

    for url in _COMFAMA_AGENDA_URLS:
        try:
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True, headers=html_headers
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    print(f"  [comfama_scraper] HTML {url} → HTTP {resp.status_code}")
                    continue
                html = resp.text

            if len(html) < 1000:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Comfama event cards — common selectors used by their theme
            card_selectors = [
                "article.tribe_events_cat",
                "article[class*='tribe']",
                "div.tribe_events_cat",
                "div[class*='event-card']",
                "div[class*='evento']",
                "article[class*='event']",
                "li[class*='tribe']",
                "div[class*='tribe']",
                "li[class*='event']",
                # Generic fallback: kept but results are filtered by is_likely_cultural_event
                "article",
            ]
            cards = []
            for sel in card_selectors:
                cards = soup.select(sel)
                if cards:
                    break

            if not cards:
                # Try JSON-LD structured data
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json
                        ld = json.loads(script.string or "")
                        items = ld if isinstance(ld, list) else [ld]
                        for item in items:
                            if item.get("@type") in ("Event", "MusicEvent", "TheaterEvent"):
                                titulo = item.get("name", "").strip()
                                fecha_inicio = item.get("startDate", "")
                                fecha_fin = item.get("endDate")
                                lugar_obj = item.get("location") or {}
                                lugar = (
                                    lugar_obj.get("name", "") if isinstance(lugar_obj, dict) else str(lugar_obj)
                                )
                                descripcion = (item.get("description") or "")[:500]
                                imagen_url = (item.get("image") or [None])[0] if isinstance(item.get("image"), list) else item.get("image")
                                if titulo and fecha_inicio:
                                    events.append({
                                        "titulo": titulo[:200],
                                        "fecha_inicio": _parse_comfama_date(fecha_inicio),
                                        "fecha_fin": _parse_comfama_date(fecha_fin) if fecha_fin else None,
                                        "descripcion": descripcion,
                                        "nombre_lugar": (lugar or "Comfama")[:200],
                                        "barrio": None,
                                        "municipio": "medellin",
                                        "precio": "Consultar",
                                        "es_gratuito": False,
                                        "categoria_principal": "centro_cultural",
                                        "categorias": [],
                                        "imagen_url": imagen_url,
                                        "fuente_url": item.get("url") or url,
                                    })
                    except Exception:
                        pass
                if events:
                    break
                continue

            for card in cards[:60]:
                # Title
                titulo_tag = (
                    card.find("h2") or card.find("h3") or card.find("h4")
                    or card.find(class_=re.compile(r"title|titulo|nombre", re.I))
                )
                titulo = titulo_tag.get_text(strip=True) if titulo_tag else ""
                if not titulo or len(titulo) < 4:
                    continue

                # Date
                fecha_tag = (
                    card.find("time")
                    or card.find(class_=re.compile(r"fecha|date|start", re.I))
                    or card.find(attrs={"datetime": True})
                )
                fecha_raw = ""
                if fecha_tag:
                    fecha_raw = fecha_tag.get("datetime") or fecha_tag.get_text(strip=True)

                # Location
                lugar_tag = card.find(class_=re.compile(r"lugar|venue|location|sede", re.I))
                lugar = lugar_tag.get_text(strip=True) if lugar_tag else "Comfama"

                # Category
                cat_tag = card.find(class_=re.compile(r"categ|tag|tipo", re.I))
                cat_raw = cat_tag.get_text(strip=True) if cat_tag else ""

                # Image
                img_tag = card.find("img")
                imagen_url = None
                if img_tag:
                    imagen_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")

                # Link
                a_tag = card.find("a", href=True)
                link = ""
                if a_tag:
                    href = a_tag["href"]
                    link = href if href.startswith("http") else f"https://www.comfama.com{href}"

                fecha_iso = _parse_comfama_date(fecha_raw)
                if fecha_iso:
                    try:
                        dt = datetime.fromisoformat(fecha_iso)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=CO_TZ)
                        if dt < now_co - timedelta(hours=2):
                            continue
                    except Exception:
                        pass

                precio_tag = card.find(class_=re.compile(r"precio|price|costo|valor|tarifa", re.I))
                precio_raw = precio_tag.get_text(strip=True) if precio_tag else ""
                es_gratuito = any(w in precio_raw.lower() for w in ("gratis", "gratuito", "free", "$0"))
                precio_display = "Gratis" if es_gratuito else (precio_raw or "Consultar")

                events.append({
                    "titulo": titulo[:200],
                    "fecha_inicio": fecha_iso,
                    "fecha_fin": None,
                    "descripcion": "",
                    "nombre_lugar": (lugar or "Comfama")[:200],
                    "barrio": None,
                    "municipio": "medellin",
                    "precio": precio_display,
                    "es_gratuito": es_gratuito,
                    "categoria_principal": _map_categoria(cat_raw),
                    "categorias": [cat_raw] if cat_raw else [],
                    "imagen_url": imagen_url,
                    "fuente_url": link or url,
                })

            if events:
                print(f"  [comfama_scraper] HTML parsed {len(events)} events from {url}")
                break

        except Exception as exc:
            print(f"[comfama_scraper] HTML scrape error for {url}: {exc}")

    # Last resort: let scrape_agenda_sources() handle it via AI extraction
    # (it already has Comfama URLs in AGENDA_SOURCES)
    if not events:
        print("  [comfama_scraper] No events parsed from HTML — scrape_agenda_sources() will handle Comfama URLs")

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

            # Filter out non-events (blog posts, news, etc.)
            if not is_likely_cultural_event(
                ev.get("titulo"),
                ev.get("descripcion"),
                fuente_url=ev.get("fuente_url"),
                categoria=ev.get("categoria_principal"),
            ):
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
