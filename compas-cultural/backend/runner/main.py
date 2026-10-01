"""
Runner local: python -m runner.main [--login] [--ig] [--feed] [--fb] [--limite N] [--dry-run] [--ver]

Se ejecuta desde compas-cultural/backend (los .bat ya lo hacen).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

try:  # .env del backend (SUPABASE_URL, SUPABASE_KEY). Nunca contraseñas de IG/FB.
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except Exception:
    pass

LOG_DIR = Path(__file__).resolve().parent / "logs"


def _log_archivo():
    LOG_DIR.mkdir(exist_ok=True)
    return open(LOG_DIR / f"{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s); st.flush()
            except Exception:
                pass

    def flush(self):
        pass


PRIORIDAD_DEFAULT = "teatro,danza,circo,impro,titeres,colectivo,musica_en_vivo,hip_hop,poesia"


def _prioridad(lugar: dict, claves: list[str]) -> int:
    texto = " ".join(str(lugar.get(k) or "") for k in ("tipo", "categoria_principal", "nombre")).lower()
    return 0 if any(c in texto for c in claves) else 1


def _cargar_lugares(campo: str, limite: int, prioridad: str = "") -> list[dict]:
    from app.database import supabase
    if supabase is None:
        sys.exit("❌ Falta SUPABASE_URL / SUPABASE_KEY en compas-cultural/backend/.env")
    cols = "id,nombre,slug,instagram_handle,facebook,municipio,barrio,lat,lng,categoria_principal,tipo"
    try:
        # Se traen más de los necesarios y se ordenan: primero los prioritarios
        # (teatros y colectivos independientes), luego los menos visitados.
        q = (supabase.table("lugares").select(cols + ",ultimo_scrape_intento")
             .not_.is_(campo, "null").neq("nivel_actividad", "cerrado")
             .order("ultimo_scrape_intento", desc=False, nullsfirst=True).limit(max(limite * 4, limite)))
        filas = q.execute().data or []
        claves = [c.strip() for c in prioridad.split(",") if c.strip()]
        if claves:
            filas.sort(key=lambda l: _prioridad(l, claves))  # sort estable: conserva el orden por antigüedad
        return filas[:limite]
    except Exception:
        return (supabase.table("lugares").select(cols).not_.is_(campo, "null").limit(limite).execute().data or [])


def _marcar_intento(lugar_id: str) -> None:
    from app.database import supabase
    try:
        supabase.table("lugares").update({"ultimo_scrape_intento": datetime.utcnow().isoformat()}).eq("id", lugar_id).execute()
    except Exception:
        pass


def _registrar(fuente: str, stats: dict, segundos: float) -> None:
    from app.database import supabase
    try:
        supabase.table("scraping_log").insert({
            "fuente": fuente, "registros_nuevos": stats.get("publicar", 0) + stats.get("cuarentena", 0),
            "registros_actualizados": stats.get("duplicado", 0), "errores": stats.get("error", 0),
            "detalle": stats, "duracion_segundos": round(segundos, 1),
        }).execute()
    except Exception as exc:
        print(f"⚠ No se pudo registrar en scraping_log: {exc}")


async def login() -> None:
    from runner.browser import PERFIL_DIR, abrir_navegador
    print("Se abrirá un navegador. Inicia sesión TÚ MISMO en Instagram y en Facebook")
    print("(con la cuenta dedicada a Cultura Etérea). Cuando termines, cierra la ventana.")
    print(f"La sesión queda guardada en: {PERFIL_DIR}")
    async with abrir_navegador(headless=False) as ctx:
        p1 = await ctx.new_page()
        await p1.goto("https://www.instagram.com/accounts/login/")
        p2 = await ctx.new_page()
        await p2.goto("https://www.facebook.com/login/")
        while ctx.pages:
            await asyncio.sleep(1)


async def correr(args) -> int:
    from runner import fb, ig, pipeline
    from runner.browser import SesionBloqueada, abrir_navegador, pausa

    total: dict = {}
    t0 = time.time()
    try:
        async with abrir_navegador(headless=not args.ver) as ctx:
            if args.ig or args.feed:
                lugares_ig = _cargar_lugares("instagram_handle", 1000 if args.feed else args.limite, args.prioridad)
                por_handle = {h: l for l in lugares_ig if (h := pipeline.handle_ig(l.get("instagram_handle")))}
                if args.ig:
                    print(f"\n📸 Instagram: {min(len(por_handle), args.limite)} perfiles")
                    for h, lugar in list(por_handle.items())[: args.limite]:
                        print(f"  → @{h} ({lugar['nombre'][:40]})")
                        perfil = await ig.leer_perfil(ctx, h)
                        _marcar_intento(lugar["id"])
                        if perfil:
                            st = pipeline.publicar(pipeline.eventos_desde_perfil_ig(perfil, lugar), args.dry_run)
                            for k, v in st.items():
                                total[k] = total.get(k, 0) + v
                        await pausa(5, 11)
                if args.feed:
                    print("\n📰 Feed propio de Instagram")
                    posts = await ig.leer_feed(ctx, max_posts=args.limite * 3)
                    print(f"  {len(posts)} posts leídos; solo se usan los de lugares/colectivos conocidos")
                    st = pipeline.publicar(pipeline.eventos_desde_feed(posts, por_handle), args.dry_run)
                    for k, v in st.items():
                        total[k] = total.get(k, 0) + v
            if args.fb:
                lugares_fb = _cargar_lugares("facebook", args.limite, args.prioridad)
                print(f"\n📘 Facebook: {len(lugares_fb)} páginas")
                for lugar in lugares_fb:
                    url = pipeline.url_fb(lugar.get("facebook"))
                    if not url:
                        continue
                    print(f"  → {url} ({lugar['nombre'][:40]})")
                    evs = await fb.eventos_de_pagina(ctx, url)
                    st = pipeline.publicar(pipeline.eventos_desde_fb(evs, lugar), args.dry_run)
                    for k, v in st.items():
                        total[k] = total.get(k, 0) + v
                    await pausa(6, 12)
    except SesionBloqueada as exc:
        print(f"\n⛔ {exc}\n   Corrida detenida para proteger la cuenta.")
        total["sesion_bloqueada"] = 1
    print(f"\n✅ Resumen: {total}  ({time.time() - t0:.0f} s)")
    if not args.dry_run:
        _registrar("runner_local", total, time.time() - t0)
    return 2 if total.get("sesion_bloqueada") else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Runner local de Cultura Etérea (Playwright + sesión propia)")
    ap.add_argument("--login", action="store_true", help="Abrir navegador para iniciar sesión (una vez)")
    ap.add_argument("--ig", action="store_true", help="Perfiles de Instagram de lugares/colectivos")
    ap.add_argument("--feed", action="store_true", help="Feed propio de Instagram")
    ap.add_argument("--fb", action="store_true", help="Eventos de páginas de Facebook")
    ap.add_argument("--limite", type=int, default=25, help="Máx. perfiles/páginas por corrida (default 25)")
    ap.add_argument("--dry-run", action="store_true", help="Solo mostrar qué haría, sin escribir")
    ap.add_argument("--ver", action="store_true", help="Mostrar el navegador mientras corre")
    ap.add_argument("--prioridad", default=PRIORIDAD_DEFAULT,
                    help="Tipos/categorías que se visitan primero (coma). Vacío = solo por antigüedad")
    args = ap.parse_args()
    sys.stdout = _Tee(sys.__stdout__, _log_archivo())
    if args.login:
        asyncio.run(login())
        return
    if not (args.ig or args.feed or args.fb):
        args.ig = args.feed = args.fb = True
    sys.exit(asyncio.run(correr(args)))


if __name__ == "__main__":
    main()
