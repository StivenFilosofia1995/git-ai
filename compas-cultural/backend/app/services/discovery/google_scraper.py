# -*- coding: utf-8 -*-
"""
Google scraper — Busca colectivos culturales en Google.
"""
import logging
import re

from bs4 import BeautifulSoup

from .config import (
    CATEGORIAS, MUNICIPIOS, GOOGLE_QUERY_TEMPLATES, MAX_GOOGLE_RESULTS,
)
from .utils import (
    fetch_url, clean_text, detect_platform, handle_from_url,
    extract_handles, extract_emails, extract_phones, polite_delay,
)

logger = logging.getLogger("discovery.google")


def _build_queries(max_per_category: int = 3) -> list[dict]:
    """Genera combinaciones keyword × municipio × template (limitadas)."""
    queries = []
    for cat, keywords in CATEGORIAS.items():
        for kw in keywords[:max_per_category]:
            for mun in MUNICIPIOS[:5]:  # Top 5 municipios
                for tpl in GOOGLE_QUERY_TEMPLATES[:4]:  # Top 4 templates
                    q = tpl.replace("{keyword}", kw).replace("{municipio}", mun)
                    queries.append({"query": q, "categoria": cat, "municipio": mun})
    return queries


async def google_search(query: str, num: int = 10) -> list[dict]:
    """Busca en Google y parsea resultados orgánicos."""
    params = {
        "q": query,
        "num": min(num, MAX_GOOGLE_RESULTS),
        "start": 0,
        "hl": "es",
        "gl": "co",
    }
    resp = await fetch_url("https://www.google.com/search", params=params)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for g in soup.select("div.g, div[data-hveid]"):
        link_tag = g.select_one("a[href^='http']")
        if not link_tag:
            continue
        href = link_tag["href"]
        title = link_tag.get_text(strip=True)
        snippet_el = g.select_one("span.st, div.VwiC3b, div[data-sncf]")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if href and title:
            results.append({"title": title, "url": href, "snippet": snippet})
    return results


def _result_to_colectivo(result: dict, categoria: str, municipio: str) -> dict | None:
    """Convierte resultado de Google a dict de colectivo descubierto."""
    url = result["url"]
    title = result["title"]
    snippet = result.get("snippet", "")
    full_text = f"{title} {snippet}"

    plat = detect_platform(url)
    handle = handle_from_url(url)
    if not handle:
        handles = extract_handles(full_text)
        handle = f"@{handles[0]}" if handles else ""
    if not handle:
        return None

    nombre = clean_text(title)
    nombre = re.sub(
        r"\s*[\-–|•]\s*(Instagram|Facebook|Twitter|X|TikTok).*$",
        "", nombre, flags=re.IGNORECASE,
    ).strip()

    emails = extract_emails(full_text)
    phones = extract_phones(full_text)

    return {
        "nombre": nombre or handle.strip("@"),
        "handle": handle,
        "plataforma": plat,
        "url": url,
        "categoria": categoria,
        "municipio": municipio,
        "descripcion": clean_text(snippet)[:300],
        "email": emails[0] if emails else "",
        "telefono": phones[0] if phones else "",
        "fuente": "google_search",
    }


async def scrape_google(max_queries: int = 50) -> list[dict]:
    """Ejecuta búsquedas de Google y retorna colectivos encontrados."""
    queries = _build_queries()
    if max_queries > 0:
        queries = queries[:max_queries]

    logger.info(f"Google scraper: {len(queries)} queries")
    colectivos = []
    seen = set()

    for i, qinfo in enumerate(queries, 1):
        if i % 10 == 0:
            logger.info(f"  [{i}/{len(queries)}] progreso...")
        results = await google_search(qinfo["query"])
        for r in results:
            col = _result_to_colectivo(r, qinfo["categoria"], qinfo["municipio"])
            if col:
                uid = f"{col['plataforma']}::{col['handle'].lower()}"
                if uid not in seen:
                    seen.add(uid)
                    colectivos.append(col)
        await polite_delay()

    logger.info(f"Google scraper finalizado: {len(colectivos)} colectivos únicos")
    return colectivos
