"""
fundacion_epm_scraper.py
Scraper dedicado para Fundación EPM y sus espacios culturales:
  - Parque de los Deseos
  - Biblioteca España / Bibliored EPM
  - UVAs (Unidades de Vida Articulada) — agenda pública
  - Planetario de Medellín (EPM / Alcaldía)

Estrategia por capa:
  1. JSON-LD structured data (<script type="application/ld+json">)
  2. WP REST API si el sitio lo expone (/wp-json/tribe/events/v1/events)
  3. HTML scraping con BeautifulSoup
  4. RSS feed
"""
import asyncio
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.database import supabase
from app.services.ml_utils import is_likely_duplicate

CO_TZ = ZoneInfo("America/Bogota")

# ─── Fuentes ────────────────────────────────────────────────────────────────

_SOURCES = [
    {
        "nombre": "Parque de los Deseos",
        "fuente": "parque_deseos",
        "urls": [
            "https://www.fundacionepm.org.co/micrositios/parque-de-los-deseos/agenda/",
            "https://www.fundacionepm.org.co/micrositios/parque-de-los-deseos/",
        ],
        "wp_base": "https://www.fundacionepm.org.co",
        "municipio": "medellin",
        "nombre_lugar": "Parque de los Deseos",
    },
    {
        "nombre": "Fundación EPM — Agenda general",
        "fuente": "fundacion_epm",
        "urls": [
            "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
            "https://www.fundacionepm.org.co/agenda/",
            "https://www.fundacionepm.org.co/",
        ],
        "wp_base": "https://www.fundacionepm.org.co",
        "municipio": "medellin",
        "nombre_lugar": "Fundación EPM",
    },
    {
        "nombre": "Biblioteca EPM",
        "fuente": "biblioteca_epm",
        "urls": [
            "https://www.bibliotecaepm.com/agenda/",
            "https://www.bibliotecaepm.com/actividades/",
            "https://www.bibliotecaepm.com/programacion/",
            "https://www.bibliotecaepm.com/",
        ],
        "wp_base": "https://www.bibliotecaepm.com",
        "rss": "https://www.bibliotecaepm.com/feed/",
        "municipio": "medellin",
        "nombre_lugar": "Biblioteca EPM",
    },
    {
        "nombre": "Planetario de Medellín",
        "fuente": "planetario_medellin",
        "urls": [
            "https://www.planetariomedellin.org/agenda/",
            "https://www.planetariomedellin.org/programacion/",
            "https://www.planetariomedellin.org/",
        ],
        "wp_base": "https://www.planetariomedellin.org",
        "municipio": "medellin",
        "nombre_lugar": "Planetario de Medellín",
    },
    {
        "nombre": "UVAs de Medellín — INDER / EPM",
        "fuente": "uva_epm",
        "urls": [
            "https://www.inder.gov.co/programacion/",
            "https://www.inder.gov.co/eventos/",
            "https://www.medellin.gov.co/es/cultura-y-turismo/agenda-cultural/",
        ],
        "wp_base": None,
        "municipio": "medellin",
        "nombre_lugar": "UVA Medellín",
    },
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_CATEGORY_MAP = {
    "teatro": "teatro",
    "danza": "danza",
    "musica": "musica_en_vivo",
    "música": "musica_en_vivo",
    "concierto": "musica_en_vivo",
    "jazz": "jazz",
    "cine": "cine",
    "exposicion": "galeria",
    "exposición": "galeria",
    "galeria": "galeria",
    "galería": "galeria",
    "taller": "taller",
    "conferencia": "conferencia",
    "charla": "conferencia",
    "festival": "festival",
    "poesia": "poesia",
    "poesía": "poesia",
    "fotografia": "fotografia",
    "fotografía": "fotografia",
    "astronomia": "conferencia",
    "astronomía": "conferencia",
    "ciencia": "conferencia",
    "literatura": "editorial",
    "infantil": "taller",
    "niños": "taller",
    "familia": "taller",
}


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower().strip()


def _map_cat(raw: str) -> str:
    n = _norm(raw)
    for key, val in _CATEGORY_MAP.items():
        if key in n:
            return val
    return "otro"


def _slugify(text: str) -> str:
    norm = unicodedata.normalize("NFD", (text or "").lower().strip())
    clean = "".join(c if c.isalnum() or c == " " else " " for c in norm
                    if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "-", clean).strip("-")[:200]


def _parse_date(date_str: str) -> Optional[str]:
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d de %B de %Y",
    ):
        try:
            dt = datetime.strptime(date_str[:len(fmt) + 5], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CO_TZ)
            return dt.isoformat()
        except ValueError:
            continue
    return None


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


# ─── Extractor 1: JSON-LD ────────────────────────────────────────────────────

def _extract_jsonld_events(html: str, source_config: dict) -> list[dict]:
    """Extract structured Event data from JSON-LD blocks."""
    import json
    events = []
    soup = BeautifulSoup(html, "html.parser")
    now_co = datetime.now(CO_TZ)

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
        except Exception:
            continue
        items = ld if isinstance(ld, list) else [ld]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("Event", "MusicEvent", "TheaterEvent", "DanceEvent", "EducationEvent", "ExhibitionEvent"):
                continue
            titulo = (item.get("name") or "").strip()
            if not titulo:
                continue
            fecha_inicio = _parse_date(item.get("startDate") or "")
            if not fecha_inicio:
                continue
            try:
                dt = datetime.fromisoformat(fecha_inicio)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=CO_TZ)
                if dt < now_co - timedelta(hours=3):
                    continue
                if dt > now_co + timedelta(days=180):
                    continue
            except Exception:
                continue

            loc = item.get("location") or {}
            lugar = (loc.get("name", "") if isinstance(loc, dict) else str(loc)) or source_config["nombre_lugar"]
            desc = _strip_html(item.get("description") or "")[:500]
            imagen_url = None
            img = item.get("image")
            if isinstance(img, list) and img:
                imagen_url = img[0] if isinstance(img[0], str) else (img[0] or {}).get("url")
            elif isinstance(img, str):
                imagen_url = img
            elif isinstance(img, dict):
                imagen_url = img.get("url")

            offers = item.get("offers") or {}
            precio = None
            es_gratuito = False
            if isinstance(offers, dict):
                availability = (offers.get("availability") or "").lower()
                price = offers.get("price")
                if price in (0, "0", "0.00", "gratis", "free"):
                    es_gratuito = True
                    precio = "Gratis"
                elif price:
                    precio = str(price)
            elif isinstance(offers, list) and offers:
                o = offers[0]
                if isinstance(o, dict):
                    p = o.get("price")
                    if p in (0, "0", "0.00"):
                        es_gratuito = True
                        precio = "Gratis"
                    elif p:
                        precio = str(p)

            cat_raw = ""
            if item.get("superEvent"):
                se = item["superEvent"]
                if isinstance(se, dict):
                    cat_raw = se.get("name", "")
            if not cat_raw and item.get("category"):
                cat_raw = item["category"] if isinstance(item["category"], str) else ""

            events.append({
                "titulo": titulo[:200],
                "fecha_inicio": fecha_inicio,
                "fecha_fin": _parse_date(item.get("endDate") or ""),
                "descripcion": desc,
                "nombre_lugar": lugar[:200],
                "municipio": source_config["municipio"],
                "barrio": None,
                "precio": precio or "Consultar",
                "es_gratuito": es_gratuito,
                "categoria_principal": _map_cat(cat_raw),
                "categorias": [cat_raw] if cat_raw else [],
                "imagen_url": imagen_url,
                "fuente_url": item.get("url") or "",
                "fuente": source_config["fuente"],
            })

    return events


# ─── Extractor 2: WP REST API ────────────────────────────────────────────────

async def _try_wp_rest(source_config: dict, client: httpx.AsyncClient) -> list[dict]:
    wp_base = source_config.get("wp_base")
    if not wp_base:
        return []
    events = []
    now_co = datetime.now(CO_TZ)

    api_urls = [
        f"{wp_base}/wp-json/tribe/events/v1/events",
        f"{wp_base}/wp-json/wp/v2/tribe_events",
        f"{wp_base}/wp-json/wp/v2/events",
        f"{wp_base}/wp-json/wp/v2/posts?categories=eventos&per_page=20",
    ]
    for api_url in api_urls:
        try:
            params = {"per_page": 30, "start_date": now_co.strftime("%Y-%m-%d")} if "tribe" in api_url else {"per_page": 30}
            resp = await client.get(api_url, params=params, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data.get("events", data) if "tribe/events/v1" in api_url else data
            if not isinstance(items, list) or not items:
                continue
            print(f"  [epm_scraper] WP REST {api_url} → {len(items)} items")
            for item in items:
                titulo = (item.get("title") or {}).get("rendered") or item.get("title", "")
                if isinstance(titulo, str):
                    titulo = re.sub(r"<[^>]+>", "", titulo).strip()
                if not titulo:
                    continue
                meta = item.get("meta") or {}
                acf = item.get("acf") or {}
                fecha_inicio = (
                    meta.get("_EventStartDate")
                    or acf.get("fecha_inicio")
                    or item.get("start_date")
                    or item.get("date", "")
                )
                try:
                    dt = datetime.fromisoformat(fecha_inicio.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=CO_TZ)
                    if dt < now_co - timedelta(hours=3):
                        continue
                except Exception:
                    pass
                desc = re.sub(r"<[^>]+>", "", (item.get("excerpt") or {}).get("rendered", ""))[:500]
                embedded = item.get("_embedded") or {}
                imagen_url = None
                if embedded.get("wp:featuredmedia"):
                    media = embedded["wp:featuredmedia"][0] or {}
                    imagen_url = media.get("source_url")
                events.append({
                    "titulo": titulo[:200],
                    "fecha_inicio": _parse_date(fecha_inicio),
                    "fecha_fin": _parse_date(meta.get("_EventEndDate") or acf.get("fecha_fin") or ""),
                    "descripcion": desc,
                    "nombre_lugar": (meta.get("_EventVenue") or source_config["nombre_lugar"])[:200],
                    "municipio": source_config["municipio"],
                    "barrio": None,
                    "precio": "Consultar",
                    "es_gratuito": False,
                    "categoria_principal": "otro",
                    "categorias": [],
                    "imagen_url": imagen_url,
                    "fuente_url": item.get("link") or item.get("url") or "",
                    "fuente": source_config["fuente"],
                })
            if events:
                return events
        except Exception as e:
            print(f"  [epm_scraper] WP REST error {api_url}: {e}")
            continue
    return events


# ─── Extractor 3: HTML scraping ──────────────────────────────────────────────

def _extract_html_events(html: str, source_url: str, source_config: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    now_co = datetime.now(CO_TZ)

    card_selectors = [
        "article[class*='event']",
        "article[class*='tribe']",
        "div[class*='event-card']",
        "div[class*='evento']",
        "li[class*='event']",
        "div[class*='programacion']",
        "div[class*='actividad']",
        "article",
        "div[class*='card']",
    ]
    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if len(cards) >= 2:
            break

    for card in cards[:60]:
        titulo_tag = (
            card.find("h2") or card.find("h3") or card.find("h4")
            or card.find(class_=re.compile(r"title|titulo|nombre", re.I))
        )
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else ""
        if not titulo or len(titulo) < 4:
            continue

        fecha_tag = (
            card.find("time")
            or card.find(class_=re.compile(r"fecha|date|start|cuando", re.I))
            or card.find(attrs={"datetime": True})
        )
        fecha_raw = ""
        if fecha_tag:
            fecha_raw = fecha_tag.get("datetime") or fecha_tag.get_text(strip=True)

        fecha_iso = _parse_date(fecha_raw)
        if fecha_iso:
            try:
                dt = datetime.fromisoformat(fecha_iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=CO_TZ)
                if dt < now_co - timedelta(hours=3):
                    continue
            except Exception:
                pass

        lugar_tag = card.find(class_=re.compile(r"lugar|venue|location|sede|espacio", re.I))
        lugar = lugar_tag.get_text(strip=True) if lugar_tag else source_config["nombre_lugar"]

        cat_tag = card.find(class_=re.compile(r"categ|tag|tipo|disciplina", re.I))
        cat_raw = cat_tag.get_text(strip=True) if cat_tag else ""

        img_tag = card.find("img")
        imagen_url = None
        if img_tag:
            imagen_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")

        a_tag = card.find("a", href=True)
        link = ""
        if a_tag:
            href = a_tag["href"]
            base = source_config.get("wp_base") or ""
            link = href if href.startswith("http") else f"{base}{href}"

        events.append({
            "titulo": titulo[:200],
            "fecha_inicio": fecha_iso,
            "fecha_fin": None,
            "descripcion": "",
            "nombre_lugar": lugar[:200],
            "municipio": source_config["municipio"],
            "barrio": None,
            "precio": "Consultar",
            "es_gratuito": False,
            "categoria_principal": _map_cat(cat_raw),
            "categorias": [cat_raw] if cat_raw else [],
            "imagen_url": imagen_url,
            "fuente_url": link or source_url,
            "fuente": source_config["fuente"],
        })

    return events


# ─── Extractor 4: RSS ────────────────────────────────────────────────────────

async def _try_rss(source_config: dict, client: httpx.AsyncClient) -> list[dict]:
    rss_url = source_config.get("rss")
    if not rss_url:
        return []
    events = []
    now_co = datetime.now(CO_TZ)
    try:
        resp = await client.get(rss_url, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item")[:30]:
            titulo = (item.find("title") or {}).get_text(strip=True)
            if not titulo:
                continue
            pubdate = (item.find("pubDate") or {}).get_text(strip=True)
            fecha_iso = _parse_date(pubdate)
            desc_raw = (item.find("description") or {}).get_text(strip=True)
            link = (item.find("link") or {}).get_text(strip=True)
            events.append({
                "titulo": titulo[:200],
                "fecha_inicio": fecha_iso,
                "fecha_fin": None,
                "descripcion": _strip_html(desc_raw)[:500],
                "nombre_lugar": source_config["nombre_lugar"],
                "municipio": source_config["municipio"],
                "barrio": None,
                "precio": "Consultar",
                "es_gratuito": False,
                "categoria_principal": "otro",
                "categorias": [],
                "imagen_url": None,
                "fuente_url": link,
                "fuente": source_config["fuente"],
            })
    except Exception as e:
        print(f"  [epm_scraper] RSS error {rss_url}: {e}")
    return events


# ─── Scraping de una fuente ──────────────────────────────────────────────────

async def _scrape_source(source_config: dict) -> list[dict]:
    events: list[dict] = []
    nombre = source_config["nombre"]
    print(f"[epm_scraper] → Scraping: {nombre}")

    async with httpx.AsyncClient(
        timeout=25,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        # Try WP REST first (fast, structured)
        wp_events = await _try_wp_rest(source_config, client)
        if wp_events:
            print(f"  [epm_scraper] {nombre}: WP REST → {len(wp_events)} eventos")
            return wp_events

        # Try RSS
        rss_events = await _try_rss(source_config, client)
        if rss_events:
            print(f"  [epm_scraper] {nombre}: RSS → {len(rss_events)} eventos")
            return rss_events

        # HTML scraping
        for url in source_config["urls"]:
            try:
                resp = await client.get(url, timeout=20)
                if resp.status_code != 200:
                    print(f"  [epm_scraper] {url} → HTTP {resp.status_code}")
                    continue
                html = resp.text
                if len(html) < 500:
                    continue

                # JSON-LD first pass
                ld_events = _extract_jsonld_events(html, source_config)
                if ld_events:
                    print(f"  [epm_scraper] {nombre}: JSON-LD {url} → {len(ld_events)} eventos")
                    events.extend(ld_events)
                    break

                # HTML fallback
                html_events = _extract_html_events(html, url, source_config)
                if html_events:
                    print(f"  [epm_scraper] {nombre}: HTML {url} → {len(html_events)} eventos")
                    events.extend(html_events)
                    break

            except Exception as e:
                print(f"  [epm_scraper] Error {url}: {e}")
                continue

    return events


# ─── Guardar eventos ─────────────────────────────────────────────────────────

async def _save_events(events: list[dict]) -> dict:
    now_co = datetime.now(CO_TZ)
    stats = {"nuevos": 0, "duplicados": 0, "descartados": 0}

    try:
        existing_resp = (
            supabase.table("eventos")
            .select("titulo,fecha_inicio,fuente_url")
            .gte("fecha_inicio", now_co.strftime("%Y-%m-%d"))
            .execute()
        )
        existing = existing_resp.data or []
    except Exception:
        existing = []

    for ev in events:
        try:
            if not ev.get("titulo"):
                stats["descartados"] += 1
                continue

            fecha_str = ev.get("fecha_inicio") or ""
            if fecha_str:
                try:
                    dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=CO_TZ)
                    if dt < now_co - timedelta(hours=3):
                        stats["descartados"] += 1
                        continue
                    if dt > now_co + timedelta(days=180):
                        stats["descartados"] += 1
                        continue
                except Exception:
                    pass

            # Dedup via fuente_url exact match
            if ev.get("fuente_url"):
                match = next((e for e in existing if e.get("fuente_url") == ev["fuente_url"]), None)
                if match:
                    stats["duplicados"] += 1
                    continue

            # Dedup via BM25 title similarity
            if fecha_str and is_likely_duplicate(
                ev["titulo"],
                fecha_str[:10],
                [{"titulo": e["titulo"], "fecha_inicio": e["fecha_inicio"]} for e in existing],
            ):
                stats["duplicados"] += 1
                continue

            slug_base = _slugify(ev["titulo"])
            fuente_slug = _slugify(ev.get("fuente") or "epm")
            date_part = (fecha_str or "")[:10].replace("-", "") or hashlib.md5(ev["titulo"].encode()).hexdigest()[:8]
            slug = f"{fuente_slug}-{slug_base}-{date_part}"

            for attempt in range(10):
                candidate = slug if attempt == 0 else f"{slug}-{attempt}"
                dup = (
                    supabase.table("eventos")
                    .select("id")
                    .eq("slug", candidate)
                    .limit(1)
                    .execute()
                )
                if not (dup.data or []):
                    slug = candidate
                    break

            record = {
                "slug": slug,
                "titulo": ev["titulo"],
                "fecha_inicio": ev.get("fecha_inicio"),
                "fecha_fin": ev.get("fecha_fin"),
                "descripcion": ev.get("descripcion") or "",
                "nombre_lugar": ev.get("nombre_lugar") or ev.get("fuente", "Fundación EPM"),
                "municipio": ev.get("municipio") or "medellin",
                "barrio": ev.get("barrio"),
                "precio": ev.get("precio") or "Consultar",
                "es_gratuito": ev.get("es_gratuito") or False,
                "categoria_principal": ev.get("categoria_principal") or "otro",
                "categorias": ev.get("categorias") or [],
                "imagen_url": ev.get("imagen_url"),
                "fuente_url": ev.get("fuente_url") or "",
                "fuente": ev.get("fuente") or "fundacion_epm",
                "hora_confirmada": bool(ev.get("fecha_inicio") and "T" in str(ev.get("fecha_inicio") or "")),
            }

            supabase.table("eventos").insert(record).execute()
            existing.append({"titulo": ev["titulo"], "fecha_inicio": ev.get("fecha_inicio"), "fuente_url": ev.get("fuente_url")})
            stats["nuevos"] += 1

        except Exception as e:
            print(f"  [epm_scraper] Save error: {e}")
            stats["descartados"] += 1

    return stats


# ─── Entry point ─────────────────────────────────────────────────────────────

async def run_fundacion_epm_scraper() -> dict:
    """
    Scraper principal. Recorre todas las fuentes EPM/UVAs y guarda en BD.
    Devuelve stats agregadas {nuevos, duplicados, descartados, fuentes}.
    """
    total = {"nuevos": 0, "duplicados": 0, "descartados": 0, "fuentes": 0}
    all_events: list[dict] = []

    tasks = [_scrape_source(src) for src in _SOURCES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for src, result in zip(_SOURCES, results):
        if isinstance(result, Exception):
            print(f"[epm_scraper] ✗ {src['nombre']}: {result}")
            continue
        if result:
            all_events.extend(result)
            total["fuentes"] += 1
            print(f"[epm_scraper] ✓ {src['nombre']}: {len(result)} candidatos")

    if all_events:
        stats = await _save_events(all_events)
        total["nuevos"] += stats["nuevos"]
        total["duplicados"] += stats["duplicados"]
        total["descartados"] += stats["descartados"]

    print(
        f"[epm_scraper] Completado — "
        f"nuevos={total['nuevos']} | dup={total['duplicados']} | descartados={total['descartados']} | fuentes={total['fuentes']}"
    )
    return total
