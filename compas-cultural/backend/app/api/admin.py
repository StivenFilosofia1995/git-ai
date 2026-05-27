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
        BLAST_KEY = "blast:2026-05c"
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

    # ── Interacciones (clicks) ────────────────────────────────────────────────
    top_espacios_clicks: list[dict] = []
    total_interacciones = 0
    interacciones_por_tipo: dict[str, int] = {}
    try:
        int_resp = (
            supabase.table("perfil_interacciones")
            .select("tipo,item_id,categoria")
            .gte("created_at", hace_7.isoformat())
            .limit(2000)
            .execute()
        )
        interacciones = int_resp.data or []
        total_interacciones = len(interacciones)
        item_counts: dict[str, int] = {}
        for row in interacciones:
            t = row.get("tipo") or "ver"
            interacciones_por_tipo[t] = interacciones_por_tipo.get(t, 0) + 1
            item = row.get("item_id")
            if item:
                item_counts[item] = item_counts.get(item, 0) + 1
        top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        if top_items:
            ids = [i for i, _ in top_items]
            lug_resp = (
                supabase.table("lugares")
                .select("id,nombre,slug,categoria_principal,barrio")
                .in_("id", ids)
                .execute()
            )
            lug_map = {l["id"]: l for l in (lug_resp.data or [])}
            for item_id, count in top_items:
                l = lug_map.get(item_id)
                if l:
                    top_espacios_clicks.append({
                        "nombre": l.get("nombre"),
                        "slug": l.get("slug"),
                        "categoria": l.get("categoria_principal"),
                        "barrio": l.get("barrio"),
                        "clicks": count,
                    })
    except Exception:
        pass

    # ── Registros por día (usuarios) ──────────────────────────────────────────
    registros_por_dia: list[dict] = []
    try:
        from app.services.email_service import _load_auth_users
        all_users = _load_auth_users(2000)
        day_counts: dict[str, int] = {}
        for u in all_users:
            created = (u.get("created_at") or "")[:10]
            if created >= hace_7.strftime("%Y-%m-%d"):
                day_counts[created] = day_counts.get(created, 0) + 1
        for i in range(6, -1, -1):
            dia = hoy_inicio - timedelta(days=i)
            k = dia.strftime("%Y-%m-%d")
            registros_por_dia.append({"fecha": dia.strftime("%d/%m"), "nuevos": day_counts.get(k, 0)})
    except Exception:
        for i in range(6, -1, -1):
            dia = hoy_inicio - timedelta(days=i)
            registros_por_dia.append({"fecha": dia.strftime("%d/%m"), "nuevos": 0})

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
        "email": {
            "blast_key": "blast:2026-05c",
            "blast_cursor": blast_cursor,
            "destinatarios_estimados": auth_users,
        },
        "scrapers": {
            "runs_7d": scraper_runs_7d,
            "nuevos_eventos_7d": total_nuevos_7d_log,
            "fuentes_activas": len(fuentes_seen),
            "ultimas_fuentes": list(fuentes_seen.values())[:10],
        },
        "interacciones": {
            "total_7d": total_interacciones,
            "por_tipo": interacciones_por_tipo,
            "top_espacios": top_espacios_clicks,
        },
        "usuarios": {
            "auth_registrados": auth_users,
            "registros_por_dia": registros_por_dia,
        },
    }


@router.get("/eventos")
def admin_list_eventos(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    categoria: str = "",
    municipio: str = "",
    reportados: bool = False,
):
    _check_key(x_api_key)
    from app.database import supabase
    offset = (max(page, 1) - 1) * per_page
    q = (
        supabase.table("eventos")
        .select(
            "id,titulo,slug,fecha_inicio,categoria_principal,municipio,barrio,"
            "verificado,reportado,fuente,imagen_url,es_gratuito,created_at",
            count="exact",
        )
        .order("fecha_inicio", desc=False)
        .range(offset, offset + per_page - 1)
    )
    if search:
        q = q.ilike("titulo", f"%{search}%")
    if categoria:
        q = q.eq("categoria_principal", categoria)
    if municipio:
        q = q.eq("municipio", municipio)
    if reportados:
        q = q.eq("reportado", True)
    resp = q.execute()
    return {"data": resp.data or [], "total": resp.count or 0, "page": page, "per_page": per_page}


@router.get("/espacios")
def admin_list_espacios(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    tipo: str = "",
    municipio: str = "",
):
    _check_key(x_api_key)
    from app.database import supabase
    offset = (max(page, 1) - 1) * per_page
    q = (
        supabase.table("lugares")
        .select(
            "id,nombre,slug,tipo,categoria_principal,municipio,barrio,"
            "instagram_handle,sitio_web,nivel_actividad,verificado,created_at",
            count="exact",
        )
        .order("nombre", desc=False)
        .range(offset, offset + per_page - 1)
    )
    if search:
        q = q.ilike("nombre", f"%{search}%")
    if tipo:
        q = q.eq("tipo", tipo)
    if municipio:
        q = q.eq("municipio", municipio)
    resp = q.execute()
    return {"data": resp.data or [], "total": resp.count or 0, "page": page, "per_page": per_page}


@router.get("/usuarios")
def admin_list_usuarios(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    page: int = 1,
    per_page: int = 50,
):
    _check_key(x_api_key)
    from app.services.email_service import _load_auth_users
    all_users = _load_auth_users(2000)
    start = (max(page, 1) - 1) * per_page
    end = start + per_page
    return {
        "data": all_users[start:end],
        "total": len(all_users),
        "page": page,
        "per_page": per_page,
    }


@router.get("/logs")
def admin_scraping_logs(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    limit: int = 100,
):
    _check_key(x_api_key)
    from app.database import supabase
    resp = (
        supabase.table("scraping_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(min(limit, 200))
        .execute()
    )
    return {"data": resp.data or [], "total": len(resp.data or [])}


@router.post("/trigger-scraper")
async def trigger_scraper(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Trigger full scraper + comfama + agenda alternativa (background)."""
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
        try:
            from app.services.comfama_scraper import run_comfama_scraper
            await run_comfama_scraper()
        except Exception as e:
            print(f"[admin] comfama error: {e}")

    asyncio.create_task(_run())
    return {"ok": True, "message": "Scraper (auto + comfama) iniciado en background"}


@router.post("/trigger-blast-tick")
def trigger_blast_tick(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Send to next pending email recipient."""
    _check_key(x_api_key)
    from app.services.email_service import send_blast_campaign_tick
    stats = send_blast_campaign_tick()
    return {"ok": True, "stats": stats}


@router.post("/reset-blast")
def reset_blast(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Reset blast campaign cursor so it starts over from recipient 0.
    Use this after bumping BLAST_KEY or to re-send to all users.
    """
    _check_key(x_api_key)
    from app.services.email_service import _kv_upsert
    BLAST_KEY = "blast:2026-05c"
    _kv_upsert(f"cursor:{BLAST_KEY}", "0")
    return {"ok": True, "message": f"Blast cursor reseteado para {BLAST_KEY}. El próximo tick arranca desde el recipient 0."}


@router.post("/trigger-cleanup")
async def trigger_cleanup(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
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


@router.post("/trigger-cleanup-news")
async def trigger_cleanup_news(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    batch_size: int = Query(default=200, ge=10, le=1000, description="Máx eventos a revisar"),
):
    """Purge upcoming events that are news/blog posts, not real cultural events."""
    _check_key(x_api_key)
    import asyncio
    from app.services.auto_scraper import cleanup_news_events

    async def _run():
        try:
            await cleanup_news_events(batch_size=batch_size)
        except Exception as e:
            print(f"[admin] cleanup-news error: {e}")

    asyncio.create_task(_run())
    return {"ok": True, "message": f"Purga de noticias iniciada en background (batch={batch_size})"}


@router.post("/full-reset")
async def full_reset(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Limpia noticias + corre todos los scrapers clave en background.
    Orden: cleanup_news → comfama → bibliotecas_mde → fundacion_epm → agenda_alternativa
    """
    _check_key(x_api_key)
    import asyncio

    async def _run():
        try:
            from app.services.auto_scraper import cleanup_news_events
            await cleanup_news_events(batch_size=500)
        except Exception as e:
            print(f"[full-reset] cleanup_news error: {e}")
        await asyncio.sleep(2)
        try:
            from app.services.comfama_scraper import run_comfama_scraper
            await run_comfama_scraper()
        except Exception as e:
            print(f"[full-reset] comfama error: {e}")
        await asyncio.sleep(2)
        try:
            from app.services.bibliotecas_mde_scraper import run_bibliotecas_mde_scraper
            await run_bibliotecas_mde_scraper(pages=6)
        except Exception as e:
            print(f"[full-reset] bibliotecas error: {e}")
        await asyncio.sleep(2)
        try:
            from app.services.fundacion_epm_scraper import run_fundacion_epm_scraper
            await run_fundacion_epm_scraper()
        except Exception as e:
            print(f"[full-reset] epm error: {e}")
        await asyncio.sleep(2)
        try:
            from app.services.auto_scraper import scrape_agenda_sources, scrape_compas_urbano
            await scrape_agenda_sources()
            await scrape_compas_urbano()
        except Exception as e:
            print(f"[full-reset] agenda_sources error: {e}")

    asyncio.create_task(_run())
    return {
        "ok": True,
        "message": "Full reset iniciado: cleanup_news → comfama → bibliotecas → epm → agenda_sources",
    }
