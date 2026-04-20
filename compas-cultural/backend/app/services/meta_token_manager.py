"""
Meta Graph API Token Manager.
Automatically renews the access token before it expires.
Stores tokens in Supabase for persistence across deploys.
"""
import httpx
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.database import supabase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


META_GRAPH_URL = "https://graph.facebook.com/v21.0"


async def get_valid_token() -> str | None:
    """Get a valid Meta access token. Checks DB first, then env, auto-renews if needed."""
    # 1. Check DB for stored token
    try:
        resp = supabase.table("config_kv").select("*").eq("key", "meta_access_token").single().execute()
        if resp.data:
            token = resp.data["value"]
            expires_at = resp.data.get("expires_at")
            if expires_at:
                exp = datetime.fromisoformat(expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                # If token expires in less than 7 days, renew it
                if exp > _utcnow() + timedelta(days=7):
                    return token
                else:
                    print("[META] Token expires soon, renewing...")
                    new_token = await _exchange_token(token)
                    if new_token:
                        return new_token
                    # If renewal fails, use the old one if still valid
                    if exp > _utcnow():
                        return token
    except Exception as e:
        # Table might not exist yet — fall through to env token
        if "config_kv" in str(e):
            await _ensure_config_table()
        else:
            print(f"[META] DB token check failed: {e}")

    # 2. Fall back to env token
    env_token = settings.meta_access_token
    if env_token:
        # Try to exchange for long-lived token and store it
        new_token = await _exchange_token(env_token)
        if new_token:
            return new_token
        return env_token

    return None


async def _exchange_token(current_token: str) -> str | None:
    """Exchange a token for a long-lived token (60 days). Store in DB."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # First check token validity and expiry
            debug_resp = await client.get(
                f"{META_GRAPH_URL}/debug_token",
                params={
                    "input_token": current_token,
                    "access_token": current_token,
                }
            )
            if debug_resp.status_code == 200:
                token_data = debug_resp.json().get("data", {})
                expires_at = token_data.get("expires_at", 0)
                if expires_at == 0:
                    # Token never expires (system user token) — just store it
                    await _store_token(current_token, None)
                    return current_token

            # Exchange for long-lived token
            resp = await client.get(
                f"{META_GRAPH_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.meta_app_id,
                    "client_secret": settings.meta_app_secret,
                    "fb_exchange_token": current_token,
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get("access_token")
                expires_in = data.get("expires_in", 5184000)  # default 60 days
                if new_token:
                    expires_at_dt = _utcnow() + timedelta(seconds=expires_in)
                    await _store_token(new_token, expires_at_dt)
                    print(f"[META] Token renewed, expires: {expires_at_dt.isoformat()}")
                    return new_token
            else:
                # Token exchange failed — the current token might still work
                # Store it anyway so we have it in DB
                await _store_token(current_token, _utcnow() + timedelta(days=30))
                print(f"[META] Token exchange failed ({resp.status_code}), using current token")
    except Exception as e:
        print(f"[META] Token exchange error: {e}")

    return None


async def _store_token(token: str, expires_at: datetime | None):
    """Store token in Supabase config_kv table."""
    try:
        row = {
            "key": "meta_access_token",
            "value": token,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "updated_at": _utcnow().isoformat(),
        }
        # Upsert: insert or update
        supabase.table("config_kv").upsert(row, on_conflict="key").execute()
    except Exception as e:
        print(f"[META] Failed to store token: {e}")


async def _ensure_config_table():
    """Create config_kv table if it doesn't exist."""
    try:
        supabase.rpc("exec_sql", {
            "sql": """
                CREATE TABLE IF NOT EXISTS config_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """
        }).execute()
    except Exception as e:
        print(f"[META] Could not create config_kv table: {e}")


async def check_token_health() -> dict:
    """Check if the Meta token is valid and return its status."""
    token = await get_valid_token()
    if not token:
        return {"status": "no_token", "message": "No Meta access token configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{META_GRAPH_URL}/debug_token",
                params={"input_token": token, "access_token": token}
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                is_valid = data.get("is_valid", False)
                expires_at = data.get("expires_at", 0)
                scopes = data.get("scopes", [])
                return {
                    "status": "valid" if is_valid else "invalid",
                    "expires_at": datetime.fromtimestamp(expires_at).isoformat() if expires_at else "never",
                    "scopes": scopes,
                }
            return {"status": "error", "message": f"API returned {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
