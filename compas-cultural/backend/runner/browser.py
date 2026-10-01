"""Navegador con perfil persistente: la sesión de IG/FB la inicia el usuario una sola vez."""
from __future__ import annotations

import asyncio
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path

PERFIL_DIR = Path(os.getenv("ETEREA_PERFIL_DIR") or Path(os.getenv("LOCALAPPDATA", Path.home())) / "CulturaEterea" / "pw-profile")


class SesionBloqueada(RuntimeError):
    """Instagram/Facebook pidió login o verificación (checkpoint): se detiene la corrida."""


async def pausa(min_s: float = 3.0, max_s: float = 8.0) -> None:
    """Ritmo humano entre acciones (evita bloqueos de la cuenta)."""
    await asyncio.sleep(random.uniform(min_s, max_s))


@asynccontextmanager
async def abrir_navegador(headless: bool = True):
    from playwright.async_api import async_playwright

    PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PERFIL_DIR),
            headless=headless,
            locale="es-CO",
            timezone_id="America/Bogota",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            yield ctx
        finally:
            await ctx.close()


def verificar_sesion(url: str, red: str) -> None:
    u = url.lower()
    if red == "ig" and ("/accounts/login" in u or "/challenge" in u or "/checkpoint" in u):
        raise SesionBloqueada("Instagram pide iniciar sesión o verificación. Ejecuta login_primera_vez.bat")
    if red == "fb" and ("/login" in u or "checkpoint" in u):
        raise SesionBloqueada("Facebook pide iniciar sesión o verificación. Ejecuta login_primera_vez.bat")
