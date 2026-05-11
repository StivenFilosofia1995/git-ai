from fastapi import APIRouter, HTTPException, Query
from typing import Annotated

router = APIRouter()


@router.post("/blast-now")
def trigger_blast_now(api_key: Annotated[str, Query()] = ""):
    """Sends one email to the next unsent user in the blast campaign."""
    from app.config import settings
    if api_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="Unauthorized")
    from app.services.email_service import send_blast_campaign_tick
    stats = send_blast_campaign_tick()
    return stats


@router.get("/blast-status")
def get_blast_status():
    """Returns cursor position and recipient count for the blast campaign."""
    from app.services.email_service import (
        _load_auth_users, _load_profile_recipients, _load_place_recipients,
        _append_recipient, _kv_get,
    )
    BLAST_KEY = "blast:2026-05"
    cursor = _kv_get(f"cursor:{BLAST_KEY}") or "0"

    recipients: list[dict] = []
    seen: set[str] = set()
    for r in _load_auth_users(500):
        _append_recipient(recipients, seen, r)
    for r in _load_profile_recipients(300):
        _append_recipient(recipients, seen, r)
    for r in _load_place_recipients(200):
        _append_recipient(recipients, seen, r)

    return {
        "blast_key": BLAST_KEY,
        "cursor": int(cursor),
        "total_recipients": len(recipients),
    }
