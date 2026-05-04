"""
Endpoints para el sistema de auto-scraping, descubrimiento y social listener.
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from app.config import settings

router = APIRouter(prefix="/scraper", tags=["scraper"])


def _get_auto_scraper_services():
    """Lazy import heavy scraping services so router can load even if optional deps fail."""
    try:
        from app.services.auto_scraper import (
            run_auto_scraper,
            scrape_single_lugar,
            scrape_zona,
            repair_suspicious_event_dates,
            enrich_event_images,
            scrape_agenda_sources,
            scrape_compas_urbano,
        )
        return {
            "run_auto_scraper": run_auto_scraper,
            "scrape_single_lugar": scrape_single_lugar,
            "scrape_zona": scrape_zona,
            "repair_suspicious_event_dates": repair_suspicious_event_dates,
            "enrich_event_images": enrich_event_images,
            "scrape_agenda_sources": scrape_agenda_sources,
            "scrape_compas_urbano": scrape_compas_urbano,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Servicio de scraping no disponible: {e}",
        )


def _get_discovery_services():
    """Lazy import discovery services so /scraper routes stay mounted in production."""
    try:
        from app.services.event_fallback_discovery import (
            discover_events_for_filters,
            commit_discovered_events,
        )
        return {
            "discover_events_for_filters": discover_events_for_filters,
            "commit_discovered_events": commit_discovered_events,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Servicio de discovery no disponible: {e}",
        )


def _verify_scraper_key(x_scraper_key: str = Header(..., alias="X-Scraper-Key")):
    """Verify the scraper API key from request header."""
    if x_scraper_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="Invalid scraper API key")


@router.post("/run", dependencies=[Depends(_verify_scraper_key)])
async def trigger_full_scraper(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=None, description="Máximo de lugares a scrapear"),
):
    """Trigger manual del auto-scraper completo (se ejecuta en background)."""
    svc = _get_auto_scraper_services()
    background_tasks.add_task(svc["run_auto_scraper"], limit=limit)
    return {
        "status": "started",
        "message": f"Auto-scraper iniciado en background{f' (limit={limit})' if limit else ''}",
    }


@router.post("/run-now", dependencies=[Depends(_verify_scraper_key)])
async def trigger_scrape_now(background_tasks: BackgroundTasks):
    """Limpia eventos pasados y corre scraper + agenda alternativa inmediatamente."""
    svc = _get_auto_scraper_services()

    async def _cleanup_and_scrape():
        try:
            await svc["run_auto_scraper"]()
        except Exception as e:
            print(f"❌ run-now scraper error: {e}")
        try:
            await svc["scrape_agenda_sources"]()
        except Exception as e:
            print(f"❌ run-now agenda sources error: {e}")

    background_tasks.add_task(_cleanup_and_scrape)
    return {"status": "started", "message": "Limpieza + scrape completo iniciado en background"}


@router.post("/lugar/{lugar_id}", dependencies=[Depends(_verify_scraper_key)])
async def trigger_lugar_scraper(lugar_id: str):
    """Scrape un lugar específico (síncrono, retorna resultados)."""
    svc = _get_auto_scraper_services()
    result = await svc["scrape_single_lugar"](lugar_id)
    return result


@router.post("/lugar/{lugar_id}/publico")
async def trigger_lugar_scraper_publico(lugar_id: str):
    """Scrape un lugar en vivo (acceso público, síncrono, timeout 90s).
    Intenta scraping directo; si no tiene web/IG, usa búsqueda con Claude.
    """
    try:
        svc = _get_auto_scraper_services()
        result = await asyncio.wait_for(svc["scrape_single_lugar"](lugar_id), timeout=90.0)
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
    limit: int = Query(default=40, ge=5, le=120, description="Máx lugares a scrapear en la zona"),
):
    """Scrape todos los espacios de un municipio/zona (acceso público, síncrono).
    Busca eventos en las redes y sitios web de los espacios de esa zona.
    """
    svc = _get_auto_scraper_services()
    result = await svc["scrape_zona"](municipio, limit=limit)
    return {
        "status": "completed",
        "message": f"Búsqueda completada: {result.get('eventos_nuevos', 0)} eventos nuevos en {municipio}.",
        "result": result,
    }


@router.post("/repair-fechas", dependencies=[Depends(_verify_scraper_key)])
async def trigger_repair_fechas_scraper(
    limit_eventos: int = Query(default=160, ge=20, le=500, description="Eventos próximos a inspeccionar"),
    max_lugares: int = Query(default=50, ge=1, le=120, description="Máximo de lugares a re-scrapear"),
    municipio: str | None = Query(default=None, description="Filtrar reparación por municipio"),
):
    """Re-scrapea lugares con eventos sospechosos de fecha/hora para corregir agenda.

    Útil después de fixes de parsing para recalcular eventos legacy.
    """
    svc = _get_auto_scraper_services()
    result = await svc["repair_suspicious_event_dates"](
        limit_eventos=limit_eventos,
        max_lugares=max_lugares,
        municipio=municipio,
    )

    return {
        "status": "completed",
        "message": (
            "Repair scraper completado: "
            f"{result.get('lugares_reprocesados', 0)} lugar(es) re-scrapeados, "
            f"{result.get('nuevos', 0)} evento(s) nuevos, "
            f"{result.get('corregidos_hora', 0)} hora(s) corregida(s)."
        ),
        "result": result,
    }


@router.post("/discover-events/publico")
async def trigger_discover_events_publico(
    municipio: str | None = Query(default=None),
    categoria: str | None = Query(default=None),
    es_gratuito: bool | None = Query(default=None),
    colectivo_slug: str | None = Query(default=None),
    texto: str | None = Query(default=None),
    barrio: str | None = Query(default=None),
    max_queries: int = Query(default=2, ge=1, le=8),
    max_results_per_query: int = Query(default=3, ge=1, le=10),
    days_from: int = Query(default=0, ge=0, le=120),
    days_ahead: int | None = Query(default=None, ge=0, le=120),
    strict_categoria: bool = Query(default=False),
    auto_insert: bool = Query(default=True, description="Si true, inserta automáticamente en BD"),
):
    """Descubrimiento inteligente público cuando no hay resultados en filtros.

    Ejecuta búsqueda web (Google) guiada por filtros y devuelve candidatos.
    El frontend puede pedir confirmación del usuario para agregar los eventos.
    """
    discovery = _get_discovery_services()
    result = await discovery["discover_events_for_filters"](
        municipio=municipio,
        categoria=categoria,
        es_gratuito=es_gratuito,
        colectivo_slug=colectivo_slug,
        texto=texto,
        barrio=barrio,
        max_queries=max_queries,
        max_results_per_query=max_results_per_query,
        days_from=days_from,
        days_ahead=days_ahead,
        strict_categoria=strict_categoria,
        auto_insert=auto_insert,
    )

    # Rescue mode: when strict/short filters return nothing, retry across categories
    # and a wider date window to avoid empty UX in agenda exploration.
    first_found = len(result.get("candidatos") or [])
    first_new = int(result.get("nuevos") or 0)
    if first_found == 0 and first_new == 0:
        sweep_categories = [categoria] if categoria else [
            "teatro",
            "musica_en_vivo",
            "cine",
            "danza",
            "festival",
            "galeria",
            "libreria",
            "conferencia",
        ]
        widened_days = max(days_ahead or 0, 14)

        merged = {
            **result,
            "nuevos": 0,
            "duplicados": 0,
            "errores": 0,
            "encontrados": 0,
            "consultas": [],
            "urls_analizadas": 0,
            "candidatos": [],
            "variables": {
                **(result.get("variables") or {}),
                "rescue_mode": "category_sweep",
                "rescue_days_ahead": str(widened_days),
            },
        }

        seen_keys: set[str] = set()
        for cat in sweep_categories:
            retry = await discovery["discover_events_for_filters"](
                municipio=municipio,
                categoria=cat,
                es_gratuito=es_gratuito,
                colectivo_slug=colectivo_slug,
                texto=texto,
                max_queries=max(max_queries, 4),
                max_results_per_query=max(max_results_per_query, 6),
                days_from=days_from,
                days_ahead=widened_days,
                strict_categoria=False,
                auto_insert=auto_insert,
            )
            merged["nuevos"] += int(retry.get("nuevos") or 0)
            merged["duplicados"] += int(retry.get("duplicados") or 0)
            merged["errores"] += int(retry.get("errores") or 0)
            merged["urls_analizadas"] += int(retry.get("urls_analizadas") or 0)
            merged["consultas"].extend(retry.get("consultas") or [])

            for ev in (retry.get("candidatos") or []):
                key = ev.get("slug") or f"{(ev.get('titulo') or '').strip().lower()}::{str(ev.get('fecha_inicio') or '')[:10]}"
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                if len(merged["candidatos"]) < 80:
                    merged["candidatos"].append(ev)

        merged["consultas"] = list(dict.fromkeys(merged["consultas"]))[:120]
        merged["encontrados"] = len(merged["candidatos"])
        result = merged

    candidatos_n = len(result.get("candidatos") or [])
    if auto_insert:
        nuevos = result.get("nuevos", 0)
        duplicados = result.get("duplicados", 0)
        errores = result.get("errores", 0)
        candidatos_n = len(result.get("candidatos") or [])
        if nuevos > 0:
            message = (
                f"Descubrimiento completado: {nuevos} evento(s) nuevos agregados a la BD "
                f"y {duplicados} duplicado(s) omitidos."
            )
            if errores:
                message += f" Hubo {errores} candidato(s) con error al insertar."
        else:
            if errores > 0 and candidatos_n > 0:
                message = (
                    f"Búsqueda web completada: se encontraron {candidatos_n} candidato(s), "
                    f"pero no se pudieron insertar ({errores} error(es)); {duplicados} ya existían."
                )
            else:
                message = (
                    "Búsqueda web completada: no hubo eventos nuevos para insertar, "
                    f"{duplicados} ya existían en la BD."
                )
    elif candidatos_n > 0:
        message = (
            f"Se encontraron {candidatos_n} eventos candidatos para el Valle. "
            "¿Deseas agregarlos al sistema para otros habitantes?"
        )
    else:
        message = (
            "No se encontraron eventos nuevos con esos filtros. "
            "Intenta cambiar municipio, categoría o texto."
        )

    return {
        "status": "completed",
        "message": message,
        "result": result,
    }


@router.post("/discover-events/publico/commit")
async def commit_discover_events_publico(body: dict):
    """Confirma y agrega al sistema los eventos descubiertos por usuarios."""
    candidatos = body.get("candidatos") or []
    if not isinstance(candidatos, list) or not candidatos:
        raise HTTPException(status_code=400, detail="Debes enviar una lista de candidatos")

    discovery = _get_discovery_services()
    result = discovery["commit_discovered_events"](candidatos)
    return {
        "status": "completed",
        "message": (
            f"Aporte guardado: {result.get('nuevos', 0)} nuevos, "
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
    svc = _get_auto_scraper_services()
    background_tasks.add_task(svc["enrich_event_images"])
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
    svc = _get_auto_scraper_services()
    background_tasks.add_task(svc["scrape_agenda_sources"])
    background_tasks.add_task(svc["scrape_compas_urbano"])
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
