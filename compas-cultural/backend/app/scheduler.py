"""
Scheduler: ejecuta auto-scraper, discovery y social listener periódicamente.
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


async def _run_social_listener():
    """Job wrapper for the social listener."""
    from app.services.social_listener import run_social_listener
    try:
        await run_social_listener()
    except Exception as e:
        print(f"❌ Social listener error: {e}")


async def _run_discovery():
    """Job wrapper for discovery (modo rápido)."""
    from app.services.discovery_service import run_discovery
    try:
        await run_discovery(mode="rapido")
    except Exception as e:
        print(f"❌ Discovery error: {e}")


async def _run_agenda_alternativa():
    """Job wrapper for alternative agenda scraping."""
    from app.services.auto_scraper import scrape_agenda_sources
    try:
        await scrape_agenda_sources()
    except Exception as e:
        print(f"❌ Agenda alternativa error: {e}")


def start_scheduler():
    """Start the periodic scraper. Called from FastAPI lifespan."""
    # Auto-scraper: cada 4 horas (más frecuente para acumular datos)
    scheduler.add_job(
        _run_scraper_job,
        trigger=IntervalTrigger(hours=4),
        id="auto_scraper",
        name="Auto-scraper cultural",
        replace_existing=True,
    )

    # Social Listener: cada 2 horas (escucha IG/FB por nuevos eventos)
    scheduler.add_job(
        _run_social_listener,
        trigger=IntervalTrigger(hours=2),
        id="social_listener",
        name="Social Listener — redes sociales",
        replace_existing=True,
    )

    # Discovery: cada 12 horas (descubre nuevos colectivos — más frecuente)
    scheduler.add_job(
        _run_discovery,
        trigger=IntervalTrigger(hours=12),
        id="discovery",
        name="Discovery — nuevos colectivos",
        replace_existing=True,
    )

    # Enriquecer imágenes: cada 6 horas
    scheduler.add_job(
        _run_image_enrichment,
        trigger=IntervalTrigger(hours=6),
        id="image_enrichment",
        name="Enriquecimiento de imágenes",
        replace_existing=True,
    )

    # Agenda alternativa: cada 8 horas
    scheduler.add_job(
        _run_agenda_alternativa,
        trigger=IntervalTrigger(hours=8),
        id="agenda_alternativa",
        name="Agenda alternativa — medios independientes",
        replace_existing=True,
    )

    # Scrape inicial 5 minutos después de arrancar (da tiempo al healthcheck)
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=5)),
        id="auto_scraper_startup",
        name="Scrape inicial al arrancar",
        replace_existing=True,
    )

    # Social Listener inicial: 7 minutos después de arrancar
    scheduler.add_job(
        _run_social_listener,
        trigger=DateTrigger(run_date=datetime.now() + timedelta(minutes=7)),
        id="social_listener_startup",
        name="Social Listener inicial",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler iniciado:")
    print("   • Auto-scraper: cada 4h (inicio en 30s)")
    print("   • Social Listener: cada 2h (inicio en 2min)")
    print("   • Discovery: cada 12h")
    print("   • Imágenes: cada 6h")
    print("   • Agenda alternativa: cada 8h")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ Scheduler detenido")
