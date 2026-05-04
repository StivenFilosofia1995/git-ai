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


def _run_weekly_digest():
    """Digest tick: sends at most one recipient per execution."""
    from app.services.email_service import send_weekly_digest_campaign
    try:
        stats = send_weekly_digest_campaign()
        print(
            "📬 Digest tick: "
            f"destinatarios={stats.get('recipients', 0)} | "
            f"sent={stats.get('sent', 0)} | "
            f"skipped={stats.get('skipped', 0)} | "
            f"failed={stats.get('failed', 0)} | "
            f"target={stats.get('target_email') or '-'}"
        )
    except Exception as e:
        print(f"❌ Digest tick error: {e}")


def _run_privacy_cleanup():
    """Job wrapper for automatic privacy/data retention cleanup."""
    from app.services.privacy_cleanup import run_privacy_cleanup
    try:
        stats = run_privacy_cleanup()
        print(
            "🧹 Privacy cleanup: "
            f"solicitudes={stats.get('solicitudes_eliminadas', 0)} | "
            f"logs={stats.get('scraping_logs_eliminados', 0)} | "
            f"ocr_rows={stats.get('ocr_rows_eliminados', 0)} | "
            f"ocr_textos={stats.get('ocr_textos_borrados', 0)}"
        )
    except Exception as e:
        print(f"❌ Privacy cleanup error: {e}")


def start_scheduler():
    """Start the periodic scraper. Called from FastAPI lifespan."""

    # ── Auto-scraper: diario 2:00 AM Colombia ─────────────────────────────
    scheduler.add_job(
        _run_scraper_job,
        trigger=CronTrigger(hour=2, minute=0, timezone=CO_TZ),
        id="auto_scraper",
        name="Auto-scraper cultural (diario 2:00am, hora Colombia)",
        replace_existing=True,
    )

    # ── Social Listener: cada 3 horas ──────────────────────────────────────
    scheduler.add_job(
        _run_social_listener,
        trigger=CronTrigger(hour="*/3", minute=25, timezone=CO_TZ),
        id="social_listener",
        name="Social Listener — redes sociales (cada 3h)",
        replace_existing=True,
    )

    # ── Discovery: 2 veces al día ──────────────────────────────────────────
    scheduler.add_job(
        _run_discovery,
        trigger=CronTrigger(hour="8,20", minute=10, timezone=CO_TZ),
        id="discovery",
        name="Discovery — nuevos colectivos (08:10, 20:10)",
        replace_existing=True,
    )

    # ── Enriquecimiento de imágenes: 2 veces al día ────────────────────────
    scheduler.add_job(
        _run_image_enrichment,
        trigger=CronTrigger(hour="10,22", minute=20, timezone=CO_TZ),
        id="image_enrichment",
        name="Enriquecimiento de imágenes (10:20, 22:20)",
        replace_existing=True,
    )

    # ── Agenda alternativa: 4 veces al día ─────────────────────────────────
    scheduler.add_job(
        _run_agenda_alternativa,
        trigger=CronTrigger(hour="7,11,16,21", minute=40, timezone=CO_TZ),
        id="agenda_alternativa",
        name="Agenda alternativa — medios independientes (4x día)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_weekly_digest,
        trigger=CronTrigger(minute="*/5", timezone=CO_TZ),
        id="weekly_digest",
        name="Boletín semanal (goteo cada 5 minutos)",
        replace_existing=True,
    )

    # ── Limpieza de privacidad: diaria 3:30 AM Colombia ───────────────────
    scheduler.add_job(
        _run_privacy_cleanup,
        trigger=CronTrigger(hour=3, minute=30, timezone=CO_TZ),
        id="privacy_cleanup",
        name="Limpieza automática de datos (privacidad)",
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

    # ── Limpieza inicial 30 segundos después de arrancar ────────────────────
    # Elimina eventos pasados ANTES de que corra el scraper.
    scheduler.add_job(
        _run_cleanup,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(seconds=30)),
        id="cleanup_startup",
        name="Limpieza inicial al arrancar",
        replace_existing=True,
    )

    # ── Scrape inicial 90 segundos después de arrancar ─────────────────────
    # Corre después del cleanup para traer eventos del día actual.
    scheduler.add_job(
        _run_scraper_job,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(seconds=90)),
        id="auto_scraper_startup",
        name="Scrape inicial al arrancar",
        replace_existing=True,
    )

    # ── Agenda alternativa inicial: 3 minutos después de arrancar ──────────
    # Asegura que fuentes alternativas (teatros, bibliotecas, colectivos)
    # sean rastreadas en el mismo ciclo de arranque.
    scheduler.add_job(
        _run_agenda_alternativa,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(seconds=180)),
        id="agenda_alternativa_startup",
        name="Agenda alternativa inicial al arrancar",
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

    # ── Privacy cleanup inicial: 5 minutos tras arranque ──────────────────
    scheduler.add_job(
        _run_privacy_cleanup,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(minutes=5)),
        id="privacy_cleanup_startup",
        name="Limpieza de datos inicial",
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler iniciado (zona Colombia):")
    print("   • Limpieza inicial: en 30s (startup)")
    print("   • Scrape inicial: en 90s (startup)")
    print("   • Auto-scraper: diario a las 02:00")
    print("   • Social Listener: cada 3h (minuto 25, inicio en 3min)")
    print("   • Discovery: 08:10 y 20:10")
    print("   • Imágenes: 10:20 y 22:20")
    print("   • Agenda alternativa: 07:40, 11:40, 16:40, 21:40")
    print("   • Boletín semanal: 1 destinatario cada 5 minutos")
    print("   • Limpieza de privacidad: diaria a las 3:30am")
    print("   • Limpieza eventos pasados: diaria a las 1:00am")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ Scheduler detenido")

