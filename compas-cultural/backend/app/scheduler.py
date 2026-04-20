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


async def _run_scraper_job():
    """Job wrapper for the smart scraper."""
    from app.services.auto_scraper import run_auto_scraper
    try:
        await run_auto_scraper()
    except Exception as e:
        print(f"[ERR] Scheduler error: {e}")


async def _run_image_enrichment():
    """Job wrapper for image enrichment."""
    from app.services.auto_scraper import enrich_event_images
    try:
        await enrich_event_images()
    except Exception as e:
        print(f"[ERR] Image enrichment error: {e}")


async def _run_agenda_alternativa():
    """Job wrapper for alternative agenda scraping."""
    from app.services.auto_scraper import scrape_agenda_sources
    try:
        await scrape_agenda_sources()
    except Exception as e:
        print(f"[ERR] Agenda alternativa error: {e}")


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
    """Remove events that are more than 7 days past their end date."""
    try:
        from app.database import supabase
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        resp = supabase.table("eventos").delete().lt("fecha_inicio", cutoff).execute()
        deleted = len(resp.data) if resp.data else 0
        if deleted > 0:
            print(f"[CLEANUP] Removed {deleted} expired events")
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
    """
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

    # Meta token renewal: cada 7 días
    scheduler.add_job(
        _renew_meta_token,
        trigger=IntervalTrigger(days=7),
        id="meta_token_renewal",
        name="Meta token auto-renewal",
        replace_existing=True,
    )

    # Event cleanup: cada 24 horas
    scheduler.add_job(
        _cleanup_old_events,
        trigger=IntervalTrigger(hours=24),
        id="event_cleanup",
        name="Cleanup expired events",
        replace_existing=True,
    )

    # Initial scrape 5 minutes after startup
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=5)),
        id="auto_scraper_startup",
        name="Initial scrape at startup",
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
    print("[SCHEDULER] Smart Listener activo:")
    print("   - Smart scraper: cada 12h (Vision + Meta API + RSS)")
    print("   - Imágenes: cada 12h")
    print("   - Agenda alternativa: cada 24h")
    print("   - Meta token renewal: cada 7 días")
    print("   - Cleanup eventos: cada 24h")
    print("   Smart Listener activo — Vision + Meta API + RSS")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)