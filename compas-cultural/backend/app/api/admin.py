"""Admin dashboard — aggregated metrics for platform health."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Query, UploadFile, File
from pydantic import BaseModel
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
):
    _check_key(x_api_key)
    from app.database import supabase
    try:
        offset = (max(page, 1) - 1) * per_page
        q = (
            supabase.table("eventos")
            .select("*", count="exact")
            .order("fecha_inicio", desc=False)
            .range(offset, offset + per_page - 1)
        )
        if search:
            q = q.ilike("titulo", f"%{search}%")
        if categoria:
            q = q.eq("categoria_principal", categoria)
        if municipio:
            q = q.eq("municipio", municipio)
        resp = q.execute()
        return {"data": resp.data or [], "total": resp.count or 0, "page": page, "per_page": per_page}
    except Exception as exc:
        print(f"[admin/eventos ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"admin/eventos error: {type(exc).__name__}: {exc}")


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
        .select("*", count="exact")
        .order("nombre", desc=False)
        .range(offset, offset + per_page - 1)
    )
    if search:
        q = q.ilike("nombre", f"%{search}%")
    if tipo:
        q = q.eq("tipo", tipo)
    if municipio:
        q = q.eq("municipio", municipio)
    try:
        resp = q.execute()
        return {"data": resp.data or [], "total": resp.count or 0, "page": page, "per_page": per_page}
    except Exception as exc:
        print(f"[admin/espacios ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"admin/espacios error: {type(exc).__name__}: {exc}")


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
    try:
        resp = (
            supabase.table("scraping_log")
            .select("*")
            .limit(min(limit, 200))
            .execute()
        )
        return {"data": resp.data or [], "total": len(resp.data or [])}
    except Exception as exc:
        print(f"[admin/logs ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"admin/logs error: {type(exc).__name__}: {exc}")


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


@router.post("/trigger-weekly-digest")
def trigger_weekly_digest(
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Force-send the weekly digest to ALL pending users right now (bypasses Monday restriction).
    Runs in background — returns immediately. Check Railway logs for progress.
    Safe to call multiple times — each user is only sent once per week via digest markers.
    """
    _check_key(x_api_key)

    def _run():
        from app.services.email_service import send_weekly_digest_campaign
        total_sent = 0
        total_skipped = 0
        total_failed = 0
        for i in range(500):
            stats = send_weekly_digest_campaign(dry_run=True)
            total_sent += stats.get("sent", 0)
            total_skipped += stats.get("skipped", 0)
            total_failed += stats.get("failed", 0)
            if stats.get("sent", 0) == 0 and stats.get("failed", 0) == 0:
                break
        print(
            f"📬 Manual digest completado — enviados={total_sent} "
            f"omitidos={total_skipped} fallidos={total_failed} "
            f"semana={stats.get('week_start')}"
        )

    background_tasks.add_task(_run)
    return {"ok": True, "message": "Digest iniciado en background — revisa los logs de Railway para ver el progreso"}


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


# ═══════════════════════════════════════════════════════════════
# ADMIN EVENT UPLOAD
# ═══════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80]


class EventoAdminCreate(BaseModel):
    titulo: str
    fecha_inicio: str               # ISO date or datetime
    hora_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    duracion_minutos: Optional[int] = None
    descripcion: Optional[str] = None
    categoria_principal: str = "otro"
    municipio: str = "medellin"
    barrio: Optional[str] = None
    nombre_lugar: Optional[str] = None
    espacio_id: Optional[str] = None
    precio: Optional[str] = None
    es_gratuito: bool = True
    imagen_url: Optional[str] = None
    link_externo: Optional[str] = None
    oculto: bool = False


class EventoAdminUpdate(BaseModel):
    titulo: Optional[str] = None
    fecha_inicio: Optional[str] = None
    hora_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    duracion_minutos: Optional[int] = None
    descripcion: Optional[str] = None
    categoria_principal: Optional[str] = None
    municipio: Optional[str] = None
    barrio: Optional[str] = None
    nombre_lugar: Optional[str] = None
    precio: Optional[str] = None
    es_gratuito: Optional[bool] = None
    imagen_url: Optional[str] = None
    oculto: Optional[bool] = None


@router.post("/eventos/imagen")
async def upload_evento_imagen(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    file: UploadFile = File(...),
    slug: str = Query(default="evento"),
):
    """Upload a poster/image to Supabase Storage. Returns the public URL."""
    _check_key(x_api_key)
    from app.services.storage_service import upload_event_image

    file_bytes = await file.read()
    try:
        url = upload_event_image(file_bytes, file.filename or "image", slug)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.post("/eventos/extraer-de-imagen")
async def extraer_evento_de_imagen(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    file: UploadFile = File(None),
    imagen_url: str = Query(default=""),
):
    """Use Claude Haiku Vision to extract event fields from a poster/image.
    Accepts either a file upload or an already-uploaded image URL.
    Returns extracted fields ready to populate the event form.
    """
    _check_key(x_api_key)
    import base64, os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY no configurada en el servidor")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        if file:
            file_bytes = await file.read()
            b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
            media_type = file.content_type or "image/jpeg"
            image_source: dict = {"type": "base64", "media_type": media_type, "data": b64}
        elif imagen_url:
            image_source = {"type": "url", "url": imagen_url}
        else:
            raise HTTPException(status_code=400, detail="Se requiere archivo o imagen_url")

        prompt = """Analiza este afiche/poster de evento cultural colombiano y extrae la información en JSON.

Devuelve SOLO un objeto JSON válido con estos campos (null si no aparece en la imagen):
{
  "titulo": "nombre completo del evento",
  "fecha_inicio": "YYYY-MM-DD",
  "fecha_fin": "YYYY-MM-DD o null",
  "hora_inicio": "HH:MM en formato 24h o null",
  "nombre_lugar": "nombre del lugar o espacio",
  "barrio": "barrio si aparece",
  "municipio": "ciudad (por defecto medellin)",
  "descripcion": "descripción corta del evento (máx 200 chars)",
  "categoria_principal": "una de: teatro|musica_en_vivo|danza|cine|festival|taller|conferencia|galeria|hip_hop|jazz|electronica|fotografia|filosofia|otro",
  "precio": "precio como texto ej: $25.000 o null si es gratis",
  "es_gratuito": true o false,
  "link_externo": "URL, email o contacto si aparece"
}

Si hay fechas en formato colombiano (ej: 15 de junio de 2026) conviértelas a YYYY-MM-DD.
Si la hora aparece como "7pm" conviértela a "19:00".
Responde SOLO con el JSON, sin explicaciones."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": image_source},
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        import json
        extracted = json.loads(raw)
        return {"ok": True, "data": extracted}

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[extraer-de-imagen ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"Error extrayendo datos: {type(exc).__name__}: {exc}")


@router.post("/eventos/crear-masivo")
async def crear_eventos_masivo(
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    files: list[UploadFile] = File(...),
):
    """Upload multiple posters, extract data with AI, and create all events.
    Runs in background. Returns a job_id to track progress via /admin/eventos/masivo-status/{job_id}.
    """
    _check_key(x_api_key)
    import uuid, os
    from app.database import supabase

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY no configurada")

    job_id = str(uuid.uuid4())[:8]
    # Store job status in config_kv
    from app.services.email_service import _kv_upsert
    import json
    _kv_upsert(f"masivo_job:{job_id}", json.dumps({
        "status": "processing", "total": len(files),
        "done": 0, "errors": 0, "created": []
    }))

    # Read all file bytes immediately (before background task)
    files_data = []
    for f in files:
        b = await f.read()
        files_data.append({"bytes": b, "content_type": f.content_type or "image/jpeg", "name": f.filename or "image"})

    def _run():
        import anthropic, base64, time, re, unicodedata
        client = anthropic.Anthropic(api_key=api_key)

        for i, fd in enumerate(files_data):
            try:
                b64 = base64.standard_b64encode(fd["bytes"]).decode()
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=800,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": fd["content_type"], "data": b64}},
                        {"type": "text", "text": """Extrae datos del afiche cultural. Devuelve SOLO JSON:
{"titulo":"...","fecha_inicio":"YYYY-MM-DD","fecha_fin":"YYYY-MM-DD o null","hora_inicio":"HH:MM o null","nombre_lugar":"...","barrio":"...","municipio":"medellin","descripcion":"...","categoria_principal":"teatro|musica_en_vivo|danza|cine|festival|taller|conferencia|galeria|hip_hop|jazz|electronica|fotografia|filosofia|otro","precio":"...","es_gratuito":true,"link_externo":"..."}"""},
                    ]}],
                )
                raw = msg.content[0].text.strip().strip("```").lstrip("json").strip()
                import json as _json
                ev = _json.loads(raw)

                # Build slug
                t = unicodedata.normalize("NFD", (ev.get("titulo") or "evento").lower())
                t = "".join(c for c in t if unicodedata.category(c) != "Mn")
                t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]
                slug = f"{t}-{int(time.time()) % 100000}"

                data = {
                    "titulo": ev.get("titulo") or "Evento sin título",
                    "slug": slug,
                    "fecha_inicio": ev.get("fecha_inicio") or "",
                    "categoria_principal": ev.get("categoria_principal") or "otro",
                    "municipio": ev.get("municipio") or "medellin",
                    "verificado": True,
                    "fuente": "admin_manual",
                    "es_gratuito": bool(ev.get("es_gratuito", True)),
                    "oculto": False,
                    "hora_confirmada": bool(ev.get("hora_inicio")),
                }
                if ev.get("hora_inicio") and ev.get("fecha_inicio"):
                    data["fecha_inicio"] = f"{ev['fecha_inicio'][:10]}T{ev['hora_inicio']}:00"
                if ev.get("fecha_fin"): data["fecha_fin"] = ev["fecha_fin"]
                if ev.get("descripcion"): data["descripcion"] = ev["descripcion"]
                if ev.get("barrio"): data["barrio"] = ev["barrio"]
                if ev.get("nombre_lugar"): data["nombre_lugar"] = ev["nombre_lugar"]
                if ev.get("precio"): data["precio"] = ev["precio"]
                if ev.get("link_externo"): data["fuente_url"] = ev["link_externo"]

                if data["fecha_inicio"]:
                    # Skip events with dates more than 3 days in the past
                    from datetime import datetime as _dtt, timezone as _tz
                    try:
                        fi = data["fecha_inicio"][:10]
                        if fi < (_dtt.now(_tz.utc) - __import__('datetime').timedelta(days=3)).strftime("%Y-%m-%d"):
                            created_id = None  # past event — skip
                        else:
                            res = supabase.table("eventos").insert(data).execute()
                            created_id = res.data[0]["id"] if res.data else None
                    except Exception:
                        res = supabase.table("eventos").insert(data).execute()
                        created_id = res.data[0]["id"] if res.data else None
                else:
                    created_id = None

                status = json.loads(_kv_get(f"masivo_job:{job_id}") or "{}")
                status["done"] = i + 1
                if created_id:
                    status["created"].append({"id": created_id, "titulo": data["titulo"]})
                _kv_upsert(f"masivo_job:{job_id}", json.dumps(status))

            except Exception as exc:
                print(f"[masivo] error en imagen {i}: {exc}")
                try:
                    status = json.loads(_kv_get(f"masivo_job:{job_id}") or "{}")
                    status["done"] = i + 1
                    status["errors"] = status.get("errors", 0) + 1
                    _kv_upsert(f"masivo_job:{job_id}", json.dumps(status))
                except Exception:
                    pass

        # Mark complete
        try:
            from app.services.email_service import _kv_get as _get
            status = json.loads(_get(f"masivo_job:{job_id}") or "{}")
            status["status"] = "done"
            _kv_upsert(f"masivo_job:{job_id}", json.dumps(status))
        except Exception:
            pass

    from app.services.email_service import _kv_get
    background_tasks.add_task(_run)
    return {"ok": True, "job_id": job_id, "total": len(files_data), "message": f"Procesando {len(files_data)} imágenes en background"}


@router.get("/eventos/masivo-status/{job_id}")
def masivo_status(job_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Check progress of a bulk image processing job."""
    _check_key(x_api_key)
    from app.services.email_service import _kv_get
    import json
    raw = _kv_get(f"masivo_job:{job_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return json.loads(raw)


@router.post("/eventos/crear")
def admin_crear_evento(
    body: EventoAdminCreate,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Create a manually-curated event (verificado=True, fuente='admin_manual')."""
    _check_key(x_api_key)
    from app.database import supabase
    import time

    base_slug = _slugify(body.titulo)
    slug = f"{base_slug}-{int(time.time()) % 100000}"

    # Check slug uniqueness
    try:
        existing = supabase.table("eventos").select("id").eq("slug", slug).limit(1).execute()
        if existing.data:
            slug = f"{slug}-{int(time.time()) % 9999}"
    except Exception:
        pass  # slug collision check is best-effort

    # Combine fecha_inicio + hora_inicio into full datetime if time provided
    fecha_inicio = body.fecha_inicio
    if body.hora_inicio:
        # Normalize time: "12:00 p. m." → "12:00", "3:00 p.m." → "15:00", etc.
        hora = body.hora_inicio.lower().replace(" ", "").replace(".", "")
        try:
            from datetime import datetime as _dt
            for fmt in ("%I:%M%p", "%H:%M", "%I%p"):
                try:
                    t = _dt.strptime(hora, fmt)
                    hora_iso = t.strftime("%H:%M")
                    break
                except ValueError:
                    continue
            else:
                hora_iso = hora[:5]  # fallback: take first 5 chars
            # Attach time to date
            date_part = body.fecha_inicio[:10]
            fecha_inicio = f"{date_part}T{hora_iso}:00"
        except Exception:
            pass  # keep original fecha_inicio if parsing fails

    data: dict = {
        "titulo": body.titulo,
        "slug": slug,
        "fecha_inicio": fecha_inicio,
        "categoria_principal": body.categoria_principal,
        "municipio": body.municipio,
        "verificado": True,
        "fuente": "admin_manual",
        "es_gratuito": body.es_gratuito,
        "oculto": body.oculto,
        "hora_confirmada": bool(body.hora_inicio),  # boolean: was a time provided?
    }
    if body.fecha_fin:
        data["fecha_fin"] = body.fecha_fin
    if body.duracion_minutos is not None:
        data["duracion_minutos"] = body.duracion_minutos
    if body.descripcion:
        data["descripcion"] = body.descripcion
    if body.barrio:
        data["barrio"] = body.barrio
    if body.nombre_lugar:
        data["nombre_lugar"] = body.nombre_lugar
    if body.espacio_id:
        data["espacio_id"] = body.espacio_id
    if body.precio:
        data["precio"] = body.precio
    if body.imagen_url:
        data["imagen_url"] = body.imagen_url
    if body.link_externo:
        data["fuente_url"] = body.link_externo

    try:
        res = supabase.table("eventos").insert(data).execute()
    except Exception as exc:
        print(f"[admin/crear ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"Error DB: {type(exc).__name__}: {exc}")
    if not res.data:
        raise HTTPException(status_code=500, detail="Error creando evento — insert sin datos")
    return res.data[0]


@router.patch("/eventos/{evento_id}")
def admin_update_evento(
    evento_id: str,
    body: EventoAdminUpdate,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Partially update an event (any field, including oculto toggle)."""
    _check_key(x_api_key)
    from app.database import supabase

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    # Allow explicitly setting oculto=False
    if body.oculto is not None:
        updates["oculto"] = body.oculto
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    res = supabase.table("eventos").update(updates).eq("id", evento_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return res.data[0]


@router.get("/eventos/manuales")
def admin_get_eventos_manuales(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    page: int = 1,
    per_page: int = 50,
):
    """List manually-uploaded events with their oculto status."""
    _check_key(x_api_key)
    from app.database import supabase
    offset = (max(page, 1) - 1) * per_page
    try:
        res = (
            supabase.table("eventos")
            .select("*", count="exact")
            .eq("fuente", "admin_manual")
            .order("created_at", desc=True)
            .range(offset, offset + per_page - 1)
            .execute()
        )
        return {"data": res.data or [], "total": res.count or 0, "page": page, "per_page": per_page}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"manuales error: {exc}")


@router.delete("/eventos/manuales-pasados")
def admin_delete_manuales_pasados(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Delete all admin_manual events with fecha_inicio in the past (more than 1 day ago)."""
    _check_key(x_api_key)
    from app.database import supabase
    from datetime import datetime, timezone, timedelta
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        res = supabase.table("eventos").delete().eq("fuente", "admin_manual").lt("fecha_inicio", ayer).execute()
        return {"ok": True, "deleted": len(res.data or [])}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")


@router.delete("/eventos/{evento_id}")
def admin_delete_evento(
    evento_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Delete an event by ID."""
    _check_key(x_api_key)
    from app.database import supabase
    res = supabase.table("eventos").delete().eq("id", evento_id).execute()
    return {"ok": True, "deleted": len(res.data or [])}


# ═══════════════════════════════════════════════════════════════
# ML MODEL MONITORING
# ═══════════════════════════════════════════════════════════════

@router.get("/modelo-ia")
def get_modelo_ia(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Return current ML classifier status, metrics and feature importances."""
    _check_key(x_api_key)
    from app.services.ml_classifier import get_model_status
    return get_model_status()


@router.post("/modelo-ia/retrain")
def retrain_modelo_ia(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Retrain the logistic regression classifier from current DB data."""
    _check_key(x_api_key)
    from app.services.ml_classifier import train_classifier
    metrics = train_classifier()
    if "error" in metrics:
        raise HTTPException(status_code=400, detail=metrics["error"])
    return {"ok": True, "metrics": metrics}


@router.post("/modelo-ia/feedback")
def add_ml_feedback(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    titulo: str = Query(...),
    descripcion: str = Query(default=""),
    fuente_url: str = Query(default=""),
    label: bool = Query(..., description="true = es evento, false = no es evento"),
):
    """Add a manually-labelled example to the ML training feedback table."""
    _check_key(x_api_key)
    from app.database import supabase
    res = supabase.table("ml_training_feedback").insert({
        "titulo": titulo[:500],
        "descripcion": descripcion[:1000],
        "fuente_url": fuente_url[:500],
        "label": label,
    }).execute()
    return {"ok": True, "id": (res.data or [{}])[0].get("id")}
