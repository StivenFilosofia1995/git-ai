# -*- coding: utf-8 -*-
"""
Instagram scraper — Descubrimiento por hashtags y perfiles públicos.
"""
import json
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .config import CATEGORIAS, MUNICIPIOS, HASHTAGS_MEDELLIN
from .utils import (
    fetch_url, clean_text, extract_handles,
    extract_emails, extract_phones, extract_og_image, polite_delay,
)

logger = logging.getLogger("discovery.instagram")


async def scrape_instagram_hashtag(tag: str) -> list[dict]:
    """Obtiene posts de un hashtag de Instagram vía web pública."""
    url = f"https://www.instagram.com/explore/tags/{quote_plus(tag)}/"
    resp = await fetch_url(url)
    if not resp:
        return []

    results = []
    soup = BeautifulSoup(resp.text, "lxml")

    # JSON embebido en <script> tags
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                results.extend(_parse_ig_json(data))
            elif isinstance(data, list):
                for item in data:
                    results.extend(_parse_ig_json(item))
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: buscar usernames en HTML
    text = resp.text
    usernames = set(re.findall(r'"username"\s*:\s*"([A-Za-z0-9_.]+)"', text))
    for uname in usernames:
        if uname not in [r.get("username") for r in results]:
            results.append({
                "username": uname,
                "caption": "",
                "url": f"https://www.instagram.com/{uname}/",
            })

    return results


def _parse_ig_json(data: dict) -> list[dict]:
    """Extrae posts/usuarios de JSON embebidos de Instagram."""
    items = []
    if "author" in data:
        author = data["author"]
        uname = (author.get("alternateName", "").strip("@")
                 or author.get("identifier", {}).get("value", ""))
        if uname:
            items.append({
                "username": uname,
                "caption": data.get("caption", ""),
                "url": data.get("url", f"https://www.instagram.com/{uname}/"),
                "image": data.get("image", ""),
            })
    # Estructura GraphQL
    for key in ("edge_hashtag_to_media", "edge_owner_to_timeline_media"):
        if key in data:
            edges = data[key].get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                owner = node.get("owner", {})
                uname = owner.get("username", "")
                cap_edges = node.get("edge_media_to_caption", {}).get("edges", [])
                caption = cap_edges[0]["node"]["text"] if cap_edges else ""
                if uname:
                    items.append({
                        "username": uname,
                        "caption": caption,
                        "url": f"https://www.instagram.com/{uname}/",
                        "image": node.get("display_url", ""),
                    })
    return items


async def scrape_instagram_profile(username: str) -> dict:
    """Obtiene datos públicos de un perfil de Instagram."""
    url = f"https://www.instagram.com/{username}/"
    resp = await fetch_url(url)
    if not resp:
        return {}

    info = {"username": username, "url": url}
    soup = BeautifulSoup(resp.text, "lxml")

    og_title = soup.find("meta", property="og:title")
    if og_title:
        info["nombre"] = og_title.get("content", "").split("(")[0].strip()

    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        desc = og_desc.get("content", "")
        info["descripcion"] = clean_text(desc)[:500]
        m = re.search(r"([\d,.]+[KkMm]?)\s*(?:Followers|seguidores)", desc, re.IGNORECASE)
        if m:
            info["seguidores"] = m.group(1)
        info["emails"] = extract_emails(desc)
        info["phones"] = extract_phones(desc)

    img = extract_og_image(soup)
    if img:
        info["imagen"] = img

    # JSON embebido
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                info["nombre"] = info.get("nombre") or data.get("name", "")
                info["descripcion"] = info.get("descripcion") or data.get("description", "")
        except (json.JSONDecodeError, TypeError):
            continue

    return info


def _classify_category(text: str) -> str:
    """Categoría más probable basada en keywords."""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORIAS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    return max(scores, key=scores.get) if scores else "arte_general"


def _guess_municipio(text: str) -> str:
    """Detecta municipio mencionado en texto."""
    text_lower = text.lower()
    for mun in MUNICIPIOS:
        if mun.lower() in text_lower:
            return mun
    return "Medellín"


async def scrape_instagram(max_hashtags: int = 0) -> list[dict]:
    """Scraping de Instagram por hashtags. Retorna colectivos descubiertos."""
    tags = HASHTAGS_MEDELLIN
    if max_hashtags > 0:
        tags = tags[:max_hashtags]

    logger.info(f"Instagram scraper: {len(tags)} hashtags")
    colectivos = []
    seen = set()

    for i, tag in enumerate(tags, 1):
        logger.info(f"  [{i}/{len(tags)}] #{tag}")
        posts = await scrape_instagram_hashtag(tag)
        for post in posts:
            uname = post["username"]
            uid = f"instagram::@{uname.lower()}"
            if uid in seen:
                continue
            seen.add(uid)

            profile = await scrape_instagram_profile(uname)
            caption = post.get("caption", "")
            desc = profile.get("descripcion", caption)
            cat = _classify_category(f"{desc} {tag}")

            col = {
                "nombre": profile.get("nombre", uname),
                "handle": f"@{uname}",
                "plataforma": "instagram",
                "url": f"https://www.instagram.com/{uname}/",
                "categoria": cat,
                "municipio": _guess_municipio(desc),
                "descripcion": clean_text(desc)[:300],
                "email": (profile.get("emails") or [""])[0] if profile.get("emails") else "",
                "telefono": (profile.get("phones") or [""])[0] if profile.get("phones") else "",
                "imagen": profile.get("imagen") or post.get("image", ""),
                "seguidores": profile.get("seguidores", ""),
                "fuente": f"instagram_hashtag:#{tag}",
            }
            colectivos.append(col)
            logger.info(f"    ✓ @{uname} — {col['nombre']} [{cat}]")

        await polite_delay()

    logger.info(f"Instagram scraper: {len(colectivos)} perfiles únicos")
    return colectivos
