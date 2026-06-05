"""Push notification endpoints — FCM token registration and send."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class TokenRegistro(BaseModel):
    token: str
    platform: str = "android"
    user_id: str | None = None


@router.post("/registrar-token")
def registrar_token(body: TokenRegistro):
    """Register an FCM device token for push notifications."""
    from app.database import supabase
    try:
        supabase.table("push_tokens").upsert({
            "token": body.token,
            "platform": body.platform,
            "user_id": body.user_id,
        }, on_conflict="token").execute()
        return {"ok": True}
    except Exception as exc:
        print(f"[push] token registration error: {exc}")
        return {"ok": False}


def send_push_notification(title: str, body: str, data: dict | None = None) -> dict:
    """Send push notification to all registered FCM tokens via Firebase HTTP v1 API."""
    import os, json
    import httpx

    server_key = os.environ.get("FCM_SERVER_KEY", "")
    if not server_key:
        print("[push] FCM_SERVER_KEY not set — skipping push")
        return {"sent": 0, "error": "FCM_SERVER_KEY not configured"}

    from app.database import supabase
    try:
        res = supabase.table("push_tokens").select("token").limit(1000).execute()
        tokens = [r["token"] for r in (res.data or [])]
    except Exception as e:
        return {"sent": 0, "error": str(e)}

    if not tokens:
        return {"sent": 0, "message": "no tokens registered"}

    sent = 0
    errors = 0
    # Send in batches of 500 (FCM limit)
    for i in range(0, len(tokens), 500):
        batch = tokens[i:i + 500]
        payload = {
            "registration_ids": batch,
            "notification": {"title": title, "body": body},
            "data": data or {},
            "android": {
                "priority": "high",
                "notification": {
                    "sound": "default",
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                }
            }
        }
        try:
            r = httpx.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={"Authorization": f"key={server_key}", "Content-Type": "application/json"},
                timeout=15,
            )
            result = r.json()
            sent += result.get("success", 0)
            errors += result.get("failure", 0)
        except Exception as e:
            print(f"[push] FCM batch error: {e}")
            errors += len(batch)

    print(f"[push] Sent: {sent}, Errors: {errors}")
    return {"sent": sent, "errors": errors, "total_tokens": len(tokens)}


@router.post("/send-test")
def send_test_notification(
    title: str = "🎭 Cultura ETÉREA",
    body: str = "Hay eventos culturales nuevos hoy en Medellín",
):
    """Admin test: send a push notification to all registered devices."""
    return send_push_notification(title, body)
