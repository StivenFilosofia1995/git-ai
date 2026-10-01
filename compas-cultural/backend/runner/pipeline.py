"""De lo leído en IG/FB a eventos: extracción determinista + puerta de calidad."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.services.event_gate import evaluar_evento, insertar_evento
from app.services.ig_event_extractor import extract_events_from_ig_profile

CO_TZ = ZoneInfo("America/Bogota")


def handle_ig(raw: Optional[str]) -> Optional[str]:
    """'@casa_x', 'instagram.com/casa_x/', 'https://www.instagram.com/casa_x?igsh=..' → 'casa_x'."""
    if not raw:
        return None
    v = str(raw).strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", v)
    v = m.group(1) if m else v.lstrip("@").split("/")[0].split("?")[0]
    v = re.sub(r"[^A-Za-z0-9._]", "", v)
    return v.lower() if v and v.lower() not in {"p", "reel", "explore", "stories"} else None


def url_fb(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = str(raw).strip()
    if "facebook.com" in v:
        return v.split("?")[0].rstrip("/")
    if re.fullmatch(r"@?[A-Za-z0-9.\-]{3,}", v):
        return f"https://www.facebook.com/{v.lstrip('@')}"
    return None


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:200]


def _completar(ev: dict, lugar: dict, fuente: str) -> dict:
    """Datos del lugar conocido + slug con fecha + fuente."""
    fecha = (ev.get("fecha_inicio") or "")[:10].replace("-", "")
    out = {k: v for k, v in ev.items() if not k.startswith("_")}
    out.update({
        "slug": _slug(f"{ev['titulo']}-{fecha}-{lugar.get('slug') or lugar['id'][:8]}"),
        "espacio_id": lugar["id"],
        "nombre_lugar": lugar.get("nombre"),
        "municipio": lugar.get("municipio"),
        "barrio": lugar.get("barrio"),
        "lat": lugar.get("lat"),
        "lng": lugar.get("lng"),
        "fuente": fuente,
        "verificado": False,
    })
    if "hora_confirmada" not in out:
        out["hora_confirmada"] = bool(ev.get("_hora_detectada"))
    return out


def eventos_desde_perfil_ig(perfil: dict, lugar: dict) -> list[dict]:
    evs = extract_events_from_ig_profile(
        perfil, lugar.get("nombre") or "", lugar.get("categoria_principal") or "otro", lugar.get("municipio") or "medellin")
    out = []
    for ev in evs:
        p = _completar(ev, lugar, "runner_ig")
        permalink = ev.get("_permalink") or ""
        p["fuente_url"] = permalink or f"https://www.instagram.com/{handle_ig(lugar.get('instagram_handle'))}/"
        m = re.search(r"/p/([^/]+)/", permalink)
        if m:
            p["fuente_post_id"] = m.group(1)
        out.append(p)
    return out


def eventos_desde_feed(posts: list[dict], lugares_por_handle: dict[str, dict]) -> list[dict]:
    """Posts del feed propio. Solo se usan los de cuentas que son lugares/colectivos conocidos;
    el resto se descarta (no se publican posts de cuentas personales)."""
    agrupado: dict[str, dict] = {}
    for post in posts:
        lugar = lugares_por_handle.get((post.get("username") or "").lower())
        if not lugar:
            continue
        perfil = agrupado.setdefault(lugar["id"], {"lugar": lugar, "captions": [], "image_urls": [],
                                                   "permalink_urls": [], "timestamps": []})
        perfil["captions"].append(post["caption"]); perfil["image_urls"].append(post["image_url"])
        perfil["permalink_urls"].append(post["permalink"]); perfil["timestamps"].append(post["taken_at"])
    out = []
    for perfil in agrupado.values():
        for ev in eventos_desde_perfil_ig(perfil, perfil["lugar"]):
            ev["fuente"] = "runner_ig_feed"
            out.append(ev)
    return out


def eventos_desde_fb(evs: list[dict], lugar: dict) -> list[dict]:
    out = []
    for ev in evs:
        p = _completar({**ev, "categoria_principal": lugar.get("categoria_principal") or "otro",
                        "categorias": [lugar.get("categoria_principal") or "otro"]}, lugar, "runner_fb")
        out.append(p)
    return out


def publicar(eventos: list[dict], dry_run: bool = False) -> dict:
    """Pasa cada evento por la puerta de calidad. En dry-run solo evalúa, no escribe."""
    from collections import Counter
    stats: Counter = Counter()
    for ev in eventos:
        if dry_run:
            r = evaluar_evento(ev, ahora=datetime.now(CO_TZ))
            stats[r.decision] += 1
            print(f"    [{r.decision:10}] {ev['fecha_inicio'][:16]} {ev['titulo'][:60]}  {','.join(r.motivos[:2])}")
            continue
        try:
            r = insertar_evento(ev)
            stats[r.decision] += 1
            print(f"    [{r.decision:10}] {ev['fecha_inicio'][:16]} {ev['titulo'][:60]}")
        except Exception as exc:
            stats["error"] += 1
            print(f"    [error     ] {ev['titulo'][:60]}: {exc}")
    return dict(stats)
