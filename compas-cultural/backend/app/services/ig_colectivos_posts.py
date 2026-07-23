# -*- coding: utf-8 -*-
"""
IG Colectivos Posts Scraper
Visita perfiles de Instagram de colectivos culturales (logueado),
captura posts recientes con imagen y extrae eventos usando Claude Haiku Vision.

SEGURIDAD: Las credenciales solo se usan en memoria, NUNCA se almacenan.
"""
from __future__ import annotations

import base64
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

CO_TZ = ZoneInfo("America/Bogota")

_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1"
)

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['es-CO', 'es', 'en']});
"""


# ─── Job store ────────────────────────────────────────────────────────────────

def _job_update(job_id: str, data: dict) -> None:
    if not job_id:
        return
    try:
        from app.database import supabase
        supabase.table("config_kv").upsert(
            {"key": f"ig_col_job:{job_id}", "value": json.dumps(data)},
            on_conflict="key",
        ).execute()
    except Exception:
        pass


def get_job_status(job_id: str) -> Optional[dict]:
    try:
        from app.database import supabase
        res = supabase.table("config_kv").select("value").eq("key", f"ig_col_job:{job_id}").execute()
        if res.data:
            return json.loads(res.data[0]["value"])
    except Exception:
        pass
    return None


# ─── Claude Haiku Vision — extrae evento de imagen ───────────────────────────

async def _extract_event_from_image(image_bytes: bytes, caption: str, handle: str) -> Optional[dict]:
    try:
        import anthropic
        from app.config import settings

        b64 = base64.standard_b64encode(image_bytes).decode()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        now_co = datetime.now(CO_TZ)
        prompt = f"""Analiza esta imagen de Instagram del colectivo cultural @{handle} y determina si es un afiche de evento cultural.
Caption del post: "{caption[:300]}"
Fecha actual: {now_co.strftime('%Y-%m-%d')}

Si ES un afiche de evento, extrae en JSON con estas claves exactas:
{{
  "es_evento": true,
  "titulo": "nombre del evento",
  "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
  "hora_inicio": "HH:MM o null",
  "hora_fin": "HH:MM o null",
  "nombre_lugar": "lugar o null",
  "municipio": "ciudad (default Medellín)",
  "barrio": "barrio o null",
  "categoria_principal": "teatro|hip_hop|jazz|galeria|arte_contemporaneo|electronica|danza|musica_en_vivo|literatura|festival|cine|fotografia|filosofia|taller|circo|conferencia|otro",
  "descripcion": "descripción breve (1-2 frases) o null",
  "precio": "precio en texto o null",
  "es_gratuito": true/false,
  "ig_usuario": "@{handle}"
}}

Si NO es un afiche de evento (foto de archivo, meme, repost, etc.): {{"es_evento": false}}

Responde SOLO el JSON, sin texto adicional."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        if not data.get("es_evento"):
            return None

        # Validate the date is in the future
        fecha_str = data.get("fecha_inicio", "")
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                if fecha.replace(tzinfo=CO_TZ) < now_co - timedelta(days=1):
                    return None  # pasado
            except Exception:
                pass

        return data
    except Exception as e:
        print(f"  [IG Posts] Error extrayendo evento de imagen: {e}")
        return None


# ─── Profile scraper ──────────────────────────────────────────────────────────

async def scan_ig_colectivo_profiles(
    email: str,
    password: str,
    handles: list[str],
    max_posts_per_profile: int = 12,
    job_id: str = "",
) -> dict:
    """
    Inicia sesión en Instagram y visita los perfiles de los colectivos dados.
    Extrae posts con imágenes, los analiza con Claude Haiku Vision y devuelve eventos.

    Credenciales SOLO en memoria, NO se almacenan.
    """
    _job_update(job_id, {
        "status": "iniciando",
        "progress": 5,
        "profiles_done": 0,
        "profiles_total": len(handles),
        "events": [],
        "error": None,
    })

    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        err = "Playwright no instalado en este servidor"
        _job_update(job_id, {"status": "error", "error": err, "events": []})
        return {"status": "error", "error": err, "events": []}

    import httpx
    events: list[dict] = []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage", "--disable-extensions",
                    "--disable-setuid-sandbox", "--single-process", "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=_UA_MOBILE,
                viewport={"width": 390, "height": 844},
                locale="es-CO",
                timezone_id="America/Bogota",
            )
            await context.add_init_script(_STEALTH_SCRIPT)
            page = await context.new_page()

            # ── Login ───────────────────────────────────────────────────────
            _job_update(job_id, {"status": "iniciando_sesion", "progress": 15,
                                  "profiles_done": 0, "profiles_total": len(handles)})
            try:
                await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30_000)
            except PWTimeout:
                pass
            await page.wait_for_timeout(2000)

            try:
                user_input = await page.wait_for_selector('input[name="username"]', timeout=12_000)
                await user_input.click()
                await page.wait_for_timeout(400)
                await page.type('input[name="username"]', email, delay=90)
                await page.wait_for_timeout(400)
                await page.type('input[name="password"]', password, delay=90)
                await page.wait_for_timeout(600)
                await page.click('button[type="submit"]')
            except PWTimeout:
                await browser.close()
                err = "No se encontró el formulario de login de Instagram"
                _job_update(job_id, {"status": "error", "error": err, "events": []})
                return {"status": "error", "error": err, "events": []}

            try:
                await page.wait_for_load_state("networkidle", timeout=25_000)
            except PWTimeout:
                pass
            await page.wait_for_timeout(3000)

            # Verificar login exitoso
            current_url = page.url
            if "login" in current_url or "challenge" in current_url:
                await browser.close()
                err = "Login fallido — verificá usuario/contraseña o desafío de seguridad"
                _job_update(job_id, {"status": "error", "error": err, "events": []})
                return {"status": "error", "error": err, "events": []}

            # Obtener cookies para requests directos a la API
            cookies = await context.cookies()
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            csrf_token = next((c["value"] for c in cookies if c["name"] == "csrftoken"), "")

            # ── Visitar cada perfil ──────────────────────────────────────────
            _job_update(job_id, {"status": "escaneando_perfiles", "progress": 30,
                                  "profiles_done": 0, "profiles_total": len(handles), "events": []})

            for i, handle in enumerate(handles):
                handle_clean = handle.lstrip("@").strip()
                progress = 30 + int(65 * i / max(len(handles), 1))
                _job_update(job_id, {
                    "status": "escaneando_perfiles",
                    "progress": progress,
                    "current_profile": f"@{handle_clean}",
                    "profiles_done": i,
                    "profiles_total": len(handles),
                    "events": events,
                })

                # Interceptar respuesta de la API de perfil
                profile_data: list[dict] = []

                async def on_response(response):
                    url = response.url
                    if "web_profile_info" in url or ("api/v1/feed/user" in url and handle_clean in url):
                        try:
                            data = await response.json()
                            profile_data.append(data)
                        except Exception:
                            pass

                page.on("response", on_response)

                try:
                    await page.goto(
                        f"https://www.instagram.com/{handle_clean}/",
                        wait_until="domcontentloaded",
                        timeout=20_000,
                    )
                except PWTimeout:
                    pass
                await page.wait_for_timeout(3000)

                page.remove_listener("response", on_response)

                # Extraer posts de la respuesta interceptada
                post_images: list[tuple[str, str]] = []  # (image_url, caption)

                for pdata in profile_data:
                    try:
                        user = (pdata.get("data") or {}).get("user") or {}
                        edges = (user.get("edge_owner_to_timeline_media") or {}).get("edges") or []
                        for edge in edges[:max_posts_per_profile]:
                            node = edge.get("node") or {}
                            if node.get("__typename") == "GraphVideo":
                                continue
                            img_url = node.get("display_url") or node.get("thumbnail_src") or ""
                            caption_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
                            caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""
                            if img_url:
                                post_images.append((img_url, caption))
                    except Exception:
                        pass

                # Descargar imágenes y analizarlas con Claude Haiku
                async with httpx.AsyncClient(timeout=15) as http:
                    for img_url, caption in post_images[:max_posts_per_profile]:
                        try:
                            img_resp = await http.get(img_url, headers={"User-Agent": _UA_MOBILE})
                            if img_resp.status_code != 200:
                                continue
                            event_data = await _extract_event_from_image(
                                img_resp.content, caption, handle_clean
                            )
                            if event_data:
                                event_data["fuente_url"] = f"https://instagram.com/{handle_clean}"
                                events.append(event_data)
                        except Exception as e:
                            print(f"  [IG Posts] Error procesando imagen de @{handle_clean}: {e}")

                await page.wait_for_timeout(2000)  # Pausa entre perfiles

            await browser.close()

    except Exception as e:
        _job_update(job_id, {"status": "error", "error": str(e), "events": events})
        return {"status": "error", "error": str(e), "events": events}

    _job_update(job_id, {
        "status": "done",
        "progress": 100,
        "profiles_done": len(handles),
        "profiles_total": len(handles),
        "events_count": len(events),
        "events": events,
    })
    return {"status": "done", "events": events, "profiles_scanned": len(handles)}


def get_stored_handles(limit: int = 50) -> list[str]:
    """Lee handles de colectivos almacenados en la BD (tabla espacios o lugares)."""
    handles: list[str] = []
    try:
        from app.database import supabase
        # Intenta desde tabla espacios con campo instagram_handle
        res = (
            supabase.table("espacios")
            .select("instagram_handle")
            .not_.is_("instagram_handle", "null")
            .limit(limit)
            .execute()
        )
        handles = [r["instagram_handle"].lstrip("@") for r in (res.data or []) if r.get("instagram_handle")]
    except Exception:
        pass

    if not handles:
        # Fallback: seed list del discovery
        from app.services.ig_colectivos_discovery import _SEED_HANDLES
        handles = list(_SEED_HANDLES)[:limit]

    return handles
