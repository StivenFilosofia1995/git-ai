"""
ig_local.py — Trae la agenda de los bares/espacios desde Instagram usando TU sesión,
en TU computador, y la sube a Cultura ETÉREA.

Por qué local: Instagram bloquea al servidor (IP de datacenter) y sin token de Meta no
hay API. Aquí un Chromium normal (visible) abre Instagram con tu cuenta; tú inicias
sesión a mano la primera vez (el programa nunca ve tu contraseña). Luego visita los
perfiles despacio, captura las últimas publicaciones y las envía al servidor, que
extrae los eventos con las mismas reglas de siempre (ig_precision, sin IA).

Uso:
    python ig_local.py                      # 40 perfiles, los menos visitados primero
    python ig_local.py --max 15             # menos perfiles
    python ig_local.py --solo birra.latina mulenzesalsabar
    python ig_local.py --guardar capturas.json   # solo captura, no sube
    python ig_local.py --subir capturas.json     # solo sube un archivo ya capturado

Configura .env (ver .env.example): SCRAPER_API_KEY=<la de Railway>
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

AQUI = Path(__file__).resolve().parent
load_dotenv(AQUI / ".env")

SERVIDOR = os.getenv("SERVIDOR", "https://www.culturaetereamed.com").rstrip("/")
API_KEY = os.getenv("SCRAPER_API_KEY", "")
PERFIL_NAVEGADOR = AQUI / "perfil_navegador"
ESTADO = AQUI / "visitados.json"
CAPTURAS = AQUI / "capturas"
POSTS_POR_PERFIL = 12
LOTE = 10

SEÑALES_BLOQUEO = ("challenge", "Espera unos minutos", "Try again later", "Inténtalo de nuevo más tarde")
SEÑALES_NO_EXISTE = ("no está disponible", "isn't available", "Esta página no está disponible")


# ── Servidor ──────────────────────────────────────────────────────────────────

def _headers() -> dict:
    if not API_KEY:
        sys.exit("Falta SCRAPER_API_KEY en tools/ig_local/.env (cópiala de Railway → Variables).")
    return {"X-Scraper-Key": API_KEY}


def pedir_handles() -> list[str]:
    r = httpx.get(f"{SERVIDOR}/api/v1/scraper/ig-local/handles", headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json()["handles"]


def subir(perfiles: list[dict]) -> None:
    for i in range(0, len(perfiles), LOTE):
        lote = perfiles[i:i + LOTE]
        r = httpx.post(f"{SERVIDOR}/api/v1/scraper/ig-local", json={"perfiles": lote},
                       headers=_headers(), timeout=600)
        if r.status_code != 200:
            print(f"  ✗ Error subiendo lote ({r.status_code}): {r.text[:200]}")
            continue
        data = r.json()
        print(f"  ⬆ Lote de {len(lote)} perfiles → {data['eventos_nuevos']} eventos nuevos")
        for h, d in data["detalle"].items():
            if d.get("estado") != "ok":
                print(f"     @{h}: {d.get('estado')}")
            elif d.get("nuevos"):
                print(f"     @{h}: +{d['nuevos']} eventos")


# ── Estado de rotación ────────────────────────────────────────────────────────

def _leer_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _marcar_visitado(estado: dict, handle: str) -> None:
    estado[handle] = datetime.now().isoformat(timespec="seconds")
    ESTADO.write_text(json.dumps(estado, indent=1), encoding="utf-8")


# ── Parseo de respuestas de Instagram ─────────────────────────────────────────

def _caption(node: dict) -> str:
    cap = node.get("caption")
    if isinstance(cap, dict):
        return cap.get("text") or ""
    if isinstance(cap, str):
        return cap
    edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
    return (edges[0].get("node") or {}).get("text", "") if edges else ""


def _imagen(node: dict) -> str:
    cands = (node.get("image_versions2") or {}).get("candidates") or []
    if cands:
        return cands[0].get("url") or ""
    return node.get("display_url") or node.get("thumbnail_src") or ""


def _recorrer(obj, posts: dict, info: dict, handle: str) -> None:
    """Busca en cualquier JSON de Instagram nodos de publicación y datos del perfil."""
    if isinstance(obj, dict):
        code = obj.get("code") or obj.get("shortcode")
        ts = obj.get("taken_at") or obj.get("taken_at_timestamp")
        if code and ts and isinstance(code, str):
            texto = _caption(obj)
            if texto and len(texto) > 10 and code not in posts:
                posts[code] = {"caption": texto, "ts": int(ts), "img": _imagen(obj)}
        if str(obj.get("username", "")).lower() == handle and "biography" in obj:
            info["biography"] = obj.get("biography") or ""
            info["external_url"] = obj.get("external_url") or None
        for v in obj.values():
            _recorrer(v, posts, info, handle)
    elif isinstance(obj, list):
        for v in obj:
            _recorrer(v, posts, info, handle)


def _a_perfil(handle: str, posts: dict, info: dict) -> dict:
    ordenados = sorted(posts.items(), key=lambda kv: kv[1]["ts"], reverse=True)[:POSTS_POR_PERFIL]
    return {
        "handle": handle,
        "biography": info.get("biography", ""),
        "external_url": info.get("external_url"),
        "captions": [p["caption"] for _, p in ordenados],
        "image_urls": [p["img"] for _, p in ordenados],
        "permalink_urls": [f"https://www.instagram.com/p/{c}/" for c, _ in ordenados],
        "timestamps": [p["ts"] for _, p in ordenados],
    }


# ── Navegador ─────────────────────────────────────────────────────────────────

def _esperar_sesion(contexto, pagina) -> None:
    pagina.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    if any(c["name"] == "sessionid" for c in contexto.cookies()):
        return
    print("\n👉 Inicia sesión en Instagram en la ventana que se abrió (solo la primera vez).")
    print("   El programa espera hasta 5 minutos y sigue solo cuando entres.\n")
    for _ in range(150):
        time.sleep(2)
        if any(c["name"] == "sessionid" for c in contexto.cookies()):
            print("✓ Sesión iniciada. Queda guardada para las próximas veces.")
            return
    sys.exit("No se detectó inicio de sesión. Vuelve a ejecutar cuando estés listo.")


def capturar(handles: list[str], pausa: tuple[int, int]) -> list[dict]:
    from playwright.sync_api import sync_playwright

    estado = _leer_estado()
    perfiles: list[dict] = []
    with sync_playwright() as pw:
        contexto = pw.chromium.launch_persistent_context(
            str(PERFIL_NAVEGADOR), headless=False, locale="es-CO",
            timezone_id="America/Bogota", viewport={"width": 1200, "height": 900},
        )
        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        _esperar_sesion(contexto, pagina)

        for i, handle in enumerate(handles, 1):
            posts: dict = {}
            info: dict = {}

            def al_responder(resp):
                url = resp.url
                if "instagram.com" not in url or not any(k in url for k in ("graphql", "/api/v1/")):
                    return
                try:
                    texto_resp = resp.text()
                except Exception:
                    return
                texto_resp = texto_resp.removeprefix("for (;;);")
                try:
                    _recorrer(json.loads(texto_resp), posts, info, handle)
                except ValueError:
                    # Algunas respuestas llegan como varios JSON seguidos (streaming), uno por línea
                    for linea in texto_resp.splitlines():
                        try:
                            _recorrer(json.loads(linea), posts, info, handle)
                        except ValueError:
                            continue

            pagina.on("response", al_responder)
            try:
                pagina.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded", timeout=45000)
                for _ in range(10):  # hasta ~10 s esperando las publicaciones
                    if posts:
                        break
                    pagina.wait_for_timeout(1000)
                pagina.mouse.wheel(0, 1200)  # un scroll como haría una persona
                pagina.wait_for_timeout(2500)
                texto = pagina.inner_text("body")[:3000]
            except Exception as e:
                texto = ""
                print(f"[{i}/{len(handles)}] @{handle}: error cargando ({type(e).__name__})")
            finally:
                pagina.remove_listener("response", al_responder)

            if "challenge" in pagina.url or any(s in texto for s in SEÑALES_BLOQUEO):
                print(f"\n⚠ Instagram pidió una pausa. Se detiene aquí para no arriesgar tu cuenta.")
                print("  Vuelve a correrlo mañana; se retoma donde quedó.")
                break
            if any(s in texto for s in SEÑALES_NO_EXISTE):
                print(f"[{i}/{len(handles)}] @{handle}: la cuenta no existe")
            else:
                perfil = _a_perfil(handle, posts, info)
                perfiles.append(perfil)
                print(f"[{i}/{len(handles)}] @{handle}: {len(perfil['captions'])} publicaciones")
            _marcar_visitado(estado, handle)

            if i < len(handles):
                time.sleep(random.uniform(*pausa))

        contexto.close()
    return perfiles


def main() -> None:
    ap = argparse.ArgumentParser(description="Agenda de Instagram → Cultura ETÉREA")
    ap.add_argument("--max", type=int, default=40, help="perfiles por corrida (default 40)")
    ap.add_argument("--solo", nargs="+", help="solo estos handles")
    ap.add_argument("--guardar", help="guardar la captura en este archivo y no subir")
    ap.add_argument("--subir", help="subir un archivo de captura (p.ej. el que te deja Claude)")
    ap.add_argument("--pausa-min", type=int, default=25)
    ap.add_argument("--pausa-max", type=int, default=50)
    a = ap.parse_args()

    if a.subir:
        subir(json.loads(Path(a.subir).read_text(encoding="utf-8"))["perfiles"])
        return

    if a.solo:
        handles = [h.lstrip("@").lower() for h in a.solo]
    else:
        estado = _leer_estado()
        todos = pedir_handles()
        # Prioridad del servidor, pero los nunca visitados / visitados hace más tiempo primero
        handles = sorted(todos, key=lambda h: (h in estado, estado.get(h, "")))[: a.max]
    print(f"Visitando {len(handles)} perfiles (pausa {a.pausa_min}-{a.pausa_max}s entre cada uno)…")

    perfiles = capturar(handles, (a.pausa_min, a.pausa_max))

    CAPTURAS.mkdir(exist_ok=True)
    archivo = Path(a.guardar) if a.guardar else CAPTURAS / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    archivo.write_text(json.dumps({"perfiles": perfiles}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nCaptura guardada en {archivo}")

    if not a.guardar and perfiles:
        subir(perfiles)


if __name__ == "__main__":
    main()
