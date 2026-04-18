"""
Scheduler: ejecuta scraping con codigo (sin IA) periodicamente.
Claude se usa SOLO para chat del usuario, NO para scraping automatico.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()


async def _run_scraper_job():
    """Job wrapper for the code-based scraper (NO Claude)."""
    from app.services.auto_scraper import run_auto_scraper
    try:
        await run_auto_scraper()
    except Exception as e:
        print(f"[ERR] Scheduler error: {e}")


async def _run_image_enrichment():
    """Job wrapper for image enrichment (NO Claude, just og:image tags)."""
    from app.services.auto_scraper import enrich_event_images
    try:
        await enrich_event_images()
    except Exception as e:
        print(f"[ERR] Image enrichment error: {e}")


async def _run_agenda_alternativa():
    """Job wrapper for alternative agenda scraping (code-based)."""
    from app.services.auto_scraper import scrape_agenda_sources
    try:
        await scrape_agenda_sources()
    except Exception as e:
        print(f"[ERR] Agenda alternativa error: {e}")


def start_scheduler():
    """Start the periodic scraper. Called from FastAPI lifespan.
    
    COST-OPTIMIZED: Runs once per day, uses code-based extraction.
    Claude is reserved ONLY for user chat interactions.
    """
    # Auto-scraper: UNA VEZ al dia (code-based, no Claude)
    scheduler.add_job(
        _run_scraper_job,
        trigger=IntervalTrigger(hours=24),
        id="auto_scraper",
        name="Auto-scraper cultural (code-based)",
        replace_existing=True,
    )

    # Enriquecer imagenes: cada 12 horas (no usa Claude, solo og:image)
    scheduler.add_job(
        _run_image_enrichment,
        trigger=IntervalTrigger(hours=12),
        id="image_enrichment",
        name="Enriquecimiento de imagenes",
        replace_existing=True,
    )

    # Agenda alternativa: una vez al dia (code-based)
    scheduler.add_job(
        _run_agenda_alternativa,
        trigger=IntervalTrigger(hours=24),
        id="agenda_alternativa",
        name="Agenda alternativa",
        replace_existing=True,
    )

    # Scrape inicial 10 minutos despues de arrancar
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=10)),
        id="auto_scraper_startup",
        name="Scrape inicial al arrancar",
        replace_existing=True,
    )

    scheduler.start()
    print("[SCHEDULER] Iniciado (modo AHORRO - sin Claude):")
    print("   - Auto-scraper: cada 24h (code-based, inicio en 10min)")
    print("   - Imagenes: cada 12h")
    print("   - Agenda alternativa: cada 24h")
    print("   - Claude se usa SOLO para chat del usuario")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)