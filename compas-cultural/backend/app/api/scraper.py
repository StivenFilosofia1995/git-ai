"""
Endpoints para el sistema de auto-scraping, descubrimiento y social listener.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from app.config import settings
from app.services.auto_scraper import run_auto_scraper, scrape_single_lugar, enrich_event_images, scrape_agenda_sources

router = APIRouter(prefix="/scraper", tags=["scraper"])


def _verify_scraper_key(x_scraper_key: str = Header(..., alias="X-Scraper-Key")):
    """Verify the scraper API key from request header."""
    if x_scraper_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="Invalid scraper API key")


# ═══════════════════════════════════════════════════════════════
# AUTO-SCRAPER (existente)
# ═══════════════════════════════════════════════════════════════

@router.post("/run", dependencies=[Depends(_verify_scraper_key)])
async def trigger_full_scraper(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=None, description="Máximo de lugares a scrapear"),
):
    """Trigger manual del auto-scraper completo (se ejecuta en background)."""
    background_tasks.add_task(run_auto_scraper, limit=limit)
    return {
        "status": "started",
        "message": f"Auto-scraper iniciado en background{f' (limit={limit})' if limit else ''}",
    }


@router.post("/lugar/{lugar_id}", dependencies=[Depends(_verify_scraper_key)])
async def trigger_lugar_scraper(lugar_id: str):
    """Scrape un lugar específico (síncrono, retorna resultados)."""
    result = await scrape_single_lugar(lugar_id)
    return result


@router.post("/lugar/{lugar_id}/publico")
async def trigger_lugar_scraper_publico(lugar_id: str):
    """Scrape un lugar en vivo (acceso público, síncrono).
    Intenta scraping directo; si no tiene web/IG, usa búsqueda con Claude.
    """
    result = await scrape_single_lugar(lugar_id)
    return {
        "status": "completed",
        "message": f"Búsqueda completada: {result.get('nuevos', 0)} eventos encontrados.",
        "lugar_id": lugar_id,
        "result": result,
    }


@router.get("/log")
async def get_scraping_log(
    limit: int = Query(default=50, le=200),
):
    """Obtener log de scraping reciente."""
    from app.database import supabase
    resp = (
        supabase.table("scraping_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"logs": resp.data, "total": len(resp.data)}


@router.post("/enrich-images", dependencies=[Depends(_verify_scraper_key)])
async def trigger_enrich_images(background_tasks: BackgroundTasks):
    """Buscar og:image en fuentes y actualizar eventos sin imagen."""
    background_tasks.add_task(enrich_event_images)
    return {"status": "started", "message": "Enriquecimiento de imágenes iniciado"}


@router.post("/agenda-alternativa", dependencies=[Depends(_verify_scraper_key)])
async def trigger_agenda_alternativa(background_tasks: BackgroundTasks):
    """Scrape fuentes de agenda alternativa e independiente."""
    background_tasks.add_task(scrape_agenda_sources)
    return {"status": "started", "message": "Scraping de agenda alternativa iniciado"}


# ═══════════════════════════════════════════════════════════════
# DISCOVERY — Descubrimiento de nuevos colectivos
# ═══════════════════════════════════════════════════════════════

@router.post("/discovery/run", dependencies=[Depends(_verify_scraper_key)])
async def trigger_discovery(
    background_tasks: BackgroundTasks,
    mode: str = Query(default="rapido", description="Modo: seed | rapido | completo"),
):
    """
    Ejecuta el descubrimiento de nuevos colectivos culturales.
    - seed: Solo importar colectivos conocidos
    - rapido: Semilla + Instagram hashtags (5-10 min)
    - completo: Todo — Google + IG + FB + Directorios (30-60 min)
    """
    from app.services.discovery_service import run_discovery
    if mode not in ("seed", "rapido", "completo"):
        raise HTTPException(status_code=400, detail="Modo inválido. Usa: seed, rapido o completo")
    background_tasks.add_task(run_discovery, mode=mode)
    return {
        "status": "started",
        "message": f"Discovery iniciado en modo '{mode}'",
    }


@router.post("/discovery/full", dependencies=[Depends(_verify_scraper_key)])
async def trigger_discovery_and_scrape(
    background_tasks: BackgroundTasks,
    mode: str = Query(default="rapido"),
):
    """
    Descubrimiento + auto-scraping combinado.
    Descubre colectivos nuevos y luego les extrae eventos con Claude.
    """
    from app.services.discovery_service import run_discovery_and_scrape
    background_tasks.add_task(run_discovery_and_scrape, mode=mode)
    return {
        "status": "started",
        "message": f"Discovery + auto-scraper iniciado en modo '{mode}'",
    }


# ═══════════════════════════════════════════════════════════════
# SOCIAL LISTENER — Monitoreo de redes sociales
# ═══════════════════════════════════════════════════════════════

@router.post("/listener/run", dependencies=[Depends(_verify_scraper_key)])
async def trigger_social_listener(background_tasks: BackgroundTasks):
    """
    Ejecuta el Social Listener: monitorea hashtags y perfiles de
    Instagram/Facebook para detectar nuevos eventos con flyers.
    """
    from app.services.social_listener import run_social_listener
    background_tasks.add_task(run_social_listener)
    return {
        "status": "started",
        "message": "Social Listener iniciado — monitoreando redes sociales",
    }


@router.post("/listener/hashtags", dependencies=[Depends(_verify_scraper_key)])
async def trigger_hashtag_listener(
    background_tasks: BackgroundTasks,
    max_hashtags: int = Query(default=10, le=29),
):
    """Escucha solo hashtags de Instagram por nuevos eventos."""
    from app.services.social_listener import listen_instagram_hashtags
    background_tasks.add_task(listen_instagram_hashtags, max_hashtags=max_hashtags)
    return {
        "status": "started",
        "message": f"Escuchando {max_hashtags} hashtags de Instagram",
    }


@router.post("/listener/profiles", dependencies=[Depends(_verify_scraper_key)])
async def trigger_profile_listener(background_tasks: BackgroundTasks):
    """Monitorea perfiles de IG/FB de todos los lugares registrados."""
    from app.services.social_listener import listen_registered_profiles
    background_tasks.add_task(listen_registered_profiles)
    return {
        "status": "started",
        "message": "Monitoreando perfiles de lugares registrados",
    }


# ═══════════════════════════════════════════════════════════════
# STATUS — Estado del sistema de scraping
# ═══════════════════════════════════════════════════════════════

@router.get("/status")
async def get_scraper_status():
    """Estado general del sistema de scraping, discovery y listener."""
    from app.database import supabase

    # Últimos logs por fuente
    resp = (
        supabase.table("scraping_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    logs = resp.data or []

    # Contadores
    total_lugares = supabase.table("lugares").select("id", count="exact").execute()
    total_eventos = supabase.table("eventos").select("id", count="exact").execute()
    eventos_con_imagen = supabase.table("eventos").select("id", count="exact").not_.is_("imagen_url", "null").execute()

    # Últimas ejecuciones por tipo
    last_by_type = {}
    for log in logs:
        fuente = log.get("fuente", "")
        if fuente not in last_by_type:
            last_by_type[fuente] = {
                "ultima_ejecucion": log.get("created_at"),
                "registros_nuevos": log.get("registros_nuevos", 0),
                "errores": log.get("errores", 0),
                "duracion": log.get("duracion_segundos"),
            }

    return {
        "total_lugares": total_lugares.count if total_lugares.count else 0,
        "total_eventos": total_eventos.count if total_eventos.count else 0,
        "eventos_con_imagen": eventos_con_imagen.count if eventos_con_imagen.count else 0,
        "ultimas_ejecuciones": last_by_type,
        "logs_recientes": logs[:10],
    }


@router.get("/red-cultural")
async def get_cultural_network_stats():
    """
    Estadísticas de la red cultural completa:
    perfiles verificados, categorías, cobertura por municipio.
    """
    from app.services.discovery.seed_data import (
        get_total_count, get_all_local_profiles, get_high_priority_profiles,
    )
    stats = get_total_count()
    high_priority = get_high_priority_profiles()
    all_local = get_all_local_profiles(min_priority="baja")

    # Agrupar por municipio
    by_municipio = {}
    for p in all_local:
        mun = p.get("municipio", "Sin definir")
        by_municipio[mun] = by_municipio.get(mun, 0) + 1

    # Agrupar por categoría
    by_cat = {}
    for p in all_local:
        cat = p.get("categoria", "otro")
        by_cat[cat] = by_cat.get(cat, 0) + 1

    return {
        "red_cultural": stats,
        "perfiles_locales": len(all_local),
        "perfiles_alta_prioridad": len(high_priority),
        "por_municipio": by_municipio,
        "por_categoria": by_cat,
    }
