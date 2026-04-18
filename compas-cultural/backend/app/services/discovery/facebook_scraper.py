# -*- coding: utf-8 -*-
"""
Facebook scraper — Busca colectivos culturales en Facebook vía Google.
"""
import logging
import re

from bs4 import BeautifulSoup

from .config import CATEGORIAS, MUNICIPIOS, FB_SEARCH_QUERIES
from .utils import (
    fetch_url, clean_text, extract_emails, extract_phones, polite_delay,
)

logger = logging.getLogger("discovery.facebook")


async def facebook_search_via_google(query: str, num: int = 10) -> list[dict]:
    """Busca páginas de Facebook a través de Google."""
    gquery = f"site:facebook.com {query}"
    params = {"q": gquery, "num": num, "hl": "es", "gl": "co"}
    resp = await fetch_url("https://www.google.com/search", params=params)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for g in soup.select("div.g, div[data-hveid]"):
        link = g.select_one("a[href*='facebook.com']")
        if not link:
            continue
        href = link["href"]
        title = link.get_text(strip=True)
        snippet_el = g.select_one("span.st, div.VwiC3b, div[data-sncf]")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        results.append({"title": title, "url": href, "snippet": snippet})
    return results


async def scrape_facebook_page(url: str) -> dict:
    """Extrae info básica de una página pública de Facebook."""
    resp = await fetch_url(url)
    if not resp:
        return {}

    info = {"url": url}
    soup = BeautifulSoup(resp.text, "lxml")

    og_title = soup.find("meta", property="og:title")
    if og_title:
        info["nombre"] = og_title.get("content", "")

    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        desc = og_desc.get("content", "")
        info["descripcion"] = clean_text(desc)[:500]
        info["emails"] = extract_emails(desc)
        info["phones"] = extract_phones(desc)

    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        info["imagen"] = og_image["content"]

    match = re.search(r"facebook\.com/([A-Za-z0-9_.]+)", url)
    if match:
        handle = match.group(1).lower()
        skip = {"pages", "groups", "events", "profile.php", "people", "watch", "photo"}
        if handle not in skip:
            info["handle"] = f"@{handle}"

    return info


def _classify_fb(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cat, kws in CATEGORIAS.items():
        score = sum(1 for kw in kws if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "arte_general"


def _guess_municipio_fb(text: str) -> str:
    text_lower = text.lower()
    for mun in MUNICIPIOS:
        if mun.lower() in text_lower:
            return mun
    return "Medellín"


async def scrape_facebook(max_queries: int = 30) -> list[dict]:
    """Busca colectivos en Facebook vía Google."""
    queries = FB_SEARCH_QUERIES
    if max_queries > 0:
        queries = queries[:max_queries]

    logger.info(f"Facebook scraper: {len(queries)} queries")
    colectivos = []
    seen = set()

    for i, qinfo in enumerate(queries, 1):
        if i % 10 == 0:
            logger.info(f"  [{i}/{len(queries)}] progreso...")
        results = await facebook_search_via_google(qinfo["q"])

        for r in results:
            url = r["url"]
            title = r["title"]
            snippet = r.get("snippet", "")
            full_text = f"{title} {snippet}"

            match = re.search(r"facebook\.com/([A-Za-z0-9_.]+)", url)
            if not match:
                continue
            raw_handle = match.group(1).lower()
            skip = {"pages", "groups", "events", "profile.php", "people", "watch", "photo"}
            if raw_handle in skip:
                continue

            uid = f"facebook::@{raw_handle}"
            if uid in seen:
                continue
            seen.add(uid)

            nombre = re.sub(
                r"\s*[\-–|•]\s*(Facebook|Meta).*$", "",
                clean_text(title), flags=re.IGNORECASE,
            ).strip()

            emails = extract_emails(full_text)
            phones = extract_phones(full_text)

            col = {
                "nombre": nombre or raw_handle,
                "handle": f"@{raw_handle}",
                "plataforma": "facebook",
                "url": url,
                "categoria": qinfo["categoria"],
                "municipio": qinfo.get("municipio", _guess_municipio_fb(full_text)),
                "descripcion": clean_text(snippet)[:300],
                "email": emails[0] if emails else "",
                "telefono": phones[0] if phones else "",
                "fuente": "facebook_google_search",
            }
            colectivos.append(col)

        await polite_delay()

    logger.info(f"Facebook scraper: {len(colectivos)} páginas únicas")
    return colectivos
