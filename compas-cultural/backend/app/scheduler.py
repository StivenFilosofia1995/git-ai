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


async def _run_precision_scraper_job():
    """Job wrapper for the precision scraper (runs all lugares + agenda alternativa)."""
    from app.services.precision_scraper import run_precision_scraper
    try:
        await run_precision_scraper(
            run_agenda_sources=True,
            run_vision_listener=False,
            enrich_images=True,
        )
    except Exception as e:
        print(f"❌ Precision scraper error: {e}")


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
    from app.services.auto_scraper import scrape_agenda_sources, scrape_compas_urbano
    try:
        await scrape_agenda_sources()
        await scrape_compas_urbano()
    except Exception as e:
        print(f"❌ Agenda alternativa error: {e}")


async def _run_comfama_scraper():
    """Job wrapper for dedicated Comfama scraper (eventos, bibliotecas, centros culturales)."""
    from app.services.comfama_scraper import run_comfama_scraper
    try:
        await run_comfama_scraper()
    except Exception as e:
        print(f"❌ Comfama scraper error: {e}")


async def _run_fundacion_epm_scraper():
    """Job wrapper for Fundación EPM scraper (UVAs, Parque Deseos, Biblioteca EPM, Planetario)."""
    from app.services.fundacion_epm_scraper import run_fundacion_epm_scraper
    try:
        await run_fundacion_epm_scraper()
    except Exception as e:
        print(f"❌ Fundación EPM scraper error: {e}")


async def _run_bibliotecas_mde_scraper():
    """Job wrapper para la Red de Bibliotecas Públicas de Medellín."""
    from app.services.bibliotecas_mde_scraper import run_bibliotecas_mde_scraper
    try:
        await run_bibliotecas_mde_scraper()
    except Exception as e:
        print(f"❌ Bibliotecas MDE scraper error: {e}")


def _run_weekly_digest():
    """Digest tick: sends at most one recipient per execution (Mondays only)."""
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


def _run_blast_tick():
    """Blast campaign tick — sends to next unsent user (any day)."""
    from app.services.email_service import send_blast_campaign_tick
    try:
        stats = send_blast_campaign_tick()
        if stats.get("sent") or stats.get("failed"):
            print(
                "🚀 Blast tick: "
                f"sent={stats.get('sent', 0)} | "
                f"skipped={stats.get('skipped', 0)} | "
                f"failed={stats.get('failed', 0)} | "
                f"target={stats.get('target_email') or '-'}"
            )
    except Exception as e:
        print(f"❌ Blast tick error: {e}")


def _reset_weekly_digest_cursor():
    """Every Monday 6am: reset the weekly digest cursor so the drip restarts."""
    from app.services.email_service import _week_start_iso, _kv_upsert
    try:
        week_start = _week_start_iso()
        _kv_upsert(f"weekly_digest_cursor:{week_start}", "0")
        print(f"📬 Digest cursor reiniciado para semana {week_start}")
    except Exception as e:
        print(f"❌ Digest cursor reset error: {e}")


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

    # ── Auto-scraper legacy: diario 2:00 AM Colombia ──────────────────────
    scheduler.add_job(
        _run_scraper_job,
        trigger=CronTrigger(hour=2, minute=0, timezone=CO_TZ),
        id="auto_scraper",
        name="Auto-scraper cultural (diario 2:00am, hora Colombia)",
        replace_existing=True,
    )

    # ── Precision scraper: 3 veces al día — alta frecuencia, todos los lugares ─
    scheduler.add_job(
        _run_precision_scraper_job,
        trigger=CronTrigger(hour="6,13,19", minute=30, timezone=CO_TZ),
        id="precision_scraper",
        name="Precision scraper (6:30, 13:30, 19:30 Colombia)",
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

    # ── Comfama scraper dedicado: 3 veces al día ───────────────────────────
    scheduler.add_job(
        _run_comfama_scraper,
        trigger=CronTrigger(hour="8,14,20", minute=15, timezone=CO_TZ),
        id="comfama_scraper",
        name="Comfama — eventos, bibliotecas, centros culturales (3x día)",
        replace_existing=True,
    )

    # ── Fundación EPM / UVAs scraper: 2 veces al día ───────────────────────
    scheduler.add_job(
        _run_fundacion_epm_scraper,
        trigger=CronTrigger(hour="9,18", minute=45, timezone=CO_TZ),
        id="fundacion_epm_scraper",
        name="Fundación EPM — UVAs, Parque Deseos, Biblioteca EPM, Planetario (2x día)",
        replace_existing=True,
    )

    # ── Bibliotecas Públicas de Medellín: 2 veces al día ───────────────────
    scheduler.add_job(
        _run_bibliotecas_mde_scraper,
        trigger=CronTrigger(hour="7,19", minute=30, timezone=CO_TZ),
        id="bibliotecas_mde_scraper",
        name="Red de Bibliotecas Públicas Medellín (07:30, 19:30)",
        replace_existing=True,
    )

    scheduler.add_job(
        _run_weekly_digest,
        trigger=CronTrigger(minute="*/4", timezone=CO_TZ),
        id="weekly_digest",
        name="Boletín semanal (goteo cada 4 minutos)",
        replace_existing=True,
    )

    # ── Blast campaign: cada 4 minutos — envío a todos los usuarios ───────────
    scheduler.add_job(
        _run_blast_tick,
        trigger=CronTrigger(minute="*/4", timezone=CO_TZ),
        id="blast_campaign",
        name="Blast campaign — goteo a todos los usuarios (cada 4min)",
        replace_existing=True,
    )

    # ── Digest reset: cada lunes 6:00 AM Colombia → reinicia cursor ──────
    scheduler.add_job(
        _reset_weekly_digest_cursor,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=CO_TZ),
        id="weekly_digest_reset_monday",
        name="Reinicio cursor boletín semanal (lunes 6am)",
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

    # ── Comfama scraper inicial: 4 minutos después de arrancar ─────────────
    scheduler.add_job(
        _run_comfama_scraper,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(minutes=4)),
        id="comfama_scraper_startup",
        name="Comfama scraper inicial al arrancar",
        replace_existing=True,
    )

    # ── Fundación EPM scraper inicial: 6 minutos después de arrancar ───────
    scheduler.add_job(
        _run_fundacion_epm_scraper,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(minutes=6)),
        id="fundacion_epm_scraper_startup",
        name="Fundación EPM scraper inicial al arrancar",
        replace_existing=True,
    )

    # ── Bibliotecas MDE scraper inicial: 8 minutos después de arrancar ─────
    scheduler.add_job(
        _run_bibliotecas_mde_scraper,
        trigger=DateTrigger(run_date=datetime.now(CO_TZ) + timedelta(minutes=8)),
        id="bibliotecas_mde_scraper_startup",
        name="Bibliotecas Públicas MDE inicial al arrancar",
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
    print("   • Comfama scraper: 08:15, 14:15, 20:15 (inicio en 4min)")
    print("   • Fundación EPM / UVAs: 09:45, 18:45 (inicio en 6min)")
    print("   • Bibliotecas Públicas MDE: 07:30, 19:30 (inicio en 8min)")
    print("   • Boletín semanal: 1 destinatario cada 4 minutos (solo lunes)")
    print("   • Limpieza de privacidad: diaria a las 3:30am")
    print("   • Limpieza eventos pasados: diaria a las 1:00am")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ Scheduler detenido")

