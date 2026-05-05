from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except Exception:
    async_playwright = None

from app.database import supabase
from app.services.auto_scraper import (
    CO_TZ,
    _normalize_scraped_datetime,
    _sanitize_payload,
    _slugify,
)
from app.services.data_quality import is_likely_cultural_event
from app.services.html_event_extractor import extract_events_code

# ── Known Medellín / Valle de Aburrá cultural sites with their agenda URLs ──
# These are scraped DIRECTLY (no Google needed) using the site-specific parsers
# already built in html_event_extractor.py.
KNOWN_CULTURAL_SITES: list[dict] = [
    {
        "url": "https://www.teatropablotobon.com/programacion",
        "nombre": "Teatro Pablo Tobón Uribe",
        "municipio": "medellin",
        "categorias": ["teatro", "danza", "musica_en_vivo"],
    },
    {
        "url": "https://www.matacandelas.com/",
        "nombre": "Teatro Matacandelas",
        "municipio": "medellin",
        "categorias": ["teatro"],
    },
    {
        "url": "https://bibliotecapiloto.gov.co/agenda/",
        "nombre": "Biblioteca Pública Piloto",
        "municipio": "medellin",
        "categorias": ["casa_cultura", "taller", "conferencia"],
    },
    {
        "url": "https://www.comfenalcoantioquia.com.co/cultura-y-educacion/eventos/",
        "nombre": "Comfenalco Antioquia",
        "municipio": "medellin",
        "categorias": ["centro_cultural", "taller", "teatro"],
    },
    {
        "url": "https://comfama.com/agenda-cultural/",
        "nombre": "Comfama",
        "municipio": "medellin",
        "categorias": ["centro_cultural"],
    },
    {
        "url": "https://www.elperpetuosocorro.org/agenda",
        "nombre": "Teatro El Perpetuo Socorro",
        "municipio": "medellin",
        "categorias": ["teatro"],
    },
    {
        "url": "https://www.culturamedellín.gov.co/agenda",
        "nombre": "Alcaldía de Medellín - Cultura",
        "municipio": "medellin",
        "categorias": ["centro_cultural", "festival", "taller"],
    },
    {
        "url": "https://www.parqueexplora.org/agenda",
        "nombre": "Parque Explora",
        "municipio": "medellin",
        "categorias": ["taller", "conferencia"],
    },
    {
        "url": "https://www.jardibotanicomedellin.org/eventos/",
        "nombre": "Jardín Botánico de Medellín",
        "municipio": "medellin",
        "categorias": ["festival", "taller"],
    },
    {
        "url": "https://www.museodeantioquia.co/agenda/",
        "nombre": "Museo de Antioquia",
        "municipio": "medellin",
        "categorias": ["arte_contemporaneo", "galeria", "conferencia"],
    },
    {
        "url": "https://www.mamm.org.co/programacion/",
        "nombre": "Museo de Arte Moderno de Medellín",
        "municipio": "medellin",
        "categorias": ["arte_contemporaneo", "cine", "conferencia"],
    },
    {
        "url": "https://www.casateatroenviado.com/agenda",
        "nombre": "Casa Teatro El Poblado",
        "municipio": "medellin",
        "categorias": ["teatro", "musica_en_vivo"],
    },
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
ACCEPT_LANG = "es-CO,es;q=0.9,en;q=0.8"


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def _precio_label(es_gratuito: Optional[bool]) -> str:
    if es_gratuito is True:
        return "gratis"
    if es_gratuito is False:
        return "pago"
    return "todos"


# ── Barrios / comunas / zonas reconocidas de Medellín y Valle de Aburrá ────
# Usados para extraer el barrio buscado cuando el usuario lo escribe
# en texto libre (ej: "eventos en aranjuez" → barrio="aranjuez").
_BARRIOS_MEDELLIN: list[str] = [
    "aranjuez", "manrique", "belen", "belén", "laureles", "castilla", "robledo",
    "la america", "la américa", "santa elena", "santa elena", "san javier",
    "el poblado", "guayabal", "la candelaria", "villa hermosa", "buenos aires",
    "prado", "carlos e restrepo", "conquistadores", "calasanz", "floresta",
    "santa teresita", "los colores", "el estadio", "suramericana", "bello",
    "itagui", "itagüí", "envigado", "sabaneta", "la estrella", "san antonio de prado",
    "copacabana", "girardota", "caldas", "la pintada", "guarne", "el centro",
    "boston", "villa del prado", "campo amor", "industriales", "el volador",
    "san cristobal", "san cristóbal", "altavista", "san sebastian de palmitas",
    "santa barbara", "santa bárbara", "el dorado", "loma hermosa", "picacho",
    "aranjuez", "andalucia", "andalucía", "popular", "santa cruz", "doce de octubre",
    "castilla", "guayabal", "belén", "laureles", "el estadio",
]

_FILLER_RE = re.compile(
    r"\b(eventos?|actividades?|culturales?|conciertos?|teatros?|musica|en|de|del|para"
    r"|con|la|el|los|las|una?|este|esta|pr[oó]ximos?|pr[oó]ximas?|hoy|ma[nñ]ana"
    r"|semana|fin de semana|cerca|medellin|colombia|antioquia)\b",
    re.IGNORECASE,
)


def _clean_search_text(text: str) -> str:
    """Elimina palabras de relleno para aislar el término de búsqueda relevante."""
    if not text:
        return ""
    clean = _FILLER_RE.sub(" ", _normalize_text(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:80]


def _extract_barrio_from_text(text: Optional[str]) -> Optional[str]:
    """Detecta si el texto libre del usuario menciona un barrio/zona conocida.

    Ordena por longitud descendente para que "la america" se detecte antes que "america".
    """
    if not text:
        return None
    t = _normalize_text(text)
    for barrio in sorted(_BARRIOS_MEDELLIN, key=len, reverse=True):
        barrio_norm = _normalize_text(barrio)
        if barrio_norm in t:
            return barrio_norm
    return None


def _build_google_queries(
    municipio: Optional[str],
    categoria: Optional[str],
    colectivo_nombre: Optional[str],
    texto: Optional[str],
    barrio: Optional[str] = None,
) -> list[str]:
    """Construye queries priorizando el texto libre del usuario (búsqueda semántica ligera).

    Estrategia de queries:
    1. Si hay barrio: primero buscar en ese barrio específico → máxima precisión
    2. Texto libre primero (lo que el usuario pidió) + contexto geográfico
    3. Fuentes oficiales de la ciudad (alcaldía, instituciones)
    4. Fuentes de colectivos (Instagram, Facebook local)
    5. Ticketeras (Eventbrite, TuBoleta)
    """
    q_parts = [p for p in [colectivo_nombre, categoria, texto] if p]
    base = " ".join(q_parts).strip() or "eventos culturales"
    region = barrio or municipio or "Medellín"
    ciudad = municipio or "Medellín"

    queries = []

    # Búsqueda hiper-local si hay barrio (ej: "aranjuez rock" → busca en Aranjuez)
    if barrio:
        queries.append(f"{base} {barrio} {ciudad}")
        queries.append(f"colectivos culturales {barrio} {ciudad} agenda")
        queries.append(f"site:instagram.com {base} {barrio}")
        queries.append(f"eventos hoy fin de semana {barrio} {ciudad}")

    queries += [
        f"{base} agenda cultural {region}",
        f"{base} concierto teatro taller {ciudad}",
        f"colectivos culturales {base} {ciudad}",
        f"site:instagram.com {base} evento {ciudad}",
        f"site:facebook.com events {base} {ciudad}",
        f"agenda cultural gratis {ciudad} hoy fin de semana",
        f"cartelera cultural {ciudad} {base}",
        f"programacion cultural {ciudad} {base}",
        f"site:eventbrite.com {base} {ciudad}",
        f"site:tuboleta.com {base} {ciudad}",
        f"cultura medellín {base} unofficial colectivo",
        f"eventos hoy mañana fin de semana {ciudad}",
    ]
    # Deduplicar preservando orden
    seen: set = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


async def _google_search_urls(query: str, max_results: int = 8) -> list[str]:
    import asyncio
    def _search():
        try:
            from ddgs import DDGS
            results = DDGS().text(query, max_results=max_results)
            return [x['href'] for x in results] if results else []
        except Exception as e:
            return []
    return await asyncio.to_thread(_search)


VALLE_ABURRA_MUNICIPIOS = [
    "medellin",
    "envigado",
    "itagui",
    "bello",
    "sabaneta",
    "la estrella",
]


async def _fetch_text_from_url(url: str) -> Optional[str]:
    headers = {
        "User-Agent": UA,
        "Accept-Language": ACCEPT_LANG,
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except Exception:
        return None

    try:
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        soup = BeautifulSoup(resp.text, "html.parser")

    og_img = None
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        og_img = tag.get("content")

    for t in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        t.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if og_img:
        text = f"[OG_IMAGE: {og_img}]\n{text}"
    return text[:7000]


async def _fetch_html_from_url(url: str) -> Optional[str]:
    headers = {
        "User-Agent": UA,
        "Accept-Language": ACCEPT_LANG,
    }
    html = None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        html = None

    if html and len(html) >= 120:
        return html

    # Fallback to full browser render for JS-heavy sites.
    browser_html = await _fetch_html_via_browser(url)
    if browser_html and len(browser_html) >= 120:
        return browser_html
    return html


async def _fetch_html_via_browser(url: str) -> Optional[str]:
    if async_playwright is None:
        return None
    browser = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(user_agent=UA, locale="es-CO")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            return await page.content()
    except Exception:
        return None
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def _search_urls_with_browser(query: str, max_results: int = 8) -> list[str]:
    if async_playwright is None:
        return []

    collected: list[str] = []
    browser = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(user_agent=UA, locale="es-CO")
            bing_url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=es-CO&cc=CO"
            await page.goto(bing_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1200)

            links = await page.eval_on_selector_all(
                "li.b_algo h2 a[href], a[href]",
                "els => els.map(e => e.href)",
            )
            for href in links or []:
                if not isinstance(href, str) or not href.startswith("http"):
                    continue
                if any(skip in href for skip in ["bing.com", "microsoft.com"]):
                    continue
                if href not in collected:
                    collected.append(href)
                if len(collected) >= max_results:
                    break
    except Exception:
        return collected
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return collected


def _extract_og_image_from_html(html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return str(tag.get("content"))
    return None


async def _scrape_known_sites(
    *,
    municipio: Optional[str],
    categoria: Optional[str],
    texto: Optional[str] = None,
    max_sites: int = 6,
) -> list[dict]:
    """Directly scrape known Medellín cultural sites using code-based parsers.

    Filters by municipio and/or categoria when provided. Returns raw event dicts
    as returned by extract_events_code() (NOT yet _build_candidate_event_data).
    """
    def _matches(site: dict) -> bool:
        # Filtra por municipio y categoría — NO por texto libre.
        # El texto libre es para queries de Google, no para filtrar sitios conocidos.
        if municipio and site.get("municipio") and site["municipio"] != municipio:
            return False
        if categoria and site.get("categorias"):
            cat_norm = categoria.replace("_", " ").lower()
            site_cats = [c.replace("_", " ").lower() for c in site["categorias"]]
            if not any(cat_norm in sc or sc in cat_norm for sc in site_cats):
                return False
        return True

    matching_sites = [s for s in KNOWN_CULTURAL_SITES if _matches(s)]
    if not matching_sites:
        # Sin match por categoría → scrapar todos los sitios del municipio
        matching_sites = [s for s in KNOWN_CULTURAL_SITES if not municipio or s.get("municipio") == municipio]
    if not matching_sites:
        matching_sites = list(KNOWN_CULTURAL_SITES)

    async def _fetch_site(site: dict) -> list[dict]:
        html = await _fetch_html_from_url(site["url"])
        if not html:
            return []
        cat = site["categorias"][0] if site["categorias"] else "otro"
        events = extract_events_code(html, site["url"], site["nombre"], cat, site["municipio"])
        print(f"  [known_sites] {site['nombre']}: {len(events)} evento(s)")
        return events

    tasks = [_fetch_site(s) for s in matching_sites[:max_sites]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    found: list[dict] = []
    for r in results:
        if isinstance(r, list):
            found.extend(r)
    return found


def _resolve_colectivo_by_slug(slug: Optional[str]) -> Optional[dict]:
    if not slug:
        return None
    try:
        resp = (
            supabase.table("lugares")
            .select("id,slug,nombre,categoria_principal,municipio,barrio,sitio_web,instagram_handle")
            .eq("slug", slug)
            .single()
            .execute()
        )
        return resp.data
    except Exception:
        return None


def _find_candidate_lugares(
    *,
    municipio: Optional[str],
    categoria: Optional[str],
    texto: Optional[str],
    barrio: Optional[str] = None,
    limit: int = 12,
) -> list[dict]:
    """Find likely matching lugares for user search filters.

    This allows the public discovery flow to scrape places relevant to what
    users typed, not only a generic zona sample.
    """
    try:
        query = supabase.table("lugares").select(
            "id,nombre,slug,municipio,barrio,categoria_principal,sitio_web,instagram_handle"
        )
        if municipio:
            query = query.eq("municipio", municipio)
        if categoria:
            query = query.eq("categoria_principal", categoria)
        if barrio:
            # Búsqueda directa por barrio — máxima precisión
            query = query.ilike("barrio", f"%{barrio}%")
        elif texto:
            # Limpiar texto libre de palabras de relleno antes de buscar
            clean = _clean_search_text(texto)
            if clean:
                query = query.or_(
                    f"nombre.ilike.%{clean}%,"
                    f"barrio.ilike.%{clean}%,"
                    f"municipio.ilike.%{clean}%"
                )
        resp = query.limit(limit).execute()
        lugares = resp.data or []
        if lugares:
            return lugares

        # Si el texto/barrio fue demasiado restrictivo, reintentar solo por municipio/categoría.
        relaxed = supabase.table("lugares").select(
            "id,nombre,slug,municipio,barrio,categoria_principal,sitio_web,instagram_handle"
        )
        if municipio:
            relaxed = relaxed.eq("municipio", municipio)
        if categoria:
            relaxed = relaxed.eq("categoria_principal", categoria)
        relaxed_resp = relaxed.limit(limit).execute()
        return relaxed_resp.data or []
    except Exception:
        return []


async def _scrape_candidate_lugares_websites(
    *,
    lugares: list[dict],
    categoria: Optional[str],
    municipio: Optional[str],
) -> list[dict]:
    """Scrape website pages from DB lugares using pure code extractors.

    This reuses the same parser stack (JSON-LD, microdata, site-specific, generic)
    and does not rely on Google search result pages.
    """
    if not lugares:
        return []

    async def _fetch_lugar(lugar: dict) -> list[dict]:
        sitio_web = (lugar.get("sitio_web") or "").strip()
        cat = categoria or lugar.get("categoria_principal") or "otro"
        muni = municipio or lugar.get("municipio") or "medellin"
        nombre = lugar.get("nombre") or "Lugar cultural"
        merged: list[dict] = []

        if sitio_web:
            html = await _fetch_html_from_url(sitio_web)
            if html:
                web_events = extract_events_code(html, sitio_web, nombre, cat, muni)
                for ev in web_events:
                    ev["_source"] = sitio_web
                merged.extend(web_events)

        ig_raw = (lugar.get("instagram_handle") or "").strip()
        ig_handle = ig_raw.lstrip("@").split("/")[0].strip()
        if ig_handle:
            try:
                from app.services.auto_scraper import _fetch_ig_profile_via_meta_api
                from app.services.instagram_pw_scraper import fetch_ig_profile
                from app.services.ig_event_extractor import extract_events_from_ig_profile

                profile = await _fetch_ig_profile_via_meta_api(ig_handle)
                if not profile:
                    profile = await fetch_ig_profile(ig_handle)
                if profile:
                    ig_events = extract_events_from_ig_profile(profile, nombre, cat, muni)
                    profile_url = f"https://www.instagram.com/{ig_handle}/"
                    for ev in ig_events:
                        ev["_source"] = ev.get("_permalink") or profile_url
                    merged.extend(ig_events)
            except Exception:
                pass

        print(f"  [lugares_db] {nombre}: {len(merged)} evento(s)")
        return merged

    tasks = [_fetch_lugar(l) for l in lugares]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    found: list[dict] = []
    for r in results:
        if isinstance(r, list):
            found.extend(r)
    return found


def _parse_iso_maybe(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CO_TZ)
    return dt.astimezone(CO_TZ)


def _enrich_event_description(descripcion: Optional[str], fecha: datetime) -> str:
    base = (descripcion or "").strip()
    if not base:
        base = "Evento cultural detectado durante la búsqueda web."
    return base


def _build_candidate_event_data(
    ev: dict,
    *,
    source_url: str,
    default_categoria: Optional[str],
    default_municipio: Optional[str],
    colectivo: Optional[dict],
    days_from: Optional[int] = None,
    days_ahead: Optional[int] = None,
    strict_categoria: bool = False,
    required_es_gratuito: Optional[bool] = None,
) -> Optional[dict]:
    titulo = ev.get("titulo")
    if not titulo:
        return None
    if not is_likely_cultural_event(
        titulo,
        ev.get("descripcion"),
        fuente_url=source_url,
        categoria=ev.get("categoria_principal") or default_categoria,
    ):
        return None

    fecha = _parse_iso_maybe(ev.get("fecha_inicio"))
    if not fecha:
        return None

    fecha = _normalize_scraped_datetime(fecha, "google_discovery")
    now_co = datetime.now(ZoneInfo("America/Bogota"))
    if fecha < now_co - timedelta(days=1):
        return None
    if days_from is not None:
        min_date = (now_co + timedelta(days=max(0, days_from))).date()
        if fecha.date() < min_date:
            return None
    if days_ahead is not None:
        max_date = (now_co + timedelta(days=days_ahead)).date()
        if fecha.date() > max_date:
            return None

    fecha_fin = _parse_iso_maybe(ev.get("fecha_fin"))
    base_slug = _slugify(titulo)
    slug = f"{base_slug}-{fecha.strftime('%Y-%m-%d')}"

    extracted_categoria = ev.get("categoria_principal") or "otro"
    categoria = default_categoria if (strict_categoria and default_categoria) else (extracted_categoria or default_categoria or "otro")
    categorias = ev.get("categorias") or [extracted_categoria]
    if default_categoria and default_categoria not in categorias:
        categorias = [default_categoria, *categorias]
    municipio = ev.get("municipio") or default_municipio or (colectivo or {}).get("municipio")
    nombre_lugar = ev.get("nombre_lugar") or (colectivo or {}).get("nombre") or "Descubierto en web"

    evento_data = {
        "titulo": titulo,
        "slug": slug,
        "espacio_id": (colectivo or {}).get("id"),
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
        "hora_confirmada": False,
        "categorias": categorias,
        "categoria_principal": categoria,
        "municipio": municipio,
        "barrio": ev.get("barrio") or (colectivo or {}).get("barrio"),
        "nombre_lugar": nombre_lugar,
        "descripcion": _enrich_event_description(ev.get("descripcion"), fecha),
        "precio": ev.get("precio"),
        "es_gratuito": ev.get("es_gratuito", False),
        "es_recurrente": ev.get("es_recurrente", False),
        "imagen_url": ev.get("imagen_url"),
        "fuente": "google_discovery",
        "fuente_url": source_url,
        "verificado": False,
    }
    if required_es_gratuito is not None and bool(evento_data.get("es_gratuito")) is not required_es_gratuito:
        return None
    return _sanitize_payload(evento_data)


def _event_exists(slug: str) -> bool:
    try:
        exists = supabase.table("eventos").select("id").eq("slug", slug).execute()
        return bool(exists.data)
    except Exception:
        return False


def _insert_discovered_event(evento_data: dict) -> tuple[bool, bool]:
    slug = evento_data.get("slug")
    if not slug:
        return False, False
    if _event_exists(slug):
        return False, True

    evento_data = _sanitize_payload(evento_data)
    supabase.table("eventos").insert(evento_data).execute()
    return True, False


# ─── Scheduling Poisson: ¿cuándo scrapar cada fuente? ────────────────────────

def _poisson_should_scrape(fuente_url: str, window_hours: float = 6.0) -> bool:
    """Proceso de Poisson homogéneo para decidir si scrapar una fuente ahora.

    λ = eventos_nuevos_últimos_7días / 7  (tasa diaria de publicación)
    P(al menos 1 evento nuevo en window_hours) = 1 - e^(-λ * window_hours/24)

    Si P > umbral (0.35), vale la pena scrapar ahora.
    Fuentes sin historial: scrapar siempre (prior optimista).
    """
    try:
        hace_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
        resp = (
            supabase.table("eventos")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("fuente_url", fuente_url)
            .gte("created_at", hace_7d)
            .execute()
        )
        k7 = resp.count or len(resp.data or [])
    except Exception:
        return True  # sin datos → scrapar (prior optimista)

    lam_daily = k7 / 7.0  # λ eventos/día
    prob = 1.0 - math.exp(-lam_daily * window_hours / 24.0)
    return prob > 0.35  # umbral configurable


def _rank_lugares_by_poisson(lugares: list[dict]) -> list[dict]:
    """Ordena lugares candidatos por probabilidad Poisson de tener eventos nuevos.

    Lugares con más actividad reciente en la BD van primero — el scraper
    prioriza los que estadísticamente tienen mayor tasa de publicación.
    """
    def _lambda(lugar: dict) -> float:
        try:
            hace_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
            resp = (
                supabase.table("eventos")
                .select("id", count="exact")  # type: ignore[arg-type]
                .eq("espacio_id", lugar["id"])
                .gte("created_at", hace_7d)
                .execute()
            )
            k7 = resp.count or len(resp.data or [])
            return k7 / 7.0
        except Exception:
            return 0.5  # prior neutro

    return sorted(lugares, key=_lambda, reverse=True)


async def discover_events_for_filters(
    *,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    colectivo_slug: Optional[str] = None,
    texto: Optional[str] = None,
    barrio: Optional[str] = None,
    max_queries: int = 4,
    max_results_per_query: int = 6,
    days_from: int = 0,
    days_ahead: Optional[int] = None,
    strict_categoria: bool = False,
    auto_insert: bool = True,
) -> dict:
    """Discover events when filter views are empty.

    Strategy:
    1) Google discovery by filters.
    2) Return normalized candidate cards.
    3) Optionally insert when auto_insert=True.
    """
    stats = {
        "nuevos": 0,
        "duplicados": 0,
        "errores": 0,
        "encontrados": 0,
        "consultas": [],
        "urls_analizadas": 0,
        "colectivo": None,
        "candidatos": [],
        "variables": {},
    }

    municipio = _normalize_text(municipio) or None
    categoria = _normalize_text(categoria) or None
    texto = (texto or "").strip() or None
    barrio = (barrio or "").strip() or None

    # Auto-detectar barrio desde el texto libre si el usuario no lo pasó explícitamente.
    # Ej: "eventos en aranjuez" → barrio = "aranjuez"
    if not barrio and texto:
        barrio = _extract_barrio_from_text(texto)

    colectivo = _resolve_colectivo_by_slug(colectivo_slug)
    if colectivo:
        stats["colectivo"] = colectivo.get("slug")

    stats["variables"] = {
        "tipo_evento": categoria or "cultural",
        "zona": municipio or (colectivo or {}).get("municipio") or "valle de aburra",
        "fecha_actual": datetime.now(CO_TZ).strftime("%Y-%m-%d"),
        "days_from": str(days_from),
        "days_ahead": str(days_ahead) if days_ahead is not None else "",
        "texto_usuario": texto or "",
        "tipo_precio": _precio_label(es_gratuito),
        "barrio": barrio or "",
    }

    # ── 1. Direct scrape of known Medellín cultural sites (reliable, no Google) ──
    known_events = await _scrape_known_sites(
        municipio=municipio,
        categoria=categoria,
        texto=texto,
        max_sites=10,
    )
    known_source = "conocido_directo"
    for ev in known_events:
        try:
            evento_data = _build_candidate_event_data(
                ev,
                source_url=ev.get("_source") or known_source,
                default_categoria=categoria,
                default_municipio=municipio,
                colectivo=colectivo,
                days_from=days_from,
                days_ahead=days_ahead,
                strict_categoria=strict_categoria,
                required_es_gratuito=es_gratuito,
            )
            if not evento_data:
                continue
            stats["encontrados"] += 1
            if len(stats["candidatos"]) < 80:
                stats["candidatos"].append(evento_data)
            if auto_insert:
                inserted, duplicate = _insert_discovered_event(evento_data)
                if inserted:
                    stats["nuevos"] += 1
                elif duplicate:
                    stats["duplicados"] += 1
        except Exception:
            stats["errores"] += 1

    # ── 2. Scrape websites from matching lugares en DB, priorizados por Poisson ──
    candidate_lugares = _find_candidate_lugares(
        municipio=municipio,
        categoria=categoria,
        texto=texto,
        barrio=barrio or stats["variables"].get("barrio") or None,
        limit=24,
    )
    # Ordenar por tasa Poisson (λ) — lugares que publican más eventos van primero
    candidate_lugares = _rank_lugares_by_poisson(candidate_lugares)
    if colectivo:
        cid = colectivo.get("id")
        if cid and not any((l.get("id") == cid) for l in candidate_lugares):
            candidate_lugares.insert(0, colectivo)
    lugares_events = await _scrape_candidate_lugares_websites(
        lugares=candidate_lugares,
        categoria=categoria,
        municipio=municipio,
    )
    for ev in lugares_events:
        try:
            evento_data = _build_candidate_event_data(
                ev,
                source_url=ev.get("_source") or "lugares_db",
                default_categoria=categoria,
                default_municipio=municipio,
                colectivo=colectivo,
                days_from=days_from,
                days_ahead=days_ahead,
                strict_categoria=strict_categoria,
                required_es_gratuito=es_gratuito,
            )
            if not evento_data:
                continue
            stats["encontrados"] += 1
            if len(stats["candidatos"]) < 80:
                stats["candidatos"].append(evento_data)
            if auto_insert:
                inserted, duplicate = _insert_discovered_event(evento_data)
                if inserted:
                    stats["nuevos"] += 1
                elif duplicate:
                    stats["duplicados"] += 1
        except Exception:
            stats["errores"] += 1

    # ── 3. Google discovery (last resort — fills remaining gaps) ─────────────
    _barrio = stats["variables"].get("barrio") or None
    queries = _build_google_queries(
        municipio=municipio,
        categoria=categoria,
        colectivo_nombre=(colectivo or {}).get("nombre"),
        texto=texto,
        barrio=_barrio,
    )[:max_queries]

    seen_urls: set[str] = set()
    for query in queries:
        stats["consultas"].append(query)
        urls = await _google_search_urls(query, max_results=max_results_per_query)
        await asyncio.sleep(2)  # Avoid rate limiting from search engines
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            stats["urls_analizadas"] += 1

            html = await _fetch_html_from_url(url)
            if not html or len(html) < 120:
                continue
            og_image = _extract_og_image_from_html(html)

            # Code-first extraction only: no paid AI fallback.
            events = extract_events_code(
                html,
                url,
                (colectivo or {}).get("nombre") or "Descubierto en Google",
                categoria or "otro",
                municipio or (colectivo or {}).get("municipio") or "medellin",
            )
            if not events:
                continue

            for ev in events:
                try:
                    if not ev.get("imagen_url") and og_image:
                        ev["imagen_url"] = og_image
                    evento_data = _build_candidate_event_data(
                        ev,
                        source_url=url,
                        default_categoria=categoria,
                        default_municipio=municipio,
                        colectivo=colectivo,
                        days_from=days_from,
                        days_ahead=days_ahead,
                        strict_categoria=strict_categoria,
                        required_es_gratuito=es_gratuito,
                    )
                    if not evento_data:
                        continue

                    stats["encontrados"] += 1
                    if len(stats["candidatos"]) < 80:
                        stats["candidatos"].append(evento_data)

                    if auto_insert:
                        inserted, duplicate = _insert_discovered_event(evento_data)
                        if inserted:
                            stats["nuevos"] += 1
                        elif duplicate:
                            stats["duplicados"] += 1
                except Exception:
                    stats["errores"] += 1

    # Keep only unique candidates by slug (or title+date fallback).
    deduped: list[dict] = []
    seen_keys: set[str] = set()
    for ev in stats["candidatos"]:
        key = ev.get("slug") or f"{(ev.get('titulo') or '').strip().lower()}::{str(ev.get('fecha_inicio') or '')[:10]}"
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(ev)
    stats["candidatos"] = deduped[:80]
    stats["encontrados"] = len(stats["candidatos"])

    try:
        supabase.table("scraping_log").insert(
            {
                "fuente": "google_discovery_publico",
                "registros_nuevos": stats["nuevos"],
                "registros_actualizados": 0,
                "errores": stats["errores"],
                "detalle": {
                    "auto_insert": auto_insert,
                    "municipio": municipio,
                    "categoria": categoria,
                    "colectivo_slug": colectivo_slug,
                    "texto": texto,
                    **stats,
                },
            }
        ).execute()
    except Exception:
        pass

    return stats


def commit_discovered_events(candidatos: list[dict]) -> dict:
    """Insert candidate events selected by the user contribution flow."""
    result = {
        "nuevos": 0,
        "duplicados": 0,
        "errores": 0,
    }
    for ev in candidatos or []:
        try:
            if not is_likely_cultural_event(
                ev.get("titulo"),
                ev.get("descripcion"),
                fuente_url=ev.get("fuente_url"),
                categoria=ev.get("categoria_principal"),
            ):
                result["errores"] += 1
                continue
            inserted, duplicate = _insert_discovered_event(ev)
            if inserted:
                result["nuevos"] += 1
            elif duplicate:
                result["duplicados"] += 1
        except Exception:
            result["errores"] += 1
    return result

