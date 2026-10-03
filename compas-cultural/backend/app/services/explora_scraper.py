"""
Parque Explora, Planetario de Medellín y Exploratorio.

Los tres publican su programación en el mismo CMS (Next.js + Cosmic). La lista pública
`/api/programate/filters` trae solo los eventos de hoy en adelante; el detalle sale de
`/_next/data/{buildId}/es/programate/{slug}.json`. Fecha y hora vienen en hora de Bogotá.

No se publican los shows del domo ni las exhibiciones permanentes (no tienen función con fecha).
Si el texto dice que el evento es en otra sede (EAFIT, Fundadores, "en los barrios"…), entra
en cuarentena para revisarlo: no se le ponen las coordenadas del museo.
"""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from app.database import supabase
from app.services.event_gate import insertar_evento

CO_TZ = ZoneInfo("America/Bogota")
BASE = "https://www.parqueexplora.org"
UA = {"User-Agent": "CulturaEterea/1.0 (+https://www.culturaetereamed.com; agenda cultural)"}

# Coordenadas verificadas en OpenStreetMap (ver seeds/data/coordenadas_verificadas.json)
SEDES = {
    "planetario": {"nombre": "Planetario de Medellín", "lat": 6.2689979, "lng": -75.5661157,
                   "direccion": "Carrera 52 # 71-117", "lugar": ("planetario",)},
    "exploratorio": {"nombre": "Exploratorio (Parque Explora)", "lat": 6.2699271, "lng": -75.5659462,
                     "direccion": "Carrera 52 # 73-75", "lugar": ("exploratorio",)},
    "explora": {"nombre": "Parque Explora", "lat": 6.2707974, "lng": -75.5655578,
                "direccion": "Carrera 52 # 73-75", "lugar": ("parque explora",)},
}
_OTRA_SEDE = re.compile(
    r"\b(eafit|teatro fundadores|estaci[oó]n villa|en los barrios|teatro metropolitano|pablo tob[oó]n)\b", re.I)
_SEDES_EXTERNAS = {
    "teatro fundadores": "Teatro Fundadores (Universidad EAFIT)",
    "estacion villa": "Estación Villa (Metro de Medellín)",
    "teatro metropolitano": "Teatro Metropolitano",
    "pablo tobon": "Teatro Pablo Tobón Uribe",
}


def _norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", _norm(s))).strip("-")[:120]


def _texto(h: Optional[str]) -> str:
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", h or "", flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def parsear_hora(obj: dict) -> Optional[tuple[int, int]]:
    """`time` es HHMM (930 = 9:30) pero a veces vale 0; entonces se lee `hour` ("5:00 p. m.")."""
    t = obj.get("time")
    if isinstance(t, int) and 0 < t < 2400 and t % 100 < 60:
        return t // 100, t % 100
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m", (obj.get("hour") or "").lower())
    if not m:
        return None
    h, mi = int(m.group(1)) % 12, int(m.group(2) or 0)
    return (h + 12 if m.group(3) == "p" else h), mi


def sede_de(obj: dict) -> dict:
    loc = _norm(" ".join(obj.get("location") or []))
    if "planetario" in loc:
        return SEDES["planetario"]
    if "exploratorio" in loc:
        return SEDES["exploratorio"]
    return SEDES["explora"]


def categoria(titulo: str, texto: str) -> str:
    t = _norm(f"{titulo} {texto[:300]}")
    if re.search(r"\b(taller|laboratorio|club|semillero|curso)\b", t):
        return "taller"
    if re.search(r"\b(concierto|sinfonic|musica|musical)\b", t):
        return "musica_en_vivo"
    if re.search(r"\b(cine|pelicula|proyeccion|documental)\b", t):
        return "cine"
    if re.search(r"\b(teatro|obra)\b", t):
        return "teatro"
    if re.search(r"\b(festival|fiesta|feria)\b", t):
        return "festival"
    return "conferencia"


def a_evento(obj: dict, det: Optional[dict] = None) -> Optional[dict]:
    det = det or {}
    titulo = (obj.get("title") or det.get("title") or "").strip()
    fecha = obj.get("date") or det.get("date")
    if not titulo or not fecha:
        return None
    try:
        d = datetime.strptime(fecha[:10], "%Y-%m-%d")
    except ValueError:
        return None
    hm = parsear_hora(obj) or parsear_hora(det)
    ini = datetime(d.year, d.month, d.day, *(hm or (0, 0)), tzinfo=CO_TZ)
    texto = _texto(det.get("content"))
    sede = sede_de(obj)
    gratis = (det.get("price_check") or "").lower().startswith("sin")
    precio = "Gratis" if gratis else "Con costo"
    valor = str(det.get("price") or "").strip()
    if not gratis and valor.isdigit() and int(valor) >= 1000:
        precio = f"${int(valor):,}".replace(",", ".")
    imagen = ((det.get("banner") or {}).get("imgix_url") or obj.get("thumbnail") or "").strip() or None
    slug_src = obj.get("slug") or _slug(titulo)
    url = f"{BASE}/programate/{slug_src}"
    extra = [f"Público: {', '.join(obj['audience'])}" if obj.get("audience") else "",
             f"Modalidad: {obj['modality']}" if obj.get("modality") else "",
             f"Inscripción o entradas: {det['url']}" if det.get("url") else ""]
    desc = " · ".join(x for x in [texto[:1200], *extra] if x)[:1500] or None
    ev = {
        "titulo": titulo[:200],
        "slug": _slug(f"{titulo}-{sede['nombre']}-{fecha[:10]}"),
        "fecha_inicio": ini.isoformat(),
        "fecha_fin": None,
        "hora_confirmada": hm is not None,
        "categoria_principal": categoria(titulo, texto),
        "municipio": "medellin",
        "barrio": "Carabobo Norte",
        "descripcion": desc,
        "imagen_url": imagen,
        "precio": precio,
        "es_gratuito": gratis,
        "fuente": "parque_explora",
        "fuente_url": url,
        "fuente_post_id": slug_src[:120],
        "verificado": True,
    }
    ev["categorias"] = [ev["categoria_principal"]]
    otras = " ".join(_norm(m.group(0)) for m in _OTRA_SEDE.finditer(f"{titulo} {texto}"))
    if otras:
        # El museo organiza, pero el evento es en otra parte: lugar real, sin el pin del museo
        externa = next((v for k, v in _SEDES_EXTERNAS.items() if k in otras), None)
        if externa:
            ev.update({"nombre_lugar": externa, "barrio": None})
        else:
            ev.update({"nombre_lugar": f"{sede['nombre']} (organiza)", "oculto": True,
                       "oculto_motivo": "explora:sede_externa"})
    else:
        ev.update({"nombre_lugar": sede["nombre"], "direccion": sede["direccion"],
                   "lat": sede["lat"], "lng": sede["lng"]})
    return ev


async def _build_id(client: httpx.AsyncClient) -> Optional[str]:
    r = await client.get(f"{BASE}/programate")
    m = re.search(r'"buildId"\s*:\s*"([^"]+)"', r.text)
    return m.group(1) if m else None


async def obtener_eventos() -> tuple[list[dict], dict]:
    diag = {"lista": 0, "detalle_ok": 0, "detalle_error": 0}
    async with httpx.AsyncClient(timeout=30, headers=UA, follow_redirects=True) as client:
        objs: list[dict] = []
        for skip in range(0, 400, 40):
            r = await client.get(f"{BASE}/api/programate/filters", params={"skip": skip})
            if r.status_code != 200:
                break
            lote = (r.json() or {}).get("objects") or []
            objs += lote
            if len(lote) < 40:
                break
        diag["lista"] = len(objs)
        build = await _build_id(client)
        eventos = []
        for o in objs:
            det = None
            if build and o.get("slug"):
                try:
                    rd = await client.get(f"{BASE}/_next/data/{build}/es/programate/{o['slug']}.json")
                    if rd.status_code == 404:
                        build = await _build_id(client)
                        rd = await client.get(f"{BASE}/_next/data/{build}/es/programate/{o['slug']}.json")
                    det = (rd.json().get("pageProps") or {}).get("data") if rd.status_code == 200 else None
                except Exception:
                    det = None
            diag["detalle_ok" if det else "detalle_error"] += 1
            ev = a_evento(o, det if isinstance(det, dict) else None)
            if ev:
                eventos.append(ev)
    return eventos, diag


def _espacio_ids() -> dict[str, str]:
    """Lugar de cada sede (para enlazar el evento con su ficha del mapa)."""
    out = {}
    try:
        lugares = supabase.table("lugares").select("id,nombre,lat").execute().data or []
    except Exception:
        return out
    for clave, s in SEDES.items():
        cands = [l for l in lugares if any(_norm(l.get("nombre")).startswith(p) for p in s["lugar"])]
        cands.sort(key=lambda l: l.get("lat") is None)
        if cands:
            out[s["nombre"]] = cands[0]["id"]
    return out


async def run_explora_scraper() -> dict:
    eventos, diag = await obtener_eventos()
    ids = _espacio_ids()
    stats = {"eventos": len(eventos), "decisiones": {}}
    for ev in eventos:
        if ev.get("nombre_lugar") in ids:
            ev["espacio_id"] = ids[ev["nombre_lugar"]]
        try:
            dec = insertar_evento(ev, upsert=True).decision
        except Exception as exc:
            print(f"[explora] {ev['titulo'][:50]}: {exc}")
            dec = "error"
        stats["decisiones"][dec] = stats["decisiones"].get(dec, 0) + 1
    try:
        supabase.table("scraping_log").insert({
            "fuente": "parque_explora", "registros_nuevos": stats["decisiones"].get("publicar", 0),
            "registros_actualizados": stats["decisiones"].get("duplicado", 0),
            "errores": stats["decisiones"].get("error", 0), "detalle": {**diag, **stats["decisiones"]},
        }).execute()
    except Exception as exc:
        print(f"[explora] log: {exc}")
    print(f"🔭 Parque Explora / Planetario: {stats}")
    return stats
