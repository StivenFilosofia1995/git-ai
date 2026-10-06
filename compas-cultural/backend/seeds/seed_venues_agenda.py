"""
Seed: bares, teatros y espacios con agenda activa que aún no estaban en `lugares`.

Lista construida en oct-2026 a partir de un mapeo de venues del Valle de Aburrá;
el Instagram y la web de cada lugar se verificaron en fuentes propias del lugar
(su web, Google Maps, Facebook, prensa). Solo entran registros con confianza
alta/media y con al menos Instagram o sitio web, para que el auto-scraper los recorra.

Uso:
    cd backend
    python seeds/seed_venues_agenda.py            # dry-run: muestra qué haría
    python seeds/seed_venues_agenda.py --apply    # inserta en Supabase
"""
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import supabase

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "venues_agenda_2026_10.json")

# tipo del mapeo → (tipo, categoria_principal) usados en la tabla lugares
TIPO_MAP = {
    "bar": ("bar", "musica_en_vivo"),
    "club_musica": ("bar", "musica_en_vivo"),
    "teatro": ("teatro", "teatro"),
    "cafe_cultural": ("cafe", "centro_cultural"),
    "centro_cultural": ("centro_cultural", "centro_cultural"),
    "museo": ("museo", "galeria"),
    "galeria": ("galeria", "galeria"),
    "libreria": ("libreria", "libreria"),
    "academia": ("espacio_fisico", "taller"),
    "universidad": ("universidad", "centro_cultural"),
    "parque": ("parque_cultural", "centro_cultural"),
    "espacio_eventos": ("espacio_fisico", "otro"),
    "otro": ("espacio_fisico", "otro"),
}

VALLE = {"medellin", "envigado", "itagui", "bello", "sabaneta", "la_estrella",
         "caldas", "copacabana", "girardota", "barbosa"}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:200]


def _clean_handle(raw):
    if not raw:
        return None
    h = raw.strip().lstrip("@").split("?")[0].strip("/").lower()
    return h or None


def seed_venues(apply: bool, verbose: bool = True) -> dict:
    """Idempotente: solo inserta los venues cuyo slug/handle no existan aún."""
    venues = json.load(open(DATA_FILE, encoding="utf-8"))

    existing = supabase.table("lugares").select("slug,instagram_handle").execute().data or []
    slugs = {r["slug"] for r in existing}
    handles = {_clean_handle(r.get("instagram_handle")) for r in existing} - {None}

    nuevos, omitidos = [], []
    for v in venues:
        handle = _clean_handle(v.get("instagram"))
        if v.get("tipo") == "no_venue" or v.get("confianza") not in ("alta", "media"):
            omitidos.append((v["lugar"], "no_venue/confianza baja"))
            continue
        if not handle and not v.get("sitio_web"):
            omitidos.append((v["lugar"], "sin instagram ni web"))
            continue
        if v.get("municipio") not in VALLE:
            omitidos.append((v["lugar"], f"fuera del Valle ({v.get('municipio')})"))
            continue
        nombre = v.get("nombre_oficial") or v["lugar"]
        slug = slugify(nombre)
        if slug in slugs or (handle and handle in handles):
            omitidos.append((v["lugar"], "ya existe"))
            continue

        tipo, categoria = TIPO_MAP.get(v.get("tipo"), TIPO_MAP["otro"])
        nuevos.append({
            "nombre": nombre,
            "slug": slug,
            "tipo": tipo,
            "categorias": [categoria],
            "categoria_principal": categoria,
            "municipio": v["municipio"],
            "barrio": v.get("barrio"),
            "direccion": v.get("direccion"),
            "instagram_handle": handle,
            "sitio_web": v.get("sitio_web"),
            "lat": v.get("lat"),
            "lng": v.get("lng"),
            "nivel_actividad": "activo",
            "fuente_datos": "mapeo_venues_2026_10",
        })
        slugs.add(slug)
        if handle:
            handles.add(handle)

    if verbose:
        print(f"Nuevos: {len(nuevos)} | Omitidos: {len(omitidos)}")
        for n in nuevos:
            print(f"  + {n['nombre']:<45} @{n['instagram_handle'] or '-':<28} {n['municipio']}")
        for nombre, motivo in omitidos:
            print(f"  - {nombre:<45} ({motivo})")

    if not apply:
        if verbose:
            print("\nDry-run. Usa --apply para insertar.")
        return {"nuevos": len(nuevos), "insertados": 0}

    insertados = 0
    for n in nuevos:
        try:
            supabase.table("lugares").insert(n).execute()
            insertados += 1
        except Exception as e:
            print(f"  ✗ {n['nombre']}: {e}")
    print(f"✓ Venues agenda: insertados {insertados}/{len(nuevos)} lugares nuevos.")
    return {"nuevos": len(nuevos), "insertados": insertados}


if __name__ == "__main__":
    seed_venues(apply="--apply" in sys.argv)
