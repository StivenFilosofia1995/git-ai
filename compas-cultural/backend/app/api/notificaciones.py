"""Push notification endpoints — FCM (Android) + Web Push VAPID (iPhone PWA)."""
from __future__ import annotations
import os, json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:autonomycsia@gmail.com"}


class TokenRegistro(BaseModel):
    token: str
    platform: str = "android"  # android | web
    user_id: str | None = None


class WebPushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {p256dh, auth}
    user_id: str | None = None


@router.get("/vapid-public-key")
def get_vapid_public_key():
    """Return VAPID public key for web push subscription."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="VAPID keys not configured")
    return {"publicKey": VAPID_PUBLIC_KEY}


@router.post("/registrar-token")
def registrar_token(body: TokenRegistro):
    """Register FCM device token (Android app)."""
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


@router.post("/registrar-web-push")
def registrar_web_push(body: WebPushSubscription):
    """Register Web Push subscription (iPhone PWA + Chrome/Firefox)."""
    from app.database import supabase
    try:
        supabase.table("web_push_subscriptions").upsert({
            "endpoint": body.endpoint,
            "keys": json.dumps(body.keys),
            "user_id": body.user_id,
        }, on_conflict="endpoint").execute()
        return {"ok": True}
    except Exception as exc:
        print(f"[web-push] subscription error: {exc}")
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


def send_web_push_notification(title: str, body: str, url: str = "/") -> dict:
    """Send Web Push to all subscribed browsers/PWAs (iPhone included)."""
    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
        return {"sent": 0, "error": "VAPID keys not configured"}
    try:
        from pywebpush import webpush, WebPushException
        from app.database import supabase
        res = supabase.table("web_push_subscriptions").select("endpoint,keys").limit(1000).execute()
        subs = res.data or []
    except Exception as e:
        return {"sent": 0, "error": str(e)}

    sent = errors = 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    for sub in subs:
        try:
            keys = json.loads(sub["keys"]) if isinstance(sub["keys"], str) else sub["keys"]
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": keys},
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
        except WebPushException as e:
            if "410" in str(e) or "404" in str(e):
                # Expired subscription — remove it
                try:
                    from app.database import supabase as _sb
                    _sb.table("web_push_subscriptions").delete().eq("endpoint", sub["endpoint"]).execute()
                except Exception:
                    pass
            errors += 1
        except Exception:
            errors += 1

    print(f"[web-push] Sent: {sent}, Errors: {errors}")
    return {"sent": sent, "errors": errors}


@router.post("/send-test")
def send_test_notification(
    title: str = "🎭 Cultura ETÉREA",
    body: str = "Hay eventos culturales nuevos hoy en Medellín",
):
    """Admin test: send push to ALL platforms (Android FCM + iPhone Web Push)."""
    fcm = send_push_notification(title, body)
    web = send_web_push_notification(title, body)
    return {"fcm": fcm, "web_push": web}
