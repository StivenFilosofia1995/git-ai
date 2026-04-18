# -*- coding: utf-8 -*-
"""
Social Listener — Monitoreo periódico de redes sociales para detectar
nuevos eventos culturales automáticamente.

Escucha hashtags de Instagram, perfiles de Facebook, y feeds de lugares
registrados. Usa Claude para extraer eventos de los posts encontrados
y crea tarjetas de eventos con flyers automáticamente.
"""
import json
import logging
import re
import traceback
from datetime import datetime, timedelta

import anthropic
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from .discovery.config import HASHTAGS_MEDELLIN, CATEGORIAS, MUNICIPIOS, MUNICIPIO_SLUG_MAP
from .discovery.utils import (
    fetch_url, clean_text, extract_og_image, polite_delay,
)
from .discovery.seed_data import get_all_local_profiles, get_high_priority_profiles

logger = logging.getLogger("social_listener")

_CLIENT = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# ── Prompt para extraer eventos de posts de redes sociales ───
SOCIAL_EVENT_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Analiza estos posts de redes sociales y extrae TODOS los EVENTOS culturales mencionados.

Fecha actual: {fecha_actual}

Posts encontrados:
---
{posts_content}
---

Para cada evento encontrado, extrae esta información en JSON:
[
  {{
    "titulo": "nombre del evento",
    "descripcion": "descripción completa del evento",
    "categoria_principal": "teatro | musica | literatura | filosofia | arte_general | hip_hop | jazz | electronica | galeria | danza | cine | fotografia | festival | otro",
    "categorias": ["lista de categorías aplicables"],
    "fecha_inicio": "YYYY-MM-DDTHH:MM:SS (si se puede determinar)",
    "fecha_fin": "YYYY-MM-DDTHH:MM:SS (opcional)",
    "municipio": "medellin | bello | itagui | envigado | sabaneta | caldas | la_estrella | copacabana | girardota | barbosa",
    "barrio": "barrio si se menciona",
    "nombre_lugar": "lugar donde se realiza",
    "precio": "precio o 'Entrada libre'",
    "es_gratuito": true/false,
    "es_recurrente": true/false,
    "imagen_url": "URL de la imagen del post/flyer si está disponible",
    "fuente_url": "URL del post original",
    "handle_organizador": "@handle del organizador",
    "nombre_organizador": "nombre del colectivo/espacio organizador"
  }}
]

Reglas:
- Solo incluye eventos FUTUROS (después de {fecha_actual}).
- Si un post es un flyer/afiche de evento, extrae toda la info visible.
- Si no hay eventos válidos, responde: []
- Responde SOLO con el JSON array, sin texto adicional.
"""


def _slugify(text: str) -> str:
    text = text.lower().strip()
    for old, new in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


def _normalize_municipio(raw: str) -> str:
    """Normaliza nombre de municipio a slug de la BD."""
    if not raw:
        return "medellin"
    return MUNICIPIO_SLUG_MAP.get(raw.lower().strip(), "medellin")


async def _fetch_meta_api_posts(handle: str) -> list[dict]:
    """Obtiene posts recientes vía Meta Graph API (si configurada)."""
    if not settings.meta_access_token or not settings.meta_ig_business_account_id:
        return []

    clean_handle = handle.lstrip("@")
    url = f"https://graph.facebook.com/v18.0/{settings.meta_ig_business_account_id}"
    params = {
        "fields": f"business_discovery.fields(username,name,biography,media.limit(20){{caption,timestamp,media_url,permalink,media_type}}).fields(username({clean_handle}))",
        "access_token": settings.meta_access_token,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            bd = data.get("business_discovery", {})
            media = bd.get("media", {}).get("data", [])
            posts = []
            for m in media:
                posts.append({
                    "caption": m.get("caption", ""),
                    "image_url": m.get("media_url", ""),
                    "permalink": m.get("permalink", ""),
                    "timestamp": m.get("timestamp", ""),
                    "handle": f"@{clean_handle}",
                })
            return posts
    except Exception as e:
        logger.warning(f"Meta API error for {handle}: {e}")
        return []


async def _fetch_ig_web_posts(handle: str) -> list[dict]:
    """Obtiene posts de un perfil IG vía web pública (fallback)."""
    clean_handle = handle.lstrip("@")
    posts = []

    # Intentar picuki
    for site in ["picuki.com", "imginn.com"]:
        url = f"https://www.{site}/profile/{clean_handle}"
        resp = await fetch_url(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Buscar posts con imágenes y captions
        for item in soup.select(".post-image, .item, .photo-item, article")[:15]:
            img = item.select_one("img")
            caption_el = item.select_one(".photo-description, .caption, .post-caption")
            link_el = item.select_one("a")

            image_url = ""
            if img:
                image_url = img.get("src") or img.get("data-src") or ""

            caption = ""
            if caption_el:
                caption = clean_text(caption_el.get_text(" "))

            permalink = ""
            if link_el and link_el.get("href"):
                permalink = link_el["href"]
                if not permalink.startswith("http"):
                    permalink = f"https://www.instagram.com/p/{permalink.strip('/')}"

            if caption or image_url:
                posts.append({
                    "caption": caption[:1000],
                    "image_url": image_url,
                    "permalink": permalink,
                    "handle": f"@{clean_handle}",
                })

        if posts:
            break
        await polite_delay()

    return posts


async def _fetch_hashtag_posts(tag: str) -> list[dict]:
    """Obtiene posts de un hashtag de Instagram."""
    posts = []
    for site in ["picuki.com", "imginn.com"]:
        url = f"https://www.{site}/tag/{tag}"
        resp = await fetch_url(url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".post-image, .item, .photo-item, article")[:20]:
            img = item.select_one("img")
            caption_el = item.select_one(".photo-description, .caption, .post-caption")
            link_el = item.select_one("a")
            user_el = item.select_one(".profile-name, .username, a[href*='/profile/']")

            image_url = img.get("src") or img.get("data-src") or "" if img else ""
            caption = clean_text(caption_el.get_text(" ")) if caption_el else ""
            permalink = ""
            if link_el and link_el.get("href"):
                permalink = link_el["href"]

            username = ""
            if user_el:
                username = clean_text(user_el.get_text()).lstrip("@")

            if caption or image_url:
                posts.append({
                    "caption": caption[:1000],
                    "image_url": image_url,
                    "permalink": permalink,
                    "handle": f"@{username}" if username else "",
                    "hashtag": tag,
                })

        if posts:
            break
        await polite_delay()

    return posts


async def _fetch_facebook_posts(page_url: str) -> list[dict]:
    """Obtiene posts de una página de Facebook vía web pública."""
    resp = await fetch_url(page_url)
    if not resp:
        return []

    posts = []
    soup = BeautifulSoup(resp.text, "lxml")

    # Extraer og:image como posible flyer
    og_img = extract_og_image(soup)
    og_desc = soup.find("meta", property="og:description")
    description = og_desc.get("content", "") if og_desc else ""

    if description:
        posts.append({
            "caption": clean_text(description)[:1000],
            "image_url": og_img or "",
            "permalink": page_url,
            "handle": "",
        })

    return posts


async def _extract_events_from_posts(posts: list[dict]) -> list[dict]:
    """Usa Claude para extraer eventos de posts de redes sociales."""
    if not posts:
        return []

    # Formatear posts para el prompt
    posts_text = ""
    for i, p in enumerate(posts, 1):
        posts_text += f"\n--- Post #{i} ---\n"
        if p.get("handle"):
            posts_text += f"De: {p['handle']}\n"
        if p.get("caption"):
            posts_text += f"Texto: {p['caption']}\n"
        if p.get("image_url"):
            posts_text += f"Imagen: {p['image_url']}\n"
        if p.get("permalink"):
            posts_text += f"Link: {p['permalink']}\n"

    prompt = SOCIAL_EVENT_PROMPT.format(
        fecha_actual=datetime.utcnow().strftime("%Y-%m-%d"),
        posts_content=posts_text[:6000],
    )

    def _call_claude():
        response = _CLIENT.messages.create(
            model=settings.anthropic_model,
            max_tokens=3000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        # Handle trailing commas
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        events = json.loads(raw)
        return events if isinstance(events, list) else []

    try:
        import asyncio
        return await asyncio.to_thread(_call_claude)
    except Exception as e:
        logger.error(f"Claude extraction error: {e}")
        return []


async def _insert_event(event: dict) -> bool:
    """Inserta un evento descubierto en la BD con deduplicación."""
    titulo = event.get("titulo")
    if not titulo:
        return False

    slug = _slugify(titulo)

    # Dedup: no insertar si ya existe con slug similar
    try:
        existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
        if existing.data:
            return False
    except Exception:
        pass

    # Buscar espacio asociado por handle
    espacio_id = None
    handle = event.get("handle_organizador", "").lstrip("@")
    if handle:
        try:
            esp = supabase.table("lugares").select("id").eq(
                "instagram_handle", f"@{handle}"
            ).execute()
            if esp.data:
                espacio_id = esp.data[0]["id"]
        except Exception:
            pass

    municipio = _normalize_municipio(event.get("municipio", "medellin"))
    now = datetime.utcnow()

    # Fecha
    fecha_inicio = now
    if event.get("fecha_inicio"):
        try:
            fecha_inicio = datetime.fromisoformat(event["fecha_inicio"])
            if fecha_inicio < now - timedelta(days=1):
                return False  # Evento pasado
        except (ValueError, TypeError):
            fecha_inicio = now

    evento_data = {
        "titulo": titulo,
        "slug": slug,
        "espacio_id": espacio_id,
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": event.get("fecha_fin"),
        "categorias": event.get("categorias", []),
        "categoria_principal": event.get("categoria_principal", "otro"),
        "municipio": municipio,
        "barrio": event.get("barrio"),
        "nombre_lugar": event.get("nombre_lugar"),
        "descripcion": event.get("descripcion"),
        "imagen_url": event.get("imagen_url"),
        "precio": event.get("precio"),
        "es_gratuito": event.get("es_gratuito", False),
        "es_recurrente": event.get("es_recurrente", False),
        "fuente": "social_listener",
        "fuente_url": event.get("fuente_url"),
        "verificado": False,
    }

    try:
        supabase.table("eventos").insert(evento_data).execute()
        logger.info(f"  🎭 Nuevo evento: {titulo}")
        return True
    except Exception as e:
        logger.error(f"  ⚠ Error insertando evento {titulo}: {e}")
        return False


async def _register_discovered_lugar(colectivo: dict) -> str | None:
    """Registra un colectivo descubierto como nuevo lugar en la BD."""
    handle = colectivo.get("handle", "").lstrip("@")
    if not handle:
        return None

    # Check si ya existe por handle
    try:
        existing = supabase.table("lugares").select("id").or_(
            f"instagram_handle.eq.@{handle},instagram_handle.eq.{handle}"
        ).execute()
        if existing.data:
            return existing.data[0]["id"]
    except Exception:
        pass

    nombre = colectivo.get("nombre", handle)
    slug = _slugify(nombre)

    # Check slug duplicado
    try:
        existing = supabase.table("lugares").select("id").eq("slug", slug).execute()
        if existing.data:
            slug = f"{slug}-{handle[:20]}"
    except Exception:
        pass

    municipio = _normalize_municipio(colectivo.get("municipio", "Medellín"))

    # Mapear categoría
    cat = colectivo.get("categoria", "arte_general")
    cat_map = {
        "teatro": "teatro", "musica": "musica_en_vivo",
        "literatura": "editorial", "filosofia": "otro",
        "arte_general": "centro_cultural",
        "cine": "otro", "fotografia": "otro",
        "danza": "otro",
    }
    tipo_map = {
        "teatro": "espacio_fisico", "musica": "colectivo",
        "literatura": "editorial", "filosofia": "colectivo",
        "arte_general": "colectivo",
        "cine": "colectivo", "fotografia": "colectivo",
        "danza": "colectivo",
    }

    # Determinar si es institucional basado en seguidores y fuente
    seguidores = colectivo.get("seguidores", 0)
    fuente = colectivo.get("fuente", "scraper")
    es_institucional = seguidores > 50000 or fuente == "semilla_verificada"

    lugar_data = {
        "nombre": nombre,
        "slug": slug,
        "tipo": tipo_map.get(cat, "colectivo"),
        "categorias": [cat],
        "categoria_principal": cat_map.get(cat, "otro"),
        "municipio": municipio,
        "descripcion_corta": colectivo.get("descripcion", "")[:300] or None,
        "instagram_handle": f"@{handle}",
        "sitio_web": colectivo.get("url") if colectivo.get("plataforma") == "web" else None,
        "facebook": colectivo.get("url") if colectivo.get("plataforma") == "facebook" else None,
        "telefono": colectivo.get("telefono") or None,
        "email": colectivo.get("email") or None,
        "es_underground": not es_institucional,
        "es_institucional": es_institucional,
        "fuente_datos": f"discovery:{fuente}",
        "nivel_actividad": "activo",
    }

    try:
        resp = supabase.table("lugares").insert(lugar_data).execute()
        if resp.data:
            logger.info(f"  📍 Nuevo lugar registrado: {nombre} (@{handle})")
            return resp.data[0]["id"]
    except Exception as e:
        logger.error(f"  ⚠ Error registrando lugar {nombre}: {e}")
    return None


# ═══════════════════════════════════════════════════════════════
# FUNCIONES PRINCIPALES DEL LISTENER
# ═══════════════════════════════════════════════════════════════

async def listen_instagram_hashtags(max_hashtags: int = 10) -> dict:
    """
    Monitorea hashtags de Instagram por nuevos eventos culturales.
    Descubre posts → Claude extrae eventos → inserta en BD con flyers.
    """
    logger.info("🔍 Social Listener: escuchando hashtags de Instagram...")
    stats = {"posts_analizados": 0, "eventos_nuevos": 0, "errores": 0}

    tags = HASHTAGS_MEDELLIN[:max_hashtags]
    all_posts = []

    for tag in tags:
        try:
            posts = await _fetch_hashtag_posts(tag)
            all_posts.extend(posts)
            logger.info(f"  #{tag}: {len(posts)} posts")
        except Exception as e:
            logger.warning(f"  #{tag}: error - {e}")
            stats["errores"] += 1
        await polite_delay()

    stats["posts_analizados"] = len(all_posts)

    if all_posts:
        # Procesar en lotes de 15 posts
        for i in range(0, len(all_posts), 15):
            batch = all_posts[i:i + 15]
            events = await _extract_events_from_posts(batch)
            for ev in events:
                if await _insert_event(ev):
                    stats["eventos_nuevos"] += 1

    logger.info(f"✅ Hashtags: {stats['posts_analizados']} posts → {stats['eventos_nuevos']} eventos nuevos")
    return stats


async def listen_registered_profiles() -> dict:
    """
    Monitorea los perfiles de Instagram/Facebook de lugares registrados.
    Busca nuevos posts y extrae eventos automáticamente.
    """
    logger.info("🔍 Social Listener: monitoreando perfiles registrados...")
    stats = {"perfiles": 0, "posts_analizados": 0, "eventos_nuevos": 0, "errores": 0}

    try:
        resp = supabase.table("lugares").select(
            "id, nombre, instagram_handle, facebook, sitio_web"
        ).eq("nivel_actividad", "activo").execute()
        lugares = resp.data or []
    except Exception as e:
        logger.error(f"Error cargando lugares: {e}")
        return stats

    for lugar in lugares:
        stats["perfiles"] += 1
        all_posts = []

        # Instagram
        ig_handle = lugar.get("instagram_handle")
        if ig_handle:
            try:
                # Primero intentar Meta API
                posts = await _fetch_meta_api_posts(ig_handle)
                if not posts:
                    posts = await _fetch_ig_web_posts(ig_handle)
                all_posts.extend(posts[:10])
            except Exception as e:
                logger.warning(f"  IG {ig_handle}: {e}")
                stats["errores"] += 1

        # Facebook
        fb_url = lugar.get("facebook")
        if fb_url:
            try:
                posts = await _fetch_facebook_posts(fb_url)
                all_posts.extend(posts[:5])
            except Exception as e:
                stats["errores"] += 1

        stats["posts_analizados"] += len(all_posts)

        if all_posts:
            events = await _extract_events_from_posts(all_posts)
            for ev in events:
                # Asociar al lugar
                ev["handle_organizador"] = ig_handle or ""
                if await _insert_event(ev):
                    stats["eventos_nuevos"] += 1

        await polite_delay()

    logger.info(
        f"✅ Perfiles: {stats['perfiles']} monitoreados, "
        f"{stats['posts_analizados']} posts → {stats['eventos_nuevos']} eventos nuevos"
    )
    return stats


async def _listen_seed_profiles() -> dict:
    """
    Monitorea perfiles de la red cultural verificada (seed_data)
    que NO están aún registrados como lugares en la BD.
    Esto asegura cobertura completa de la agenda cultural.
    """
    logger.info("🌱 Social Listener: monitoreando perfiles seed de alta/media prioridad...")
    stats = {"perfiles": 0, "posts_analizados": 0, "eventos_nuevos": 0, "errores": 0, "registrados": 0}

    # Obtener handles ya en BD
    try:
        resp = supabase.table("lugares").select("instagram_handle").not_.is_("instagram_handle", "null").execute()
        existing_handles = {
            r["instagram_handle"].lower().lstrip("@")
            for r in (resp.data or []) if r.get("instagram_handle")
        }
    except Exception:
        existing_handles = set()

    # Obtener perfiles seed de alta y media prioridad
    seed_profiles = get_all_local_profiles(min_priority="media")
    # Filtrar los que NO están en BD
    unregistered = [
        p for p in seed_profiles
        if p["handle"].lower().lstrip("@") not in existing_handles
    ]

    logger.info(f"  Seed: {len(seed_profiles)} locales, {len(unregistered)} no registrados en BD")

    # Primero registrarlos como lugares
    for p in unregistered:
        try:
            col = {
                "nombre": p.get("nombre", p["handle"].lstrip("@")),
                "handle": p["handle"],
                "plataforma": "instagram",
                "categoria": p.get("categoria", "arte_general"),
                "municipio": p.get("municipio", "Medellín"),
                "fuente": "semilla_verificada",
            }
            if await _register_discovered_lugar(col):
                stats["registrados"] += 1
        except Exception as e:
            logger.warning(f"  Error registrando {p['handle']}: {e}")

    # Ahora scrapear los de alta prioridad por eventos
    high_priority = [p for p in seed_profiles if p.get("prioridad") == "alta"]
    # Limitar a 30 por ciclo para no saturar
    high_priority = high_priority[:30]

    for p in high_priority:
        stats["perfiles"] += 1
        handle = p["handle"].lstrip("@")
        all_posts = []

        try:
            posts = await _fetch_meta_api_posts(handle)
            if not posts:
                posts = await _fetch_ig_web_posts(handle)
            all_posts.extend(posts[:8])
        except Exception as e:
            logger.warning(f"  Seed IG @{handle}: {e}")
            stats["errores"] += 1

        stats["posts_analizados"] += len(all_posts)

        if all_posts:
            events = await _extract_events_from_posts(all_posts)
            for ev in events:
                ev["handle_organizador"] = f"@{handle}"
                if await _insert_event(ev):
                    stats["eventos_nuevos"] += 1

        await polite_delay()

    logger.info(
        f"✅ Seed: {stats['registrados']} registrados, {stats['perfiles']} scrapeados, "
        f"{stats['posts_analizados']} posts → {stats['eventos_nuevos']} eventos nuevos"
    )
    return stats


async def run_social_listener() -> dict:
    """
    Ejecuta el ciclo completo del social listener.
    1. Escucha hashtags de Instagram
    2. Monitorea perfiles registrados en BD
    3. Monitorea perfiles seed de alta prioridad (red cultural verificada)
    """
    logger.info("═" * 50)
    logger.info("🎧 SOCIAL LISTENER — Inicio del ciclo")
    logger.info("═" * 50)

    start = datetime.utcnow()
    total_stats = {
        "hashtags": {},
        "perfiles": {},
        "seed_perfiles": {},
        "total_eventos_nuevos": 0,
        "duracion_segundos": 0,
    }

    try:
        # 1. Hashtags
        hashtag_stats = await listen_instagram_hashtags(max_hashtags=15)
        total_stats["hashtags"] = hashtag_stats
        total_stats["total_eventos_nuevos"] += hashtag_stats.get("eventos_nuevos", 0)

        # 2. Perfiles registrados en BD
        profile_stats = await listen_registered_profiles()
        total_stats["perfiles"] = profile_stats
        total_stats["total_eventos_nuevos"] += profile_stats.get("eventos_nuevos", 0)

        # 3. Perfiles seed de alta/media prioridad NO registrados en BD
        seed_stats = await _listen_seed_profiles()
        total_stats["seed_perfiles"] = seed_stats
        total_stats["total_eventos_nuevos"] += seed_stats.get("eventos_nuevos", 0)

    except Exception as e:
        logger.error(f"Social listener error: {e}\n{traceback.format_exc()}")

    duration = (datetime.utcnow() - start).total_seconds()
    total_stats["duracion_segundos"] = round(duration, 1)

    # Log
    try:
        supabase.table("scraping_log").insert({
            "fuente": "social_listener",
            "registros_nuevos": total_stats["total_eventos_nuevos"],
            "errores": (
                total_stats.get("hashtags", {}).get("errores", 0) +
                total_stats.get("perfiles", {}).get("errores", 0)
            ),
            "detalle": total_stats,
            "duracion_segundos": duration,
        }).execute()
    except Exception:
        pass

    logger.info(f"🎧 Social Listener completado en {duration:.0f}s — {total_stats['total_eventos_nuevos']} eventos nuevos")
    return total_stats
