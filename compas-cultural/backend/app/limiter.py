# -*- coding: utf-8 -*-
"""
Singleton del rate limiter (slowapi).
Importar desde aquí en main.py y en los routers que lo necesiten.
"""
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_ENABLED = True
except ImportError:
    limiter = None  # type: ignore[assignment]
    RATE_LIMIT_ENABLED = False


def rate_limit(rule: str):
    """
    Decorador de tasa que aplica slowapi si está disponible.
    Si slowapi no está instalado, devuelve la función sin cambios.

    Uso:
        @router.post("/")
        @rate_limit("10/minute")
        async def mi_endpoint(request: Request, ...):

    Nota:
        slowapi inspecciona la firma y exige un argumento llamado exactamente
        `request` o `websocket`.
    """
    if limiter is not None:
        return limiter.limit(rule)
    return lambda f: f
