"""
Scheduler: ejecuta auto-scraper, discovery y social listener periódicamente.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CO_TZ = ZoneInfo("America/Bogota")
scheduler = AsyncIOScheduler(timezone=CO_TZ)


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


async def _run_cleanup():
    """Daily cleanup: remove fully-past events, keep ongoing multi-day events."""
    from app.services.auto_scraper import cleanup_past_events
    try:
        await cleanup_past_events()
    except Exception as e:
        print(f"❌ Cleanup error: {e}")


async def _run_agenda_alternativa():
    """Job wrapper for alternative agenda scraping."""
    from app.services.auto_scraper import scrape_agenda_sources
    try:
        await scrape_agenda_sources()
    except Exception as e:
        print(f"❌ Agenda alternativa error: {e}")


def start_scheduler():
    """Start the periodic scraper. Called from FastAPI lifespan."""

    # ── Auto-scraper: diario a las 6am Colombia ────────────────────────────
    # Daily is enough — excessive polling wastes Claude tokens.
    scheduler.add_job(
        _run_scraper_job,
        trigger=CronTrigger(hour=6, minute=0, timezone=CO_TZ),
        id="auto_scraper",
        name="Auto-scraper cultural (diario 6am)",
        replace_existing=True,
    )

    # ── Social Listener: cada 6 horas ──────────────────────────────────────
    scheduler.add_job(
        _run_social_listener,
        trigger=IntervalTrigger(hours=6),
        id="social_listener",
        name="Social Listener — redes sociales",
        replace_existing=True,
    )

    # ── Discovery: cada 12 horas ───────────────────────────────────────────
    scheduler.add_job(
        _run_discovery,
        trigger=IntervalTrigger(hours=12),
        id="discovery",
        name="Discovery — nuevos colectivos",
        replace_existing=True,
    )

    # ── Enriquecimiento de imágenes: cada 12 horas ─────────────────────────
    scheduler.add_job(
        _run_image_enrichment,
        trigger=IntervalTrigger(hours=12),
        id="image_enrichment",
        name="Enriquecimiento de imágenes",
        replace_existing=True,
    )

    # ── Agenda alternativa: una vez al día (2am Colombia) ──────────────────
    scheduler.add_job(
        _run_agenda_alternativa,
        trigger=CronTrigger(hour=2, minute=0, timezone=CO_TZ),
        id="agenda_alternativa",
        name="Agenda alternativa — medios independientes",
        replace_existing=True,
    )

    # ── Limpieza diaria: 1am Colombia — elimina eventos pasados ────────────
    # Respeta eventos multi-día que aún están en curso.
    scheduler.add_job(
        _run_cleanup,
        trigger=CronTrigger(hour=1, minute=0, timezone=CO_TZ),
        id="cleanup_past_events",
        name="Limpieza eventos pasados",
        replace_existing=True,
    )

    # ── Scrape inicial 60 segundos después de arrancar ─────────────────────
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(seconds=60)),
        id="auto_scraper_startup",
        name="Scrape inicial al arrancar",
        replace_existing=True,
    )

    # ── Social Listener inicial: 3 minutos después de arrancar ─────────────
    scheduler.add_job(
        _run_social_listener,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(minutes=3)),
        id="social_listener_startup",
        name="Social Listener inicial",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler iniciado (zona Colombia):")
    print("   • Auto-scraper: diario a las 6:00am (inicio en 60s)")
    print("   • Social Listener: cada 6h (inicio en 3min)")
    print("   • Discovery: cada 12h")
    print("   • Imágenes: cada 12h")
    print("   • Agenda alternativa: diaria a las 2:00am")
    print("   • Limpieza eventos pasados: diaria a las 1:00am")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ Scheduler detenido")

