"""
Endpoints para el sistema de auto-scraping, descubrimiento y social listener.
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from app.config import settings
from app.services.auto_scraper import run_auto_scraper, scrape_single_lugar, scrape_zona, enrich_event_images, scrape_agenda_sources, scrape_compas_urbano
from app.services.event_fallback_discovery import discover_events_for_filters

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
    """Scrape un lugar en vivo (acceso público, síncrono, timeout 90s).
    Intenta scraping directo; si no tiene web/IG, usa búsqueda con Claude.
    """
    try:
        result = await asyncio.wait_for(scrape_single_lugar(lugar_id), timeout=90.0)
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "message": "La búsqueda tardó demasiado. Puede que Instagram esté lento. Intenta de nuevo.",
            "lugar_id": lugar_id,
            "result": {},
        }

    nuevos = result.get("nuevos", 0)
    duplicados = result.get("duplicados", 0)
    nombre = result.get("lugar", "")

    if nuevos > 0:
        msg = f"¡Se encontraron {nuevos} evento(s) nuevos para {nombre}!"
    elif duplicados > 0:
        msg = f"La agenda de {nombre} ya está actualizada ({duplicados} evento(s) ya guardados)."
    elif result.get("error"):
        msg = f"No se encontró información: {result['error']}"
    else:
        msg = f"Se buscó en web e Instagram de {nombre} pero no se encontraron próximos eventos publicados."

    return {
        "status": "completed",
        "message": msg,
        "lugar_id": lugar_id,
        "result": result,
    }


@router.post("/zona/{municipio}/publico")
async def trigger_zona_scraper_publico(
    municipio: str,
    limit: int = Query(default=10, le=30, description="Máx lugares a scrapear en la zona"),
):
    """Scrape todos los espacios de un municipio/zona (acceso público, síncrono).
    Busca eventos en las redes y sitios web de los espacios de esa zona.
    """
    result = await scrape_zona(municipio, limit=limit)
    return {
        "status": "completed",
        "message": f"Búsqueda completada: {result.get('eventos_nuevos', 0)} eventos nuevos en {municipio}.",
        "result": result,
    }


@router.post("/discover-events/publico")
async def trigger_discover_events_publico(
    municipio: str | None = Query(default=None),
    categoria: str | None = Query(default=None),
    colectivo_slug: str | None = Query(default=None),
    texto: str | None = Query(default=None),
    max_queries: int = Query(default=2, ge=1, le=8),
    max_results_per_query: int = Query(default=3, ge=1, le=10),
):
    """Descubrimiento inteligente público cuando no hay resultados en filtros.

    Ejecuta scraping interno por lugar/zona y fallback web (Google) con extracción
    de eventos. Todo lo encontrado se normaliza y se guarda en la tabla eventos.
    """
    result = await discover_events_for_filters(
        municipio=municipio,
        categoria=categoria,
        colectivo_slug=colectivo_slug,
        texto=texto,
        max_queries=max_queries,
        max_results_per_query=max_results_per_query,
    )
    return {
        "status": "completed",
        "message": (
            f"Descubrimiento completado: {result.get('nuevos', 0)} nuevos, "
            f"{result.get('duplicados', 0)} duplicados."
        ),
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


@router.get("/status")
async def get_scraper_status():
    """Get Smart Listener health status: Meta token, scraping stats, priorities."""
    from app.database import supabase

    status = {"smart_listener": "active"}

    # Meta token health
    try:
        from app.services.meta_token_manager import check_token_health
        status["meta_token"] = await check_token_health()
    except Exception as e:
        status["meta_token"] = {"status": "error", "message": str(e)}

    # Scraping stats
    try:
        # Total eventos
        ev_resp = supabase.table("eventos").select("id", count="exact").execute()
        status["total_eventos"] = ev_resp.count

        # Eventos from Smart Listener (Vision)
        vision_resp = supabase.table("eventos").select("id", count="exact").like(
            "fuente", "%smart_listener%"
        ).execute()
        status["eventos_smart_listener"] = vision_resp.count

        # Total lugares
        lug_resp = supabase.table("lugares").select("id", count="exact").execute()
        status["total_lugares"] = lug_resp.count

        # Scraping state summary
        try:
            state_resp = supabase.table("scraping_state").select("*").execute()
            if state_resp.data:
                high = sum(1 for s in state_resp.data if (s.get("events_found") or 0) > 0)
                low = sum(1 for s in state_resp.data if (s.get("consecutive_empty") or 0) >= 5)
                status["scraping_priorities"] = {
                    "high": high,
                    "normal": len(state_resp.data) - high - low,
                    "low": low,
                }
        except Exception:
            pass

    except Exception as e:
        status["db_error"] = str(e)

    return status


@router.post("/agenda-alternativa", dependencies=[Depends(_verify_scraper_key)])
async def trigger_agenda_alternativa(background_tasks: BackgroundTasks):
    """Scrape fuentes de agenda alternativa e independiente."""
    background_tasks.add_task(scrape_agenda_sources)
    background_tasks.add_task(scrape_compas_urbano)
    return {"status": "started", "message": "Scraping de agenda alternativa + Compás Urbano iniciado"}


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
