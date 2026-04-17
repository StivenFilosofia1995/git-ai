"""
Scheduler: ejecuta el auto-scraper periódicamente usando APScheduler.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()


async def _run_scraper_job():
    """Job wrapper for the auto-scraper."""
    from app.services.auto_scraper import run_auto_scraper
    try:
        await run_auto_scraper()
    except Exception as e:
        print(f"❌ Scheduler error: {e}")


async def _run_image_enrichment():
    """Job wrapper for image enrichment."""
    from app.services.auto_scraper import enrich_event_images
    try:
        await enrich_event_images()
    except Exception as e:
        print(f"❌ Image enrichment error: {e}")


def start_scheduler():
    """Start the periodic scraper. Called from FastAPI lifespan."""
    # Scrape completo cada 6 horas
    scheduler.add_job(
        _run_scraper_job,
        trigger=IntervalTrigger(hours=6),
        id="auto_scraper",
        name="Auto-scraper cultural",
        replace_existing=True,
    )

    # Enriquecer imágenes cada 8 horas
    scheduler.add_job(
        _run_image_enrichment,
        trigger=IntervalTrigger(hours=8),
        id="image_enrichment",
        name="Enriquecimiento de imágenes",
        replace_existing=True,
    )

    # Scrape inicial 30 segundos después de arrancar
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
        id="auto_scraper_startup",
        name="Scrape inicial al arrancar",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler iniciado — scrape inicial en 30s, luego cada 6 horas")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ Scheduler detenido")
