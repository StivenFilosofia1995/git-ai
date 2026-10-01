"""Instagram con la sesión del usuario: perfiles de colectivos/espacios y feed propio.

No parsea el DOM (cambia cada semana): escucha las respuestas JSON que la propia
página de Instagram pide al cargar (web_profile_info, feed, graphql) y las
normaliza con los parsers que ya existen en app/services.
"""
from __future__ import annotations

import json
from typing import Optional

from app.services.ig_feed_scraper import _normalize_item
from app.services.instagram_pw_scraper import _parse_api_response

from runner.browser import pausa, verificar_sesion

_URLS_JSON = ("web_profile_info", "/api/v1/feed/", "graphql/query", "/api/graphql")


def _items_de_json(data) -> list[dict]:
    """Encuentra listas de posts (items / edges) en cualquier respuesta JSON de IG."""
    out: list[dict] = []

    def walk(o, depth=0):
        if depth > 8:
            return
        if isinstance(o, dict):
            if ("caption" in o or "edge_media_to_caption" in o) and ("code" in o or "shortcode" in o):
                n = _normalize_item(o)
                if n:
                    out.append(n)
                return
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, depth + 1)

    walk(data)
    return out


async def _escuchar(page) -> list:
    capturas: list = []

    async def on_response(resp):
        if not any(k in resp.url for k in _URLS_JSON):
            return
        try:
            capturas.append(await resp.json())
        except Exception:
            pass

    page.on("response", on_response)
    return capturas


def _perfil_desde_capturas(capturas: list) -> Optional[dict]:
    perfil = {"captions": [], "image_urls": [], "permalink_urls": [], "timestamps": [], "biography": ""}
    vistos: set[str] = set()
    for data in capturas:
        p = _parse_api_response(data) if isinstance(data, dict) else None
        if p:
            perfil["biography"] = perfil["biography"] or p.get("biography", "")
            for cap, img, link, ts in zip(p["captions"], p["image_urls"], p["permalink_urls"], p["timestamps"]):
                if link and link not in vistos:
                    vistos.add(link)
                    perfil["captions"].append(cap); perfil["image_urls"].append(img)
                    perfil["permalink_urls"].append(link); perfil["timestamps"].append(ts)
        for it in _items_de_json(data):
            if it["permalink"] and it["permalink"] not in vistos and it["caption"]:
                vistos.add(it["permalink"])
                perfil["captions"].append(it["caption"]); perfil["image_urls"].append(it["image_url"])
                perfil["permalink_urls"].append(it["permalink"]); perfil["timestamps"].append(it["taken_at"])
    return perfil if perfil["captions"] else None


async def leer_perfil(ctx, handle: str) -> Optional[dict]:
    """Abre instagram.com/<handle>/ y devuelve {captions, image_urls, permalink_urls, timestamps}."""
    page = await ctx.new_page()
    try:
        capturas = await _escuchar(page)
        await page.goto(f"https://www.instagram.com/{handle.strip('@')}/", wait_until="domcontentloaded", timeout=45_000)
        verificar_sesion(page.url, "ig")
        await pausa(3, 6)
        for _ in range(2):  # dos scrolls: ~24 posts recientes
            await page.mouse.wheel(0, 2200)
            await pausa(2, 4)
        verificar_sesion(page.url, "ig")
        return _perfil_desde_capturas(capturas)
    finally:
        await page.close()


async def leer_feed(ctx, max_posts: int = 60) -> list[dict]:
    """Recorre el feed propio. Devuelve posts normalizados (caption, username, imagen, permalink…)."""
    page = await ctx.new_page()
    try:
        capturas = await _escuchar(page)
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=45_000)
        verificar_sesion(page.url, "ig")
        await pausa(4, 7)
        posts: dict[str, dict] = {}
        for _ in range(12):
            for data in list(capturas):
                for it in _items_de_json(data):
                    if it["permalink"]:
                        posts.setdefault(it["permalink"], it)
            if len(posts) >= max_posts:
                break
            await page.mouse.wheel(0, 2600)
            await pausa(2.5, 5)
            verificar_sesion(page.url, "ig")
        return list(posts.values())[:max_posts]
    finally:
        await page.close()


def guardar_muestra(capturas: list, ruta: str) -> None:
    """Para depurar: vuelca las respuestas capturadas a un archivo local."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(capturas, f, ensure_ascii=False)
