# -*- coding: utf-8 -*-
"""
Directory scraper — Scrapea directorios culturales institucionales.
"""
import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .config import CATEGORIAS, MUNICIPIOS, FUENTES_DIRECTAS
from .utils import (
    fetch_url, clean_text, detect_platform, handle_from_url,
    extract_handles, extract_emails, extract_phones, extract_og_image,
    polite_delay,
)

logger = logging.getLogger("discovery.directorios")

SOCIAL_LINK_RE = re.compile(
    r"https?://(?:www\.)?(?:instagram|facebook|twitter|x|tiktok)\.com/[A-Za-z0-9_.]+",
    re.IGNORECASE,
)


def _extract_social_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extrae links a redes sociales de una página."""
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if SOCIAL_LINK_RE.match(href):
            links.add(href)
    text = soup.get_text(" ")
    for m in SOCIAL_LINK_RE.finditer(text):
        links.add(m.group(0))
    return list(links)


def _extract_orgs_from_page(text: str) -> list[dict]:
    """Busca menciones de organizaciones culturales en texto."""
    org_patterns = re.findall(
        r"(?:Colectivo|Corporación|Fundación|Asociación|Centro Cultural|"
        r"Casa de la Cultura|Escuela de|Grupo|Compañía|Taller|Club|"
        r"Red|Plataforma|Espacio|Sala)\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{2,40}",
        text,
    )
    orgs = []
    for org_name in set(org_patterns):
        org_name = clean_text(org_name)
        idx = text.find(org_name)
        context = text[max(0, idx - 150):idx + len(org_name) + 300] if idx >= 0 else ""
        handles = extract_handles(context)
        emails = extract_emails(context)
        phones = extract_phones(context)
        if handles or emails:
            orgs.append({
                "nombre": org_name,
                "handles": handles,
                "emails": emails,
                "phones": phones,
            })
    return orgs


def _classify_dir(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cat, kws in CATEGORIAS.items():
        score = sum(1 for kw in kws if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "arte_general"


def _guess_municipio_dir(text: str) -> str:
    text_lower = text.lower()
    for mun in MUNICIPIOS:
        if mun.lower() in text_lower:
            return mun
    return "Medellín"


def _find_subpages(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Encuentra sub-páginas relevantes culturales."""
    keywords = [
        "cultura", "directorio", "colectivo", "organizacion", "agenda",
        "teatro", "musica", "literatura", "arte", "biblioteca",
        "grupo", "comunidad", "festival", "red", "aliado",
    ]
    subpages = []
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if urlparse(href).netloc != base_domain:
            continue
        link_text = (a.get_text(" ").lower() + " " + href.lower())
        if any(kw in link_text for kw in keywords):
            if href not in subpages:
                subpages.append(href)
    return subpages


async def scrape_single_directory(url: str) -> list[dict]:
    """Scrapea un solo directorio cultural y extrae colectivos."""
    logger.info(f"  Scrapeando: {url}")
    colectivos = []

    resp = await fetch_url(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(" ")
    domain = urlparse(url).netloc

    # 1) Links a redes sociales directos
    social_links = _extract_social_links(soup, url)
    for link in social_links:
        handle = handle_from_url(link)
        if not handle:
            continue
        plat = detect_platform(link)
        link_tag = soup.find("a", href=re.compile(re.escape(urlparse(link).path.strip("/"))))
        nombre = ""
        if link_tag:
            parent = link_tag.find_parent(["div", "li", "article", "section", "td", "tr"])
            if parent:
                nombre = clean_text(parent.get_text(" "))[:100]
        nombre = nombre or handle.strip("@")

        col = {
            "nombre": nombre,
            "handle": handle,
            "plataforma": plat,
            "url": link,
            "categoria": _classify_dir(nombre + " " + text[:500]),
            "municipio": _guess_municipio_dir(text),
            "fuente": f"directorio:{domain}",
        }
        colectivos.append(col)

    # 2) Organizaciones mencionadas en texto
    orgs = _extract_orgs_from_page(text)
    for org in orgs:
        for h in org["handles"]:
            col = {
                "nombre": org["nombre"],
                "handle": f"@{h}",
                "plataforma": "desconocida",
                "url": url,
                "categoria": _classify_dir(org["nombre"]),
                "municipio": _guess_municipio_dir(org["nombre"] + " " + text[:300]),
                "email": (org["emails"] or [""])[0] if org.get("emails") else "",
                "telefono": (org["phones"] or [""])[0] if org.get("phones") else "",
                "fuente": f"directorio:{domain}",
            }
            colectivos.append(col)

    # 3) Sub-páginas relevantes (1 nivel)
    subpages = _find_subpages(soup, url)
    for suburl in subpages[:10]:
        sub_resp = await fetch_url(suburl)
        if not sub_resp:
            continue
        sub_soup = BeautifulSoup(sub_resp.text, "lxml")
        sub_links = _extract_social_links(sub_soup, suburl)
        sub_text = sub_soup.get_text(" ")

        for link in sub_links:
            handle = handle_from_url(link)
            if not handle:
                continue
            plat = detect_platform(link)
            col = {
                "nombre": handle.strip("@"),
                "handle": handle,
                "plataforma": plat,
                "url": link,
                "categoria": _classify_dir(sub_text[:500]),
                "municipio": _guess_municipio_dir(sub_text),
                "fuente": f"directorio:{domain}",
            }
            colectivos.append(col)
        await polite_delay()

    return colectivos


async def scrape_directorios(urls: list[str] = None) -> list[dict]:
    """Scrapea todas las fuentes directas."""
    urls = urls or FUENTES_DIRECTAS
    logger.info(f"Directorio scraper: {len(urls)} fuentes")
    all_colectivos = []
    seen = set()

    for url in urls:
        cols = await scrape_single_directory(url)
        for col in cols:
            uid = f"{col.get('plataforma', 'web')}::{col.get('handle', '').lower()}"
            if uid and uid not in seen:
                seen.add(uid)
                all_colectivos.append(col)
        await polite_delay()

    logger.info(f"Directorio scraper: {len(all_colectivos)} colectivos únicos")
    return all_colectivos
