"""Admin dashboard — aggregated metrics for platform health."""
from fastapi import APIRouter, HTTPException, Header
from app.config import settings

router = APIRouter()


def _check_key(x_api_key: str | None) -> None:
    if x_api_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


@router.get("/dashboard")
def get_dashboard(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Aggregated platform metrics for the internal admin dashboard."""
    _check_key(x_api_key)

    from app.database import supabase
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    CO_TZ = ZoneInfo("America/Bogota")
    now = datetime.now(CO_TZ)
    hoy_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
    manana = hoy_inicio + timedelta(days=1)
    semana = hoy_inicio + timedelta(days=7)
    hace_7 = hoy_inicio - timedelta(days=7)

    def _count(table: str, **filters) -> int:
        q = supabase.table(table).select("id", count="exact")
        for k, v in filters.items():
            if k.startswith("gte_"):
                q = q.gte(k[4:], v)
            elif k.startswith("lte_"):
                q = q.lte(k[4:], v)
            elif k.startswith("neq_"):
                q = q.neq(k[4:], v)
            elif k.startswith("not_null_"):
                q = q.not_.is_(k[9:], "null")
            else:
                q = q.eq(k, v)
        try:
            return q.execute().count or 0
        except Exception:
            return 0

    # ── Eventos ───────────────────────────────────────────────────────────────
    total_eventos = _count("eventos")
    eventos_hoy = _count("eventos",
        gte_fecha_inicio=hoy_inicio.isoformat(),
        lte_fecha_inicio=manana.isoformat())
    eventos_proxima_semana = _count("eventos",
        gte_fecha_inicio=hoy_inicio.isoformat(),
        lte_fecha_inicio=semana.isoformat())
    eventos_con_imagen = _count("eventos", not_null_imagen_url="")
    eventos_verificados = _count("eventos", verificado=True)
    eventos_nuevos_7d = _count("eventos", gte_created_at=hace_7.isoformat())

    # Categorías top
    try:
        cat_resp = (
            supabase.table("eventos")
            .select("categoria_principal")
            .gte("fecha_inicio", hoy_inicio.isoformat())
            .lte("fecha_inicio", semana.isoformat())
            .limit(500)
            .execute()
        )
        cat_counts: dict[str, int] = {}
        for ev in (cat_resp.data or []):
            cat = ev.get("categoria_principal") or "otro"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        top_categorias = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    except Exception:
        top_categorias = []

    # ── Espacios ─────────────────────────────────────────────────────────────
    total_espacios = _count("lugares")
    espacios_activos = _count("lugares", neq_nivel_actividad="cerrado")
    colectivos = _count("lugares", tipo="colectivo")
    con_instagram = _count("lugares", not_null_instagram_handle="")

    # ── Usuarios ─────────────────────────────────────────────────────────────
    try:
        from app.services.email_service import _load_auth_users
        auth_users = len(_load_auth_users(2000))
    except Exception:
        auth_users = 0

    # ── Email blast ───────────────────────────────────────────────────────────
    try:
        from app.services.email_service import _kv_get
        BLAST_KEY = "blast:2026-05b"
        blast_cursor = int(_kv_get(f"cursor:{BLAST_KEY}") or "0")
    except Exception:
        blast_cursor = 0

    # ── Scraping logs (últimas 48h) ───────────────────────────────────────────
    try:
        log_resp = (
            supabase.table("scraping_log")
            .select("fuente,registros_nuevos,errores,duracion_segundos,created_at")
            .gte("created_at", hace_7.isoformat())
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
        logs = log_resp.data or []

        # Aggregate by source (latest run per source)
        fuentes_seen: dict[str, dict] = {}
        for l in logs:
            f = l.get("fuente") or "desconocido"
            if f not in fuentes_seen:
                fuentes_seen[f] = l

        total_nuevos_7d_log = sum(l.get("registros_nuevos") or 0 for l in logs)
        scraper_runs_7d = len(logs)
    except Exception:
        fuentes_seen = {}
        total_nuevos_7d_log = 0
        scraper_runs_7d = 0
        logs = []

    # ── Recent events by day (last 7 days) ───────────────────────────────────
    eventos_por_dia: list[dict] = []
    try:
        for i in range(6, -1, -1):
            dia = hoy_inicio - timedelta(days=i)
            dia_fin = dia + timedelta(days=1)
            n = _count("eventos",
                gte_created_at=dia.isoformat(),
                lte_created_at=dia_fin.isoformat())
            eventos_por_dia.append({
                "fecha": dia.strftime("%d/%m"),
                "nuevos": n,
            })
    except Exception:
        pass

    return {
        "generado_en": now.isoformat(),
        "eventos": {
            "total": total_eventos,
            "hoy": eventos_hoy,
            "proxima_semana": eventos_proxima_semana,
            "con_imagen": eventos_con_imagen,
            "verificados": eventos_verificados,
            "nuevos_7d": eventos_nuevos_7d,
            "top_categorias": [{"cat": c, "n": n} for c, n in top_categorias],
            "por_dia": eventos_por_dia,
        },
        "espacios": {
            "total": total_espacios,
            "activos": espacios_activos,
            "colectivos": colectivos,
            "con_instagram": con_instagram,
        },
        "usuarios": {
            "auth_registrados": auth_users,
        },
        "email": {
            "blast_key": "blast:2026-05b",
            "blast_cursor": blast_cursor,
            "destinatarios_estimados": auth_users,
        },
        "scrapers": {
            "runs_7d": scraper_runs_7d,
            "nuevos_eventos_7d": total_nuevos_7d_log,
            "fuentes_activas": len(fuentes_seen),
            "ultimas_fuentes": list(fuentes_seen.values())[:10],
        },
    }


@router.post("/trigger-scraper")
def trigger_scraper(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Trigger full scraper + agenda alternativa (background)."""
    _check_key(x_api_key)
    from fastapi import BackgroundTasks
    import asyncio

    async def _run():
        from app.services.auto_scraper import run_auto_scraper, scrape_agenda_sources
        try:
            await run_auto_scraper()
        except Exception as e:
            print(f"[admin] scraper error: {e}")
        try:
            await scrape_agenda_sources()
        except Exception as e:
            print(f"[admin] agenda alt error: {e}")

    asyncio.create_task(_run())
    return {"ok": True, "message": "Scraper iniciado en background"}


@router.post("/trigger-blast-tick")
def trigger_blast_tick(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Send to next pending email recipient."""
    _check_key(x_api_key)
    from app.services.email_service import send_blast_campaign_tick
    stats = send_blast_campaign_tick()
    return {"ok": True, "stats": stats}


@router.post("/trigger-cleanup")
def trigger_cleanup(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Remove fully-past events."""
    _check_key(x_api_key)
    import asyncio
    from app.services.auto_scraper import cleanup_past_events

    async def _run():
        try:
            await cleanup_past_events()
        except Exception as e:
            print(f"[admin] cleanup error: {e}")

    asyncio.create_task(_run())
    return {"ok": True, "message": "Limpieza iniciada en background"}
