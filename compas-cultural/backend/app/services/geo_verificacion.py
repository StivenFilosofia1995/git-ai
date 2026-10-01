"""
geo_verificacion.py
===================
Verificación determinista de coordenadas de `lugares` contra OpenStreetMap (Nominatim).

Por qué existe: en la auditoría de 2026-10 solo ~27 % de los lugares tenía
coordenadas, y muchas eran de relleno (11 lugares en el mismo centro de Medellín,
grupos de galerías distintas con el mismo punto). "Cerca de mí" y el mapa
dependen de estas coordenadas.

Reglas (iguales a las de la verificación manual inicial):
- Se busca "<nombre>, <municipio>, Antioquia" y luego "<nombre>, Antioquia",
  limitado a la caja del Valle de Aburrá.
- Un resultado cuenta solo si NO es una zona administrativa (ciudad/barrio) y
  su nombre comparte ≥ 60 % de los tokens significativos con el del lugar.
- ok:          coordenada actual a ≤ 250 m del resultado → se marca verificada.
- corregir:    a > 250 m → se reemplaza por la de OSM.
- nuevo:       el lugar no tenía coordenadas → se completan.
- placeholder: la coordenada es un relleno conocido y OSM no encontró nada → se borra
               (mejor sin punto que un punto falso).
- sin_verificar: no se toca.

Política de uso de Nominatim: máx. 1 petición/s, User-Agent identificable,
lotes pequeños. Por eso corre en lotes (por defecto 40 lugares por ejecución).
"""
from __future__ import annotations

import asyncio
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.database import supabase

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "CulturaEterea/1.0 (+https://www.culturaetereamed.com; verificacion de espacios culturales)"
VIEWBOX = "-75.75,6.55,-75.25,5.95"  # Valle de Aburrá (lon_min, lat_max, lon_max, lat_min)

MUNICIPIOS = {
    "medellin": "Medellín", "envigado": "Envigado", "itagui": "Itagüí", "bello": "Bello",
    "sabaneta": "Sabaneta", "la_estrella": "La Estrella", "caldas": "Caldas",
    "copacabana": "Copacabana", "girardota": "Girardota", "barbosa": "Barbosa",
}
STOPWORDS = {"de", "del", "la", "el", "los", "las", "y", "en", "medellin", "casa", "centro",
             "cultural", "cultura", "sede", "the"}
TIPOS_ZONA = {"administrative", "city", "town", "suburb", "neighbourhood", "quarter",
              "residential", "county", "state"}
# Rellenos detectados: centro de Medellín usado por defecto en scrapers/seeds
PLACEHOLDERS = [(6.2442, -75.5812), (6.2476, -75.5658), (6.2518, -75.5636)]
UMBRAL_OK_M = 250
UMBRAL_MATCH = 0.75


def _norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _tokens(s: Optional[str]) -> set[str]:
    return {t for t in _norm(s).split() if len(t) > 2 and t not in STOPWORDS}


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p = math.radians
    x = (math.sin(p(lat2 - lat1) / 2) ** 2
         + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(p(lng2 - lng1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(x))


def es_placeholder(lat: Optional[float], lng: Optional[float]) -> bool:
    if lat is None or lng is None:
        return False
    return any(distancia_m(lat, lng, a, b) < 60 for a, b in PLACEHOLDERS)


def _municipio_osm(res: dict) -> str:
    addr = res.get("address") or {}
    texto = " ".join(str(addr.get(k, "")) for k in ("city", "town", "village", "municipality", "county"))
    texto = _norm(texto or res.get("display_name"))
    for key, nombre in MUNICIPIOS.items():
        if _norm(nombre) in texto:
            return key
    return ""


_VIA_RE = re.compile(
    r"\b(calle|cll|cl|carrera|cra|kra|kr|cr|avenida calle|avenida carrera|diagonal|dg|transversal|tv)\.?\s*(\d{1,3})"
)
_EJE = {"calle": "calle", "cll": "calle", "cl": "calle", "avenida calle": "calle", "diagonal": "calle", "dg": "calle",
        "carrera": "carrera", "cra": "carrera", "kra": "carrera", "kr": "carrera", "cr": "carrera",
        "avenida carrera": "carrera", "transversal": "carrera", "tv": "carrera"}


def ejes_direccion(direccion: Optional[str]) -> dict[str, int]:
    """'Calle 44 #39-100' → {'calle': 44, 'carrera': 39} (cuadrícula de Medellín)."""
    # Sin tildes, pero conservando "#" y "-" (los quita _norm)
    d = unicodedata.normalize("NFD", (direccion or "").lower()).encode("ascii", "ignore").decode()
    out: dict[str, int] = {}
    m = _VIA_RE.search(d)
    if not m:
        return out
    eje = _EJE[m.group(1)]
    out[eje] = int(m.group(2))
    cruce = re.search(r"(?:#|no\.?|n°|numero)\s*(\d{1,3})", d[m.end():])
    if cruce:
        out["carrera" if eje == "calle" else "calle"] = int(cruce.group(1))
    return out


def direccion_compatible(direccion: Optional[str], res: dict) -> bool:
    """Si conocemos la dirección y OSM dice en qué vía está, deben estar en la misma zona (±12)."""
    ejes = ejes_direccion(direccion)
    road = (res.get("address") or {}).get("road")
    osm = ejes_direccion(road)
    if not ejes or not osm:
        return True  # sin información suficiente: no se descarta por esto
    for eje, n in osm.items():
        if eje in ejes and abs(ejes[eje] - n) > 12:
            return False
    return True


def elegir_resultado(nombre: str, resultados: list[dict], municipio: Optional[str] = None,
                     direccion: Optional[str] = None) -> Optional[dict]:
    """Resultado de Nominatim que sea un lugar (no una zona) y cuyo nombre coincida, SIN ambigüedad.

    - Ambigüedad: si varios candidatos válidos están a > 300 m entre sí (p. ej. la sede y
      las filiales de una biblioteca con el mismo nombre) no se elige ninguno.
    - Municipio: si OSM informa municipio y no coincide con el del lugar, se descarta.
    """
    toks = _tokens(nombre)
    if not toks:
        return None
    mun = _norm(municipio).replace(" ", "_") if municipio else ""
    candidatos = []
    for res in resultados:
        if res.get("type") in TIPOS_ZONA or res.get("addresstype") in TIPOS_ZONA:
            continue
        rn = _tokens(res.get("name") or (res.get("display_name") or "").split(",")[0])
        if not rn:
            continue
        overlap = len(toks & rn) / max(1, min(len(toks), len(rn)))
        if overlap < UMBRAL_MATCH:
            continue
        mun_osm = _municipio_osm(res)
        if mun and mun_osm and mun_osm != mun:
            continue
        if not direccion_compatible(direccion, res):
            continue
        candidatos.append((overlap, res))
    if not candidatos:
        return None
    lat0, lng0 = float(candidatos[0][1]["lat"]), float(candidatos[0][1]["lon"])
    if any(distancia_m(lat0, lng0, float(r["lat"]), float(r["lon"])) > 300 for _, r in candidatos[1:]):
        return None  # ambiguo
    overlap, res = max(candidatos, key=lambda c: c[0])
    return {
        "lat": float(res["lat"]), "lng": float(res["lon"]),
        "osm": f"{res.get('osm_type')}/{res.get('osm_id')}",
        "osm_nombre": res.get("name"), "overlap": round(overlap, 2),
    }


def clasificar(actual: Optional[tuple[float, float]], match: Optional[dict]) -> tuple[str, Optional[int]]:
    if match and actual:
        d = round(distancia_m(actual[0], actual[1], match["lat"], match["lng"]))
        return ("ok" if d <= UMBRAL_OK_M else "corregir"), d
    if match:
        return "nuevo", None
    if actual and es_placeholder(*actual):
        return "placeholder", None
    return "sin_verificar", None


async def _buscar(client: httpx.AsyncClient, q: str) -> list[dict]:
    params = {"q": q, "format": "jsonv2", "limit": 5, "countrycodes": "co", "addressdetails": 1,
              "viewbox": VIEWBOX, "bounded": 1, "accept-language": "es"}
    try:
        resp = await client.get(NOMINATIM_URL, params=params)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        print(f"[geo] nominatim error: {exc}")
    finally:
        await asyncio.sleep(1.1)  # política de uso: ≤ 1 req/s (no bloquea el event loop)
    return []


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_GENERICOS = {"biblioteca", "parque", "teatro", "museo", "casa", "publica", "centro", "uva", "corporacion",
              "fundacion", "galeria", "libreria", "auditorio", "sala", "escuela", "instituto", "universidad"}


def token_distintivo(nombre: str) -> Optional[str]:
    """La palabra más específica del nombre ('Biblioteca Pública Piloto' → 'piloto')."""
    toks = sorted((t for t in _tokens(nombre) if t not in _GENERICOS and len(t) >= 4), key=len, reverse=True)
    return toks[0] if toks else None


def es_ambiguo(nombre: str, match: dict, homonimos: list[dict]) -> bool:
    """True si OSM tiene otro lugar con el mismo nombre a > 300 m del elegido."""
    toks = _tokens(nombre)
    for h in homonimos:
        rn = _tokens(h.get("name"))
        if not rn or len(toks & rn) / max(1, min(len(toks), len(rn))) < UMBRAL_MATCH:
            continue
        if distancia_m(match["lat"], match["lng"], h["lat"], h["lng"]) > 300:
            return True
    return False


async def _homonimos_overpass(client: httpx.AsyncClient, nombre: str) -> list[dict]:
    tok = token_distintivo(nombre)
    if not tok:
        return []
    patron = "".join(_VOCALES_RE.get(ch, ch) for ch in tok)
    query = (f'[out:json][timeout:25];nwr["name"~"{patron}",i](5.95,-75.75,6.55,-75.25);out center tags 30;')
    try:
        resp = await client.post(OVERPASS_URL, data={"data": query})
        if resp.status_code != 200:
            return []
        out = []
        for e in resp.json().get("elements", []):
            c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
            if c.get("lat") is not None:
                out.append({"name": (e.get("tags") or {}).get("name"), "lat": c["lat"], "lng": c["lon"]})
        return out
    except Exception as exc:
        print(f"[geo] overpass error: {exc}")
        return []
    finally:
        await asyncio.sleep(1.1)


_VOCALES_RE = {"a": "[aá]", "e": "[eé]", "i": "[ií]", "o": "[oó]", "u": "[uúü]", "n": "[nñ]"}


async def verificar_lugar(client: httpx.AsyncClient, lugar: dict) -> dict:
    municipio = MUNICIPIOS.get(_norm(lugar.get("municipio")).replace(" ", "_"), "Medellín")
    match = None
    for q in (f"{lugar['nombre']}, {municipio}, Antioquia", f"{lugar['nombre']}, Antioquia"):
        match = elegir_resultado(lugar["nombre"], await _buscar(client, q), lugar.get("municipio"),
                                 lugar.get("direccion"))
        if match:
            break
    if match and es_ambiguo(lugar["nombre"], match, await _homonimos_overpass(client, lugar["nombre"])):
        match = None  # p. ej. sede y filiales con el mismo nombre: mejor no tocar
    actual = (float(lugar["lat"]), float(lugar["lng"])) if lugar.get("lat") is not None and lugar.get("lng") is not None else None
    estado, dist = clasificar(actual, match)
    return {"id": lugar["id"], "nombre": lugar["nombre"], "estado": estado, "dist_m": dist, "match": match}


async def run_verificacion_coordenadas(limit: int = 40, aplicar: bool = True) -> dict:
    """Verifica un lote de lugares físicos (los menos recientemente verificados primero)."""
    if supabase is None:
        return {"error": "supabase no configurado"}
    try:
        resp = (
            supabase.table("lugares")
            .select("id,nombre,municipio,direccion,tipo,lat,lng,coords_verificadas_en")
            .neq("tipo", "colectivo")
            .order("coords_verificadas_en", desc=False, nullsfirst=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        # Columna aún no creada (migración pendiente): lote sin orden de antigüedad
        resp = (
            supabase.table("lugares").select("id,nombre,municipio,direccion,tipo,lat,lng")
            .neq("tipo", "colectivo").limit(limit).execute()
        )
    lugares = resp.data or []
    stats = {"revisados": 0, "ok": 0, "corregir": 0, "nuevo": 0, "placeholder": 0, "sin_verificar": 0}
    detalle = []
    ahora = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        for lugar in lugares:
            r = await verificar_lugar(client, lugar)
            stats["revisados"] += 1
            stats[r["estado"]] += 1
            detalle.append(r)
            if not aplicar:
                continue
            update: dict = {"coords_verificadas_en": ahora, "coords_estado": r["estado"]}
            if r["estado"] in ("corregir", "nuevo") and r["match"]:
                update.update({"lat": r["match"]["lat"], "lng": r["match"]["lng"],
                               "coords_fuente": f"osm:{r['match']['osm']}"})
            elif r["estado"] == "ok" and r["match"]:
                update["coords_fuente"] = f"osm:{r['match']['osm']}"
            elif r["estado"] == "placeholder":
                update.update({"lat": None, "lng": None, "coords_fuente": None})
            try:
                supabase.table("lugares").update(update).eq("id", lugar["id"]).execute()
            except Exception:
                # Sin columnas de auditoría: aplicar solo lat/lng
                solo = {k: v for k, v in update.items() if k in ("lat", "lng")}
                if solo:
                    try:
                        supabase.table("lugares").update(solo).eq("id", lugar["id"]).execute()
                    except Exception as exc:
                        print(f"[geo] update error {lugar['id']}: {exc}")
    try:
        supabase.table("scraping_log").insert({
            "fuente": "geo_verificacion", "registros_nuevos": stats["nuevo"],
            "registros_actualizados": stats["corregir"] + stats["placeholder"], "errores": 0,
            "detalle": stats,
        }).execute()
    except Exception:
        pass
    return {"stats": stats, "detalle": detalle}
