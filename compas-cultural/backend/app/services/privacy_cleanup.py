from __future__ import annotations

from datetime import timedelta

from app.config import settings
from app.database import supabase
from app.services.auto_scraper import _now_co


def run_privacy_cleanup() -> dict:
    """Best-effort automatic cleanup of old operational/scraping data.

    Goal: minimize long-term retention of personal or sensitive operational data.
    """
    now = _now_co()
    retention_cutoff = (now - timedelta(days=max(settings.privacy_retention_days, 1))).isoformat()
    ocr_raw_cutoff = (now - timedelta(days=max(settings.privacy_ocr_raw_text_retention_days, 1))).isoformat()

    stats = {
        "solicitudes_eliminadas": 0,
        "scraping_logs_eliminados": 0,
        "ocr_rows_eliminados": 0,
        "ocr_textos_borrados": 0,
        "errores": 0,
    }

    # Remove old registration requests that may contain personal traces.
    try:
        old_req = (
            supabase.table("solicitudes_registro")
            .select("id")
            .lt("created_at", retention_cutoff)
            .limit(5000)
            .execute()
        )
        req_ids = [r["id"] for r in (old_req.data or []) if r.get("id") is not None]
        if req_ids:
            supabase.table("solicitudes_registro").delete().in_("id", req_ids).execute()
            stats["solicitudes_eliminadas"] = len(req_ids)
    except Exception:
        stats["errores"] += 1

    # Remove old scraping logs.
    try:
        old_logs = (
            supabase.table("scraping_log")
            .select("id")
            .lt("ejecutado_en", retention_cutoff)
            .limit(5000)
            .execute()
        )
        log_ids = [r["id"] for r in (old_logs.data or []) if r.get("id") is not None]
        if log_ids:
            supabase.table("scraping_log").delete().in_("id", log_ids).execute()
            stats["scraping_logs_eliminados"] = len(log_ids)
    except Exception:
        stats["errores"] += 1

    # Drop very old OCR runs entirely.
    try:
        old_ocr = (
            supabase.table("event_ocr_runs")
            .select("id")
            .lt("created_at", retention_cutoff)
            .limit(5000)
            .execute()
        )
        ocr_ids = [r["id"] for r in (old_ocr.data or []) if r.get("id") is not None]
        if ocr_ids:
            supabase.table("event_ocr_runs").delete().in_("id", ocr_ids).execute()
            stats["ocr_rows_eliminados"] = len(ocr_ids)
    except Exception:
        stats["errores"] += 1

    # For more recent OCR rows, remove raw extracted text after a short retention window.
    try:
        text_rows = (
            supabase.table("event_ocr_runs")
            .select("id")
            .lt("created_at", ocr_raw_cutoff)
            .not_.is_("raw_text", "null")
            .limit(5000)
            .execute()
        )
        text_ids = [r["id"] for r in (text_rows.data or []) if r.get("id") is not None]
        for row_id in text_ids:
            supabase.table("event_ocr_runs").update({"raw_text": None}).eq("id", row_id).execute()
        stats["ocr_textos_borrados"] = len(text_ids)
    except Exception:
        stats["errores"] += 1

    return stats
