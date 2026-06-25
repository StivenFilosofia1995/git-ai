# -*- coding: utf-8 -*-
"""
IG Colectivos Discovery — descubre perfiles Instagram de colectivos culturales
alternativos de Medellín y los registra como lugares en la BD.

Estrategia:
1. Seed list de colectivos conocidos (sin red)
2. DuckDuckGo HTML scraping (sin API key)
3. Registra handles nuevos como lugares para que el scraper de Instagram los procese
"""
import re
import unicodedata
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.database import supabase

_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9",
}

_SEARCH_QUERIES = [
    "colectivos culturales medellín site:instagram.com",
    "casas culturales medellín instagram",
    "colectivo arte medellín instagram perfil",
    "espacio cultural alternativo medellín instagram",
    "colectivo teatro danza medellín instagram",
    "colectivo hip hop graffiti medellín instagram",
    "galería arte independiente medellín instagram",
    "colectivo audiovisual cine medellín instagram",
    "centro cultural comunitario medellín instagram",
    "colectivo música experimental medellín instagram",
]

# Seed: colectivos/espacios culturales medellín confirmados
_SEED_HANDLES = [
    "platohedro",
    "casakolacho",
    "festivaldepoesiamedellin",
    "circulocromatico",
    "teatroelparque",
    "corporacionculturalmedellin",
    "lacasita.mde",
    "elementosurbanos",
    "colectivomariposas",
    "accionimpro",
    "eltejarrafe",
    "festivaltibiribi",
    "redculturalmedellin",
    "circuitoculturalestacion",
    "corporacionescenarios",
    "colectivoaparte",
    "culturaencomun",
    "caminantemde",
    "festivaldesalmamde",
    "casamejia.art",
    "medellincultural",
    "comunacinco.mde",
    "casadeculturaflorida",
    "colectivomascara",
    "crecer.mde",
    "espaciodarte_mde",
    "laciudadela.cultural",
    "artesabiertos",
    "colectivopaisaje",
]

# Handles que no son colectivos (falsos positivos a filtrar)
_IGNORE_HANDLES = {
    "instagram", "explore", "p", "stories", "reel", "reels", "tv",
    "medellin", "colombia", "medellincity", "visitcolombia",
    "facebook", "twitter", "youtube", "tiktok", "whatsapp",
    "google", "play", "apps", "accounts", "help", "about",
    "legal", "privacy", "safety", "login", "signup",
}


def _extract_ig_handles(text: str) -> list[str]:
    handles: list[str] = []
    for pattern in [
        r'instagram\.com/([a-zA-Z0-9][a-zA-Z0-9_.]{2,29})(?:[/?"\s]|$)',
        r'@([a-zA-Z0-9][a-zA-Z0-9_.]{2,29})',
    ]:
        for h in re.findall(pattern, text):
            h_clean = h.lower().rstrip("/").split("?")[0].split("#")[0]
            if h_clean and h_clean not in _IGNORE_HANDLES and len(h_clean) >= 3:
                handles.append(h_clean)
    return list(dict.fromkeys(handles))


async def _ddg_search(query: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.post(_DDG_URL, data={"q": query, "b": ""}, headers=_HEADERS)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            text_content = soup.get_text(" ", strip=True)
            links = " ".join(a.get("href", "") for a in soup.find_all("a", href=True))
            return _extract_ig_handles(text_content + " " + links)[:20]
    except Exception as e:
        print(f"  [IG Discovery] Error DDG '{query[:40]}': {e}")
        return []


def _slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80]


def _get_existing_handles() -> set[str]:
    try:
        res = (
            supabase.table("lugares")
            .select("instagram_handle")
            .not_.is_("instagram_handle", "null")
            .execute()
        )
        return {
            row["instagram_handle"].lower().lstrip("@").strip()
            for row in (res.data or [])
            if row.get("instagram_handle")
        }
    except Exception as e:
        print(f"  [IG Discovery] Error leyendo handles existentes: {e}")
        return set()


def _register_lugar(handle: str) -> bool:
    """Inserta un nuevo lugar con instagram_handle para scraping posterior."""
    nombre = handle.replace(".", " ").replace("_", " ").title()
    slug = _slugify(handle)
    try:
        existing = supabase.table("lugares").select("id").eq("slug", slug).limit(1).execute()
        if existing.data:
            return False
        supabase.table("lugares").insert({
            "nombre": nombre,
            "slug": slug,
            "instagram_handle": f"@{handle}",
            "municipio": "medellin",
            "categoria_principal": "colectivo_cultural",
            "verificado": False,
            "activo": True,
        }).execute()
        return True
    except Exception as e:
        print(f"  [IG Discovery] Error registrando @{handle}: {e}")
        return False


async def discover_colectivos_instagram(
    run_web_search: bool = True,
    include_seeds: bool = True,
) -> dict:
    """
    Descubre colectivos culturales en Instagram y registra los nuevos como lugares.

    Returns: {nuevos, ya_registrados, total_encontrados}
    """
    print("\n📱 IG Colectivos Discovery — Medellín...")

    existing = _get_existing_handles()
    found: set[str] = set()

    if include_seeds:
        for h in _SEED_HANDLES:
            found.add(h.lower().lstrip("@"))

    if run_web_search:
        for query in _SEARCH_QUERIES:
            handles = await _ddg_search(query)
            found.update(h for h in handles if h not in _IGNORE_HANDLES)
            print(f"  [IG Discovery] '{query[:50]}' → {len(handles)} handles")

    nuevos = ya_registrados = 0
    for handle in sorted(found):
        if handle in existing:
            ya_registrados += 1
            continue
        if _register_lugar(handle):
            nuevos += 1
            print(f"  [IG Discovery] ✅ @{handle}")
        else:
            ya_registrados += 1

    print(
        f"  [IG Discovery] Listo — "
        f"nuevos={nuevos} ya_registrados={ya_registrados} total={len(found)}"
    )
    return {"nuevos": nuevos, "ya_registrados": ya_registrados, "total_encontrados": len(found)}
