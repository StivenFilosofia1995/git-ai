from datetime import datetime, timedelta

from fastapi import APIRouter
from app.database import supabase

router = APIRouter()

# Track startup time and last scraper run for /status
_startup_time = datetime.utcnow()


@router.get("/")
async def health_check():
    from app.config import settings
    return {
        "status": "healthy",
        "service": "compas-cultural-api",
        "groq_configured": bool(settings.groq_api_key),
        "supabase_configured": bool(settings.supabase_url),
        "chat_engine": "groq-llama-3.1-8b-instant",
        "version": "9e1bb43",
    }


@router.get("/stats")
def get_stats():
    """Real-time counts for espacios, eventos, zonas."""
    try:
        espacios = supabase.table("lugares").select("id", count="exact").execute()
        eventos = supabase.table("eventos").select("id", count="exact").execute()
        zonas = supabase.table("zonas_culturales").select("id", count="exact").execute()
        return {
            "espacios": espacios.count or len(espacios.data),
            "eventos": eventos.count or len(eventos.data),
            "zonas": zonas.count or len(zonas.data),
        }
    except Exception:
        return {"espacios": 0, "eventos": 0, "zonas": 0}


@router.get("/status")
async def scraper_status():
    """
    Scraper system status — útil para monitorear desde Railway dashboard.
    Devuelve: estado del scraper, últimos logs, eventos hoy, token Meta.
    """
    import os
    now_co = datetime.utcnow() - timedelta(hours=5)
    uptime_seconds = int((datetime.utcnow() - _startup_time).total_seconds())

    status = {
        "service": "compas-cultural-api",
        "env": os.getenv("APP_ENV", "production"),
        "uptime_seconds": uptime_seconds,
        "disable_scraper": os.getenv("DISABLE_SCRAPER", "false").lower() in ("true", "1", "yes"),
        "now_colombia": now_co.isoformat(),
        "db": "ok",
        "eventos_totales": 0,
        "eventos_hoy": 0,
        "lugares_totales": 0,
        "last_scraping_logs": [],
        "meta_token": "unknown",
    }

    try:
        ev_resp = supabase.table("eventos").select("id", count="exact").execute()
        status["eventos_totales"] = ev_resp.count or len(ev_resp.data or [])

        today_start = now_co.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_end = now_co.replace(hour=23, minute=59, second=59).isoformat()
        ev_hoy = supabase.table("eventos").select("id", count="exact").gte(
            "fecha_inicio", today_start
        ).lte("fecha_inicio", today_end).execute()
        status["eventos_hoy"] = ev_hoy.count or len(ev_hoy.data or [])

        lug_resp = supabase.table("lugares").select("id", count="exact").execute()
        status["lugares_totales"] = lug_resp.count or len(lug_resp.data or [])

        logs_resp = supabase.table("scraping_log").select(
            "fuente,registros_nuevos,errores,ejecutado_en"
        ).order("ejecutado_en", desc=True).limit(5).execute()
        status["last_scraping_logs"] = logs_resp.data or []

    except Exception as e:
        status["db"] = f"error: {str(e)[:100]}"

    try:
        token_resp = supabase.table("config_kv").select(
            "value,expires_at,updated_at"
        ).eq("key", "meta_access_token").execute()
        if token_resp.data:
            row = token_resp.data[0]
            expires_at = row.get("expires_at")
            if expires_at:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", ""))
                days_left = (exp_dt - datetime.utcnow()).days
                status["meta_token"] = f"valid ({days_left}d left)" if days_left > 0 else "expired"
            else:
                status["meta_token"] = "present (no expiry set)"
        else:
            status["meta_token"] = "not set"
    except Exception:
        status["meta_token"] = "unknown"

    return status