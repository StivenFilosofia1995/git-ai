from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.database import supabase
from app.services.auto_scraper import (
    CO_TZ,
    EVENT_EXTRACTION_PROMPT,
    _extract_events_with_groq,
    _normalize_scraped_datetime,
    _sanitize_payload,
    _slugify,
    scrape_single_lugar,
    scrape_zona,
)


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text


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

    region = municipio or "Medellin"
    return [
        f"{base} agenda cultural {region}",
        f"{base} concierto teatro taller {region}",
        f"site:instagram.com {base} evento {region}",
        f"site:facebook.com events {base} {region}",
        f"{base} abril mayo junio {region}",
    ]


async def _google_search_urls(query: str, max_results: int = 8) -> list[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    }
    params = {
        "q": query,
        "hl": "es",
        "gl": "co",
        "num": min(max_results, 10),
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://www.google.com/search", params=params, headers=headers)
            resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    urls: list[str] = []
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
    return urls


async def _fetch_text_from_url(url: str) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
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


def _insert_discovered_event(
    ev: dict,
    *,
    source_url: str,
    default_categoria: Optional[str],
    default_municipio: Optional[str],
    colectivo: Optional[dict],
) -> tuple[bool, bool]:
    titulo = ev.get("titulo")
    if not titulo:
        return False, False

    fecha = _parse_iso_maybe(ev.get("fecha_inicio"))
    if not fecha:
        return False, False

    fecha = _normalize_scraped_datetime(fecha, "google_discovery")
    now_co = datetime.now(ZoneInfo("America/Bogota"))
    if fecha < now_co - timedelta(days=1):
        return False, False

    fecha_fin = _parse_iso_maybe(ev.get("fecha_fin"))
    base_slug = _slugify(titulo)
    slug = f"{base_slug}-{fecha.strftime('%Y-%m-%d')}"

    try:
        exists = supabase.table("eventos").select("id").eq("slug", slug).execute()
        if exists.data:
            return False, True
    except Exception:
        return False, False

    categoria = ev.get("categoria_principal") or default_categoria or "otro"
    municipio = ev.get("municipio") or default_municipio or (colectivo or {}).get("municipio")
    nombre_lugar = ev.get("nombre_lugar") or (colectivo or {}).get("nombre") or "Descubierto en web"

    evento_data = {
        "titulo": titulo,
        "slug": slug,
        "espacio_id": (colectivo or {}).get("id"),
        "fecha_inicio": fecha.isoformat(),
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
        "hora_confirmada": not (fecha.hour == 0 and fecha.minute == 0),
        "categorias": ev.get("categorias") or [categoria],
        "categoria_principal": categoria,
        "municipio": municipio,
        "barrio": ev.get("barrio") or (colectivo or {}).get("barrio"),
        "nombre_lugar": nombre_lugar,
        "descripcion": ev.get("descripcion"),
        "precio": ev.get("precio"),
        "es_gratuito": ev.get("es_gratuito", False),
        "es_recurrente": ev.get("es_recurrente", False),
        "imagen_url": ev.get("imagen_url"),
        "fuente": "google_discovery",
        "fuente_url": source_url,
        "verificado": False,
    }
    evento_data = _sanitize_payload(evento_data)
    supabase.table("eventos").insert(evento_data).execute()
    return True, False


async def discover_events_for_filters(
    *,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    colectivo_slug: Optional[str] = None,
    texto: Optional[str] = None,
    max_queries: int = 4,
    max_results_per_query: int = 6,
) -> dict:
    """Discover events when filter views are empty.

    Strategy:
    1) Use internal scrapers first (single lugar / zona).
    2) If still low results, fallback to Google web discovery + LLM extraction.
    3) Insert normalized cards into eventos table so all users benefit.
    """
    stats = {
        "nuevos": 0,
        "duplicados": 0,
        "errores": 0,
        "consultas": [],
        "urls_analizadas": 0,
        "colectivo": None,
    }

    municipio = _normalize_text(municipio) or None
    categoria = _normalize_text(categoria) or None
    texto = (texto or "").strip() or None
    colectivo = _resolve_colectivo_by_slug(colectivo_slug)
    if colectivo:
        stats["colectivo"] = colectivo.get("slug")

    try:
        if colectivo and colectivo.get("id"):
            single = await scrape_single_lugar(colectivo["id"])
            stats["nuevos"] += int(single.get("nuevos", 0) or 0)
            stats["duplicados"] += int(single.get("duplicados", 0) or 0)
    except Exception:
        stats["errores"] += 1

    try:
        if municipio:
            zona = await scrape_zona(municipio, limit=12)
            stats["nuevos"] += int(zona.get("eventos_nuevos", 0) or 0)
            stats["duplicados"] += int(zona.get("duplicados", 0) or 0)
    except Exception:
        stats["errores"] += 1

    # If we already got events from internal sources, still return quickly.
    if stats["nuevos"] > 0:
        return stats

    queries = _build_google_queries(
        municipio=municipio,
        categoria=categoria,
        colectivo_nombre=(colectivo or {}).get("nombre"),
        texto=texto,
    )[:max_queries]

    now_co = datetime.now(CO_TZ)
    anio = now_co.year
    now_iso = now_co.strftime("%Y-%m-%d")

    seen_urls: set[str] = set()
    for query in queries:
        stats["consultas"].append(query)
        urls = await _google_search_urls(query, max_results=max_results_per_query)
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            stats["urls_analizadas"] += 1

            text = await _fetch_text_from_url(url)
            if not text or len(text) < 120:
                continue

            lugar_nombre = (colectivo or {}).get("nombre") or "Descubierto en Google"
            prompt = EVENT_EXTRACTION_PROMPT.format(
                fecha_actual=now_iso,
                anio_actual=anio,
                nombre_lugar=lugar_nombre,
                lugar_id=(colectivo or {}).get("id") or "N/A",
                categoria=categoria or "otro",
                municipio=municipio or (colectivo or {}).get("municipio") or "medellin",
                fuente_tipo="google",
                fuente_url=url,
                contenido=text,
            )
            events = _extract_events_with_groq(prompt)
            if not events:
                continue

            for ev in events:
                try:
                    inserted, duplicate = _insert_discovered_event(
                        ev,
                        source_url=url,
                        default_categoria=categoria,
                        default_municipio=municipio,
                        colectivo=colectivo,
                    )
                    if inserted:
                        stats["nuevos"] += 1
                    elif duplicate:
                        stats["duplicados"] += 1
                except Exception:
                    stats["errores"] += 1

    try:
        supabase.table("scraping_log").insert(
            {
                "fuente": "google_discovery_publico",
                "registros_nuevos": stats["nuevos"],
                "registros_actualizados": 0,
                "errores": stats["errores"],
                "detalle": {
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
