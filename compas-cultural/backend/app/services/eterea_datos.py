"""
Datos que ETÉREA necesita a mano (en memoria, con caducidad corta):
lugares (para reconocer "Otraparte", "Casa Teatro"…), barrios → zona/comuna, y próximos eventos
(para reconocer "el festival de flamenco" en una pregunta de detalle).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Optional

from app.services.eterea_lexico import norm

_CACHE: dict[str, tuple[float, object]] = {}


def _cacheado(clave: str, ttl: int, fn):
    hit = _CACHE.get(clave)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    try:
        valor = fn()
    except Exception as exc:
        print(f"[eterea_datos] {clave}: {exc}")
        return hit[1] if hit else ([] if clave != "zonas" else {})
    _CACHE[clave] = (time.time(), valor)
    return valor


def lugares() -> list[dict]:
    def cargar():
        from app.database import supabase
        cols = ("id,nombre,slug,tipo,categoria_principal,municipio,barrio,direccion,lat,lng,instagram_handle,"
                "sitio_web,telefono,descripcion_corta,nivel_actividad")
        filas = supabase.table("lugares").select(cols).neq("nivel_actividad", "cerrado").range(0, 1999).execute().data
        return filas or []
    return _cacheado("lugares", 1800, cargar)


def zonas() -> dict:
    """{'alias': (zona_nombre, comuna), ...} y {'zona_nombre': {barrios}}."""
    def cargar():
        from app.database import supabase
        filas = supabase.table("zonas_barrios_map").select(
            "zona_nombre,comuna,barrio_alias_norm,municipio").range(0, 4999).execute().data or []
        alias, barrios, municipio = {}, {}, {}
        for f in filas:
            a = norm(f.get("barrio_alias_norm"))
            z = f.get("zona_nombre")
            if not a or not z:
                continue
            alias[a] = (z, f.get("comuna") or "")
            barrios.setdefault(z, set()).add(a)
            municipio.setdefault(z, norm(f.get("municipio")).replace(" ", "_"))
        return {"alias": alias, "barrios": barrios, "municipio": municipio}
    return _cacheado("zonas", 3600, cargar)


def eventos_proximos(dias: int = 60) -> list[dict]:
    def cargar():
        from app.services.evento_service import CO_TZ, get_eventos
        hoy = datetime.now(CO_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        return get_eventos(fecha_desde=hoy, fecha_hasta=hoy + timedelta(days=dias), limit=1000)
    return _cacheado(f"eventos_{dias}", 600, cargar)


# ─── Reconocer nombres propios en el mensaje ─────────────────────────────
_GENERICAS = {"teatro", "biblioteca", "casa", "museo", "parque", "corporacion", "fundacion", "centro", "cultural",
              "colectivo", "espacio", "galeria", "la", "el", "los", "las", "de", "del", "y", "medellin", "agenda",
              "eventos", "programacion", "sala", "auditorio", "publica", "uva", "comfama", "grupo", "escuela",
              "academia", "taller", "club", "red", "bar", "cafe", "libreria", "editorial", "festival", "the"}
_NO_NOMBRE = {"medellin", "envigado", "itagui", "bello", "sabaneta", "caldas", "copacabana", "girardota", "barbosa",
              "estrella", "poblado", "laureles", "centro", "musica", "teatro", "danza", "cine", "arte", "poesia",
              "cultura", "hoy", "manana", "gratis", "rock", "jazz", "salsa", "tango", "lectura", "libros"}


def _prohibidas() -> set[str]:
    from app.services.eterea_buscador import TIPOS
    from app.services.eterea_lexico import FRASES_DE_TIPO
    return _NO_NOMBRE | FRASES_DE_TIPO | {d for (_, _, disp) in TIPOS.values() for d in disp}


def _frases_de(nombre: str) -> list[str]:
    n = norm(re.sub(r"\s[-–|]\s.*$", "", nombre or ""))  # "Casa Teatro El Poblado - Agenda" → sin sufijo
    frases = [n]
    distintiva = " ".join(w for w in n.split() if w not in _GENERICAS)
    if distintiva and distintiva != n and len(distintiva) >= 5 and distintiva not in _NO_NOMBRE:
        frases.append(distintiva)
    # Un nombre de una sola palabra corta o genérica ("Cine", "Salsa") no puede adueñarse de esa palabra
    prohibidas = _prohibidas()
    return [f for f in frases if len(f) >= 4 and f not in prohibidas and f not in _GENERICAS
            and (len(f.split()) >= 2 or len(f) >= 7)]


def _indice_lugares():
    def construir():
        idx = []
        for l in lugares():
            for f in _frases_de(l.get("nombre")):
                idx.append((f, l))
        idx.sort(key=lambda x: -len(x[0]))
        return idx
    return _cacheado("indice_lugares", 1800, construir)


def lugar_en(t: str) -> Optional[dict]:
    """El lugar con nombre más largo que aparece completo en el mensaje normalizado `t` (con espacios)."""
    for frase, l in _indice_lugares():
        if f" {frase} " in t:
            return l
    return None


def _centro_zona(barrios: frozenset) -> Optional[tuple[float, float]]:
    pts = [(float(l["lat"]), float(l["lng"])) for l in lugares()
           if l.get("lat") is not None and norm(l.get("barrio")) in barrios]
    if len(pts) < 2:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def zona_en(t: str) -> Optional[tuple]:
    """(nombre de la zona, barrios, centro aproximado) si el mensaje nombra una comuna, zona o barrio."""
    z = zonas()
    if not z:
        return None
    if re.search(r" (el centro|centro de medellin|del centro) ", t):
        t = t + " la candelaria "
    elegido = None
    m = re.search(r" comuna (\d{1,2}) ", t)
    if m:
        elegido = next((n for n in z["barrios"] if re.search(rf"comuna {m.group(1)}\b", norm(n))), None)
    if not elegido:
        for alias in sorted(z["alias"], key=len, reverse=True):
            if len(alias) >= 4 and f" {alias} " in t and alias not in _NO_NOMBRE - {"poblado", "laureles"}:
                elegido = z["alias"][alias][0]
                break
    if not elegido:
        for nombre in z["barrios"]:
            base = norm(re.sub(r"\(.*?\)", "", nombre))
            if len(base) >= 5 and f" {base} " in t:
                elegido = nombre
                break
    if not elegido:
        return None
    barrios = frozenset(z["barrios"].get(elegido, set()))
    return elegido, barrios, _centro_zona(barrios), z.get("municipio", {}).get(elegido)
