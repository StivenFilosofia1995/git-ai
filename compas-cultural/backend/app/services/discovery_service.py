# -*- coding: utf-8 -*-
"""
Discovery Service — Orquestador principal del descubrimiento de colectivos.
Coordina Google, Instagram, Facebook y directorios para encontrar
nuevos colectivos/espacios culturales y registrarlos automáticamente.
"""
import logging
import traceback
from datetime import datetime

from app.database import supabase
from .discovery.config import MUNICIPIO_SLUG_MAP
from .discovery.google_scraper import scrape_google
from .discovery.instagram_scraper import scrape_instagram
from .discovery.facebook_scraper import scrape_facebook
from .discovery.directory_scraper import scrape_directorios
from .discovery.seed_data import SEMILLA, get_semilla_as_colectivos, get_total_count
from .social_listener import _register_discovered_lugar

logger = logging.getLogger("discovery_service")


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    for old, new in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


def _normalize_municipio(raw: str) -> str:
    if not raw:
        return "medellin"
    return MUNICIPIO_SLUG_MAP.get(raw.lower().strip(), "medellin")


async def _get_existing_handles() -> set:
    """Obtiene todos los handles de Instagram ya registrados en la BD."""
    try:
        resp = supabase.table("lugares").select("instagram_handle").not_.is_("instagram_handle", "null").execute()
        return {r["instagram_handle"].lower().lstrip("@") for r in (resp.data or []) if r.get("instagram_handle")}
    except Exception:
        return set()


async def _register_colectivo(col: dict, existing_handles: set) -> bool:
    """Registra un colectivo descubierto como lugar si no existe."""
    handle = col.get("handle", "").lstrip("@").lower()
    if not handle or handle in existing_handles:
        return False

    result = await _register_discovered_lugar(col)
    if result:
        existing_handles.add(handle)
        return True
    return False


async def run_discovery(
    mode: str = "rapido",
    max_google: int = 30,
    max_ig_hashtags: int = 10,
    max_fb: int = 20,
) -> dict:
    """
    Ejecuta descubrimiento de nuevos colectivos culturales.

    Modos:
    - rapido: Solo seed + IG hashtags (5-10 min)
    - completo: Todo (Google + IG + FB + Directorios) (30-60 min)
    - seed: Solo importar semilla de colectivos conocidos
    """
    logger.info("═" * 50)
    logger.info(f"🔭 DISCOVERY SERVICE — modo: {mode}")
    logger.info("═" * 50)

    start = datetime.utcnow()
    stats = {
        "modo": mode,
        "descubiertos": 0,
        "registrados": 0,
        "duplicados": 0,
        "errores": 0,
        "por_fuente": {},
        "duracion_segundos": 0,
    }

    existing = await _get_existing_handles()
    logger.info(f"  Handles existentes en BD: {len(existing)}")
    all_colectivos = []

    try:
        # ── 1. Semilla COMPLETA (siempre) ────────────────────
        logger.info("\n📌 Fase 1: Importando RED CULTURAL COMPLETA (semilla verificada)...")
        all_seed = get_semilla_as_colectivos()
        seed_stats = get_total_count()
        logger.info(f"  Red cultural: {seed_stats.get('total_perfiles', 0)} perfiles totales, "
                     f"{seed_stats.get('total_locales', 0)} locales")
        seed_registered = 0
        for col in all_seed:
            if await _register_colectivo(col, existing):
                seed_registered += 1
        stats["por_fuente"]["semilla"] = {
            "encontrados": len(all_seed), "registrados": seed_registered,
            "detalle": seed_stats,
        }
        logger.info(f"  Semilla: {seed_registered} nuevos de {len(all_seed)}")

        if mode == "seed":
            stats["registrados"] = seed_registered
            return stats

        # ── 2. Instagram hashtags ────────────────────────────
        logger.info("\n📷 Fase 2: Scraping Instagram hashtags...")
        try:
            ig_colectivos = await scrape_instagram(max_hashtags=max_ig_hashtags)
            ig_registered = 0
            for col in ig_colectivos:
                if await _register_colectivo(col, existing):
                    ig_registered += 1
            all_colectivos.extend(ig_colectivos)
            stats["por_fuente"]["instagram"] = {
                "encontrados": len(ig_colectivos), "registrados": ig_registered,
            }
            logger.info(f"  Instagram: {ig_registered} nuevos de {len(ig_colectivos)}")
        except Exception as e:
            logger.error(f"  Instagram error: {e}")
            stats["errores"] += 1

        if mode == "rapido":
            stats["descubiertos"] = len(all_colectivos) + len(SEMILLA)
            stats["registrados"] = sum(s.get("registrados", 0) for s in stats["por_fuente"].values())
            return stats

        # ── 3. Google (modo completo) ────────────────────────
        logger.info("\n🔍 Fase 3: Scraping Google...")
        try:
            google_colectivos = await scrape_google(max_queries=max_google)
            g_registered = 0
            for col in google_colectivos:
                if await _register_colectivo(col, existing):
                    g_registered += 1
            all_colectivos.extend(google_colectivos)
            stats["por_fuente"]["google"] = {
                "encontrados": len(google_colectivos), "registrados": g_registered,
            }
            logger.info(f"  Google: {g_registered} nuevos de {len(google_colectivos)}")
        except Exception as e:
            logger.error(f"  Google error: {e}")
            stats["errores"] += 1

        # ── 4. Facebook (modo completo) ──────────────────────
        logger.info("\n📘 Fase 4: Scraping Facebook...")
        try:
            fb_colectivos = await scrape_facebook(max_queries=max_fb)
            fb_registered = 0
            for col in fb_colectivos:
                if await _register_colectivo(col, existing):
                    fb_registered += 1
            all_colectivos.extend(fb_colectivos)
            stats["por_fuente"]["facebook"] = {
                "encontrados": len(fb_colectivos), "registrados": fb_registered,
            }
            logger.info(f"  Facebook: {fb_registered} nuevos de {len(fb_colectivos)}")
        except Exception as e:
            logger.error(f"  Facebook error: {e}")
            stats["errores"] += 1

        # ── 5. Directorios (modo completo) ───────────────────
        logger.info("\n📚 Fase 5: Scraping directorios culturales...")
        try:
            dir_colectivos = await scrape_directorios()
            d_registered = 0
            for col in dir_colectivos:
                if await _register_colectivo(col, existing):
                    d_registered += 1
            all_colectivos.extend(dir_colectivos)
            stats["por_fuente"]["directorios"] = {
                "encontrados": len(dir_colectivos), "registrados": d_registered,
            }
            logger.info(f"  Directorios: {d_registered} nuevos de {len(dir_colectivos)}")
        except Exception as e:
            logger.error(f"  Directorios error: {e}")
            stats["errores"] += 1

    except Exception as e:
        logger.error(f"Discovery error: {e}\n{traceback.format_exc()}")
        stats["errores"] += 1

    duration = (datetime.utcnow() - start).total_seconds()
    stats["duracion_segundos"] = round(duration, 1)
    stats["descubiertos"] = len(all_colectivos) + len(SEMILLA)
    stats["registrados"] = sum(s.get("registrados", 0) for s in stats["por_fuente"].values())
    stats["duplicados"] = stats["descubiertos"] - stats["registrados"]

    # Log
    try:
        supabase.table("scraping_log").insert({
            "fuente": f"discovery:{mode}",
            "registros_nuevos": stats["registrados"],
            "errores": stats["errores"],
            "detalle": stats,
            "duracion_segundos": duration,
        }).execute()
    except Exception:
        pass

    logger.info(f"\n🔭 Discovery completado en {duration:.0f}s")
    logger.info(f"   Descubiertos: {stats['descubiertos']} | Registrados: {stats['registrados']} | Duplicados: {stats['duplicados']}")
    return stats


async def run_discovery_and_scrape(mode: str = "rapido") -> dict:
    """
    Ejecuta descubrimiento + auto-scraping de los lugares nuevos.
    1. Descubre colectivos nuevos
    2. Ejecuta auto-scraper para extraer eventos de los recién registrados
    """
    discovery_stats = await run_discovery(mode=mode)

    # Si se registraron nuevos, ejecutar auto-scraper para extraer eventos
    if discovery_stats.get("registrados", 0) > 0:
        logger.info(f"\n🔄 Ejecutando auto-scraper para {discovery_stats['registrados']} nuevos lugares...")
        try:
            from .auto_scraper import run_auto_scraper
            scraper_stats = await run_auto_scraper()
            discovery_stats["auto_scraper"] = scraper_stats
        except Exception as e:
            logger.error(f"Auto-scraper post-discovery error: {e}")

    return discovery_stats
