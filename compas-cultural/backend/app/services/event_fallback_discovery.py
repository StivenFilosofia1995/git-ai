from __future__ import annotations

import asyncio
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


def _build_google_queries(
    municipio: Optional[str],
    categoria: Optional[str],
    colectivo_nombre: Optional[str],
    texto: Optional[str],
) -> list[str]:
    q_parts = [p for p in [colectivo_nombre, categoria, texto, municipio] if p]
    base = " ".join(q_parts).strip()
    if not base:
        base = "eventos culturales Medellin"

    region = municipio or "Valle de Aburrá"
    return [
        f"{base} agenda cultural {region}",
        f"{base} concierto teatro taller {region}",
        f"site:instagram.com {base} evento {region}",
        f"site:facebook.com events {base} {region}",
        f"{base} abril mayo junio {region}",
        f"agenda cultural gratis {region} hoy",
        f"eventos hoy mañana fin de semana {region}",
        f"cartelera cultural {region} {base}",
        f"programacion cultural {region} {base}",
        f"site:eventbrite.com {base} {region}",
        f"site:tuboleta.com {base} {region}",
    ]


async def _google_search_urls(query: str, max_results: int = 8) -> list[str]:
    headers = {
        "User-Agent": UA,
        "Accept-Language": ACCEPT_LANG,
    }
    params = {
        "q": query,
        "hl": "es",
        "gl": "co",
        "num": min(max_results, 10),
    }

    urls: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.google.com/search", params=params, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=", 1)[1].split("&", 1)[0]
                if not href.startswith("http"):
                    continue
                if any(skip in href for skip in ["google.com", "webcache", "accounts.google"]):
                    continue
                if href not in urls:
                    urls.append(href)
                if len(urls) >= max_results:
                    break
    except Exception:
        pass

    # Fallback: DuckDuckGo HTML (más estable cuando Google bloquea scraping).
    if len(urls) < max_results:
        ddg_params = {"q": query}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                ddg = await client.get("https://duckduckgo.com/html/", params=ddg_params, headers=headers)
                ddg.raise_for_status()
                soup = BeautifulSoup(ddg.text, "lxml")
                for a in soup.select("a.result__a[href]"):
                    href = a.get("href", "")
                    if not href.startswith("http"):
                        continue
                    if href not in urls:
                        urls.append(href)
                    if len(urls) >= max_results:
                        break
        except Exception:
            pass

    # Fallback 2: Bing HTML.
    if len(urls) < max_results:
        bing_params = {
            "q": query,
            "setlang": "es-CO",
            "cc": "CO",
            "count": min(max_results, 10),
        }
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                bing = await client.get("https://www.bing.com/search", params=bing_params, headers=headers)
                bing.raise_for_status()
                soup = BeautifulSoup(bing.text, "lxml")
                for a in soup.select("li.b_algo h2 a[href], a[href]"):
                    href = a.get("href", "")
                    if not href.startswith("http"):
                        continue
                    if any(skip in href for skip in ["bing.com", "microsoft.com"]):
                        continue
                    if href not in urls:
                        urls.append(href)
                    if len(urls) >= max_results:
                        break
        except Exception:
            pass

    # Fallback 3: browser search (Chromium/Playwright) for anti-bot pages.
    if len(urls) < max_results:
        try:
            browser_urls = await _search_urls_with_browser(query, max_results=max_results)
            for href in browser_urls:
                if href not in urls:
                    urls.append(href)
                if len(urls) >= max_results:
                    break
        except Exception:
            pass
    return urls


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
    max_sites: int = 6,
) -> list[dict]:
    """Directly scrape known Medellín cultural sites using code-based parsers.

    Filters by municipio and/or categoria when provided. Returns raw event dicts
    as returned by extract_events_code() (NOT yet _build_candidate_event_data).
    """
    def _matches(site: dict) -> bool:
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
            .select("id,slug,nombre,categoria_principal,municipio,barrio")
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
    limit: int = 12,
) -> list[dict]:
    """Find likely matching lugares for user search filters.

    This allows the public discovery flow to scrape places relevant to what
    users typed, not only a generic zona sample.
    """
    try:
        query = supabase.table("lugares").select(
            "id,nombre,slug,municipio,barrio,categoria_principal,sitio_web"
        )
        if municipio:
            query = query.eq("municipio", municipio)
        if categoria:
            query = query.eq("categoria_principal", categoria)
        if texto:
            t = texto[:80]
            query = query.or_(
                f"nombre.ilike.%{t}%,"
                f"barrio.ilike.%{t}%,"
                f"municipio.ilike.%{t}%"
            )
        resp = query.limit(limit).execute()
        lugares = resp.data or []
        if lugares:
            return lugares

        # Si el texto fue demasiado restrictivo, reintentar solo por municipio/categoría.
        relaxed = supabase.table("lugares").select(
            "id,nombre,slug,municipio,barrio,categoria_principal,sitio_web"
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
        if not sitio_web:
            return []
        html = await _fetch_html_from_url(sitio_web)
        if not html:
            return []
        cat = categoria or lugar.get("categoria_principal") or "otro"
        muni = municipio or lugar.get("municipio") or "medellin"
        nombre = lugar.get("nombre") or "Lugar cultural"
        events = extract_events_code(html, sitio_web, nombre, cat, muni)
        print(f"  [lugares_db] {nombre}: {len(events)} evento(s)")
        return events

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
    hora_confirmada = not (fecha.hour == 0 and fecha.minute == 0)
    if "hora del evento" in base.lower():
        return base
    hora_label = fecha.astimezone(CO_TZ).strftime("%H:%M")
    prefix = f"Hora del evento: {hora_label}." if hora_confirmada else f"Hora del evento (estimada): {hora_label}."
    return f"{prefix} {base}".strip()


def _build_candidate_event_data(
    ev: dict,
    *,
    source_url: str,
    default_categoria: Optional[str],
    default_municipio: Optional[str],
    colectivo: Optional[dict],
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
        "hora_confirmada": not (fecha.hour == 0 and fecha.minute == 0),
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


async def discover_events_for_filters(
    *,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    colectivo_slug: Optional[str] = None,
    texto: Optional[str] = None,
    max_queries: int = 4,
    max_results_per_query: int = 6,
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
    colectivo = _resolve_colectivo_by_slug(colectivo_slug)
    if colectivo:
        stats["colectivo"] = colectivo.get("slug")

    stats["variables"] = {
        "tipo_evento": categoria or "cultural",
        "zona": municipio or (colectivo or {}).get("municipio") or "valle de aburra",
        "fecha_actual": datetime.now(CO_TZ).strftime("%Y-%m-%d"),
        "texto_usuario": texto or "",
        "tipo_precio": _precio_label(es_gratuito),
    }

    # ── 1. Direct scrape of known Medellín cultural sites (reliable, no Google) ──
    known_events = await _scrape_known_sites(
        municipio=municipio,
        categoria=categoria,
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

    # ── 2. Scrape websites from matching lugares in DB (pure code) ───────────
    candidate_lugares = _find_candidate_lugares(
        municipio=municipio,
        categoria=categoria,
        texto=texto,
        limit=20,
    )
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
    queries = _build_google_queries(
        municipio=municipio,
        categoria=categoria,
        colectivo_nombre=(colectivo or {}).get("nombre"),
        texto=texto,
    )[:max_queries]

    seen_urls: set[str] = set()
    for query in queries:
        stats["consultas"].append(query)
        urls = await _google_search_urls(query, max_results=max_results_per_query)
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
