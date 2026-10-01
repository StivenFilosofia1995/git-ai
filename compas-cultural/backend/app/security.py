"""Verificación centralizada de la clave de administración y de los JWT de usuario."""
from __future__ import annotations

import hmac
import time
from typing import Optional

from fastapi import HTTPException

from app.config import settings

# token -> (user_id, expira_monotonic). Evita llamar a Supabase Auth en cada request.
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}

# Valor que estuvo escrito en el repo público: nunca debe aceptarse.
_LEGACY_PUBLIC_KEYS = {"cultura-eterea-scraper-2026"}


def admin_key_configured() -> bool:
    key = (settings.scraper_api_key or "").strip()
    return bool(key) and key not in _LEGACY_PUBLIC_KEYS


def is_valid_admin_key(provided: Optional[str]) -> bool:
    if not admin_key_configured() or not provided:
        return False
    return hmac.compare_digest(provided.strip(), settings.scraper_api_key.strip())


def require_admin_key(provided: Optional[str]) -> None:
    """Falla cerrado: sin SCRAPER_API_KEY configurada, ningún endpoint admin responde."""
    if not admin_key_configured():
        raise HTTPException(
            status_code=503,
            detail="Admin deshabilitado: configura SCRAPER_API_KEY en el servidor",
        )
    if not is_valid_admin_key(provided):
        raise HTTPException(status_code=403, detail="Invalid API key")


def user_id_from_bearer(authorization: Optional[str]) -> Optional[str]:
    """Devuelve el user id SOLO si el access_token de Supabase es válido.

    La validación la hace Supabase Auth (verifica firma y expiración), así no
    dependemos del JWT secret. Ya no se aceptan UUIDs crudos como token.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if token.count(".") != 2:
        return None
    now = time.monotonic()
    cached = _TOKEN_CACHE.get(token)
    if cached and cached[1] > now:
        return cached[0]
    try:
        from app.database import supabase

        resp = supabase.auth.get_user(token)
        user = getattr(resp, "user", None)
        uid = str(user.id) if user and getattr(user, "id", None) else None
    except Exception:
        uid = None
    if uid:
        if len(_TOKEN_CACHE) > 2000:
            _TOKEN_CACHE.clear()
        _TOKEN_CACHE[token] = (uid, now + 300)
    return uid
