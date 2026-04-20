"""
Smart Scheduler: ejecuta Smart Listener con scraping inteligente.
- Auto-scraper con Vision + Meta API cada 12 horas
- Token Meta auto-renovación cada 7 días
- Enriquecimiento de imágenes cada 12 horas
- Agenda alternativa cada 24 horas
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()


def _log_job(fuente: str, ok: bool, detalle: dict = None):
    """Persiste resultado de un job en scraping_log para visibilidad en /health/status."""
    try:
        from app.database import supabase
        supabase.table("scraping_log").insert({
            "fuente": fuente,
            "registros_nuevos": detalle.get("eventos_nuevos", 0) if detalle else 0,
            "registros_actualizados": 0,
            "errores": 0 if ok else 1,
            "detalle": detalle or {"status": "ok" if ok else "error"},
        }).execute()
    except Exception:
        pass  # No fallar el scheduler por fallo de log


# Umbral de fallos consecutivos antes de enviar alerta
ALERT_THRESHOLD = 3


def _track_failure(job_name: str, error: str) -> None:
    """
    Registra un fallo consecutivo en config_kv y envía alerta al llegar al umbral.
    Clave: 'job_failures_{job_name}' → JSON {count, last_error}
    """
    try:
        import json
        from app.database import supabase
        key = f"job_failures_{job_name}"
        resp = supabase.table("config_kv").select("value").eq("key", key).execute()
        count = 1
        if resp.data:
            try:
                stored = json.loads(resp.data[0]["value"])
                count = stored.get("count", 0) + 1
            except Exception:
                count = 1
        payload = json.dumps({"count": count, "last_error": error[:300]})
        supabase.table("config_kv").upsert(
            {"key": key, "value": payload}, on_conflict="key"
        ).execute()

        if count >= ALERT_THRESHOLD:
            from app.services.email_service import send_scraper_alert
            send_scraper_alert(job_name, error, count)
            print(f"[ALERT] Enviada alerta para {job_name} (fallos={count})")
    except Exception as e:
        print(f"[WARN] No se pudo registrar fallo de {job_name}: {e}")


def _reset_failure(job_name: str) -> None:
    """Reinicia el contador de fallos tras una ejecución exitosa."""
    try:
        import json
        from app.database import supabase
        key = f"job_failures_{job_name}"
        supabase.table("config_kv").upsert(
            {"key": key, "value": json.dumps({"count": 0, "last_error": ""})},
            on_conflict="key",
        ).execute()
    except Exception:
        pass


async def _run_scraper_job():
    """Job wrapper for the smart scraper."""
    from app.services.auto_scraper import run_auto_scraper
    try:
        result = await run_auto_scraper()
        _log_job("scheduler_auto_scraper", ok=True, detalle=result)
        _reset_failure("auto_scraper")
    except Exception as e:
        print(f"[ERR] Scheduler error: {e}")
        _log_job("scheduler_auto_scraper", ok=False, detalle={"error": str(e)})
        _track_failure("auto_scraper", str(e))


async def _run_image_enrichment():
    """Job wrapper for image enrichment."""
    from app.services.auto_scraper import enrich_event_images
    try:
        result = await enrich_event_images()
        _log_job("scheduler_image_enrichment", ok=True, detalle=result or {})
        _reset_failure("image_enrichment")
    except Exception as e:
        print(f"[ERR] Image enrichment error: {e}")
        _log_job("scheduler_image_enrichment", ok=False, detalle={"error": str(e)})
        _track_failure("image_enrichment", str(e))


async def _run_ig_sources():
    """Job wrapper for scraping ALL DB lugares with instagram_handle."""
    from app.services.auto_scraper import scrape_db_instagram_sources
    try:
        result = await scrape_db_instagram_sources()
        _log_job("scheduler_ig_sources", ok=True, detalle=result)
        _reset_failure("ig_sources")
    except Exception as e:
        print(f"[ERR] IG sources error: {e}")
        _log_job("scheduler_ig_sources", ok=False, detalle={"error": str(e)})
        _track_failure("ig_sources", str(e))


async def _run_agenda_alternativa():
    """Job wrapper for alternative agenda scraping (web sources + Compas Urbano API)."""
    from app.services.auto_scraper import scrape_agenda_sources
    from app.services.compas_urbano_scraper import scrape_compas_urbano
    try:
        r1 = await scrape_compas_urbano()   # highest priority — verified events
        r2 = await scrape_agenda_sources()  # secondary web sources
        combined = {
            "eventos_nuevos": r1.get("eventos_nuevos", 0) + r2.get("eventos_nuevos", 0),
            "duplicados": r1.get("duplicados", 0) + r2.get("duplicados", 0),
            "errores": r1.get("errores", 0) + r2.get("errores", 0),
            "compas": r1,
            "agenda": r2,
        }
        _log_job("scheduler_agenda_alternativa", ok=True, detalle=combined)
        _reset_failure("agenda_alternativa")
    except Exception as e:
        print(f"[ERR] Agenda alternativa error: {e}")
        _log_job("scheduler_agenda_alternativa", ok=False, detalle={"error": str(e)})
        _track_failure("agenda_alternativa", str(e))


async def _renew_meta_token():
    """Auto-renew Meta access token before it expires."""
    try:
        from app.services.meta_token_manager import get_valid_token, check_token_health
        health = await check_token_health()
        print(f"[META] Token health: {health}")
        if health.get("status") in ("invalid", "no_token"):
            print("[META] Token invalid, attempting renewal...")
            token = await get_valid_token()
            if token:
                print("[META] Token renewed successfully")
            else:
                print("[META] ⚠️ Token renewal failed — Instagram scraping may not work")
    except Exception as e:
        print(f"[ERR] Meta token renewal error: {e}")


async def _cleanup_old_events():
    """Remove events that are fully past (>7 days after end, or >7 days after start if no end date)."""
    try:
        from app.database import supabase
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

        # 1. Eventos con fecha_fin definida: borrar si fecha_fin < cutoff
        resp_fin = (
            supabase.table("eventos")
            .delete()
            .not_.is_("fecha_fin", "null")
            .lt("fecha_fin", cutoff)
            .execute()
        )
        deleted_fin = len(resp_fin.data) if resp_fin.data else 0

        # 2. Eventos sin fecha_fin: borrar si fecha_inicio < cutoff
        resp_inicio = (
            supabase.table("eventos")
            .delete()
            .is_("fecha_fin", "null")
            .lt("fecha_inicio", cutoff)
            .execute()
        )
        deleted_inicio = len(resp_inicio.data) if resp_inicio.data else 0

        deleted = deleted_fin + deleted_inicio
        if deleted > 0:
            print(f"[CLEANUP] Removed {deleted} expired events ({deleted_fin} with end date, {deleted_inicio} without)")
    except Exception as e:
        print(f"[ERR] Cleanup error: {e}")


def start_scheduler():
    """Start the smart periodic scraper. Called from FastAPI lifespan.
    
    Schedule:
    - Smart scraper: every 12 hours (uses Vision + Meta API for high-priority, code for rest)
    - Image enrichment: every 12 hours
    - Agenda alternativa: every 24 hours
    - Meta token renewal: every 7 days
    - Event cleanup: every 24 hours
    - Initial scrape: 5 minutes after startup

    Set DISABLE_SCRAPER=true in Railway env to skip scraping jobs when an
    external worker (AI_CULTURE II) is handling scraping instead.
    """
    import os
    scraper_disabled = os.getenv("DISABLE_SCRAPER", "false").lower() in ("true", "1", "yes")

    if not scraper_disabled:
        # Smart scraper: every 12 hours
        scheduler.add_job(
            _run_scraper_job,
            trigger=IntervalTrigger(hours=12),
            id="auto_scraper",
            name="Smart Listener (Vision + Meta API + RSS)",
            replace_existing=True,
        )

        # Enriquecer imágenes: cada 12 horas
        scheduler.add_job(
            _run_image_enrichment,
            trigger=IntervalTrigger(hours=12),
            id="image_enrichment",
            name="Enriquecimiento de imágenes",
            replace_existing=True,
        )

        # Agenda alternativa: cada 24 horas
        scheduler.add_job(
            _run_agenda_alternativa,
            trigger=IntervalTrigger(hours=24),
            id="agenda_alternativa",
            name="Agenda alternativa",
            replace_existing=True,
        )

        # Instagram BD sources: cada 8 horas (dedicated IG pass — all lugares with handle)
        scheduler.add_job(
            _run_ig_sources,
            trigger=IntervalTrigger(hours=8),
            id="ig_sources",
            name="Instagram BD sources",
            replace_existing=True,
        )

        # Initial scrape 60 minutes after startup (avoid blocking event loop right away)
        scheduler.add_job(
            _run_scraper_job,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=60)),
            id="auto_scraper_startup",
            name="Initial scrape at startup",
            replace_existing=True,
        )

        # Initial IG pass: 90 minutes after startup (after the main scraper)
        scheduler.add_job(
            _run_ig_sources,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=90)),
            id="ig_sources_startup",
            name="Initial IG sources pass at startup",
            replace_existing=True,
        )
    else:
        print("[SCHEDULER] DISABLE_SCRAPER=true — scraping jobs skipped (external worker active)")

    # Meta token renewal: cada 7 días (always runs — worker II doesn't manage this)
    scheduler.add_job(
        _renew_meta_token,
        trigger=IntervalTrigger(days=7),
        id="meta_token_renewal",
        name="Meta token auto-renewal",
        replace_existing=True,
    )

    # Event cleanup: cada 24 horas (always runs)
    scheduler.add_job(
        _cleanup_old_events,
        trigger=IntervalTrigger(hours=24),
        id="event_cleanup",
        name="Cleanup expired events",
        replace_existing=True,
    )

    # Check Meta token on startup (2 minutes after boot)
    scheduler.add_job(
        _renew_meta_token,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=2)),
        id="meta_token_startup",
        name="Meta token check at startup",
        replace_existing=True,
    )

    scheduler.start()
    if not scraper_disabled:
        print("[SCHEDULER] Smart Listener activo:")
        print("   - Smart scraper (web+IG via Meta API): cada 12h")
        print("   - Instagram BD sources (todos los lugares): cada 8h")
        print("   - Imágenes: cada 12h")
        print("   - Agenda alternativa (web fijos + BD web): cada 24h")
    print("   - Meta token renewal: cada 7 días")
    print("   - Cleanup eventos: cada 24h")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)