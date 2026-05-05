# -*- coding: utf-8 -*-
"""
Compás Urbano API Scraper — fuente de mayor prioridad.
API pública JSON, sin autenticación, eventos verificados del Valle de Aburrá.

URL: https://www.apicompasurbano.com/Catalog/MacroEventos.json
"""
import re
import json
import asyncio
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.database import supabase

# ─── Constantes ────────────────────────────────────────────────────────────────

COMPAS_API_URL = "https://www.apicompasurbano.com/Catalog/MacroEventos.json"
COMPAS_BASE_URL = "https://www.compasurbano.com"

CATEGORIA_MAP = {
    1: "arte_contemporaneo",
    2: "teatro",
    3: "cine",
    4: "otro",       # conferencia
    5: "danza",
    6: "festival",
    7: "musica_en_vivo",
    8: "electronica",
    9: "otro",       # taller / experiencia
}

MUNICIPIO_ALIAS = {
    "medellín": "medellin", "medellin": "medellin",
    "itagüí": "itagui", "itagui": "itagui",
    "envigado": "envigado",
    "sabaneta": "sabaneta",
    "bello": "bello",
    "caldas": "caldas",
    "la estrella": "la_estrella", "la_estrella": "la_estrella",
    "copacabana": "copacabana",
    "girardota": "girardota",
    "barbosa": "barbosa",
}

GRATUITO_KEYWORDS = {"", "null", "gratuito", "libre", "gratis", "entrada libre", "sin costo"}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


def _normalizar_municipio(raw: str) -> str:
    if not raw:
        return "medellin"
    clean = raw.lower().strip()
    # strip accents for alias lookup
    nfd = unicodedata.normalize("NFD", clean)
    nfd = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return MUNICIPIO_ALIAS.get(clean) or MUNICIPIO_ALIAS.get(nfd, "medellin")


def _parse_fecha(raw: str) -> Optional[datetime]:
    """Parse Compas Urbano date string: '2026-04-25T20:00:00.0000000-05:00'"""
    if not raw:
        return None
    try:
        # Remove fractional seconds and timezone
        clean = re.sub(r"\.\d+", "", raw)   # remove .0000000
        clean = re.sub(r"[+-]\d{2}:\d{2}$", "", clean)  # remove -05:00
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _build_imagen_url(foto: str) -> Optional[str]:
    if not foto:
        return None
    if foto.startswith("http"):
        return foto
    return f"{COMPAS_BASE_URL}/{foto.lstrip('/')}"


def _parse_precio(ev: dict) -> tuple[str, bool]:
    """Returns (precio_str, es_gratuito) from Compas Urbano event dict."""
    modo = (ev.get("modoIngreso") or "").lower().strip()
    monto_min = ev.get("montoMinimo") or ""
    monto_max = ev.get("montoMaximo") or ""

    if modo in GRATUITO_KEYWORDS and not monto_min:
        return ("Entrada libre", True)

    if monto_min and monto_max and monto_min != monto_max:
        return (f"${monto_min} - ${monto_max}", False)
    elif monto_min:
        return (f"${monto_min}", False)
    elif monto_max:
        return (f"${monto_max}", False)

    return ("", False)


def _parse_gps(gps_raw) -> tuple[Optional[float], Optional[float]]:
    """Parse GPS JSON string: '{"lat": 6.25, "lng": -75.56}'"""
    if not gps_raw:
        return None, None
    try:
        if isinstance(gps_raw, str):
            data = json.loads(gps_raw)
        else:
            data = gps_raw
        lat = float(data.get("lat") or data.get("latitude", 0))
        lng = float(data.get("lng") or data.get("longitude", 0))
        if lat == 0 and lng == 0:
            return None, None
        return lat, lng
    except (json.JSONDecodeError, ValueError, TypeError):
        return None, None


# ─── Fetch API ─────────────────────────────────────────────────────────────────

async def _fetch_compas_eventos() -> list[dict]:
    """Fetch all events from Compas Urbano public API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CO,es;q=0.9",
        "Origin": "https://www.compasurbano.com",
        "Referer": "https://www.compasurbano.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(COMPAS_API_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            # Some endpoints wrap in a key
            for key in ("eventos", "MacroEventos", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            return []
    except Exception as e:
        print(f"[COMPAS_URBANO] Error fetching API: {e}")
        return []


# ─── Discover colectivos ────────────────────────────────────────────────────────

def _registrar_organizador(organizador: str, municipio: str) -> Optional[str]:
    """Register organizer as lugar if not exists. Returns lugar_id or None."""
    if not organizador or len(organizador) < 2:
        return None

    slug = _slugify(organizador)
    try:
        existing = supabase.table("lugares").select("id").eq("slug", slug).execute()
        if existing.data:
            return existing.data[0]["id"]

        result = supabase.table("lugares").insert({
            "nombre": organizador[:200],
            "slug": slug,
            "tipo": "colectivo",
            "categoria_principal": "otro",
            "categorias": ["otro"],
            "municipio": municipio,
            "descripcion_corta": "Organizador cultural activo en Compás Urbano",
            "fuente_datos": "compas_urbano_discovery",
            "nivel_actividad": "activo",
        }).execute()

        if result.data:
            print(f"  [COMPAS] Nuevo organizador registrado: {organizador}")
            return result.data[0]["id"]
    except Exception as e:
        print(f"  [COMPAS] Error registrando organizador '{organizador}': {e}")
    return None


# ─── Main: scrape Compas Urbano ────────────────────────────────────────────────

async def scrape_compas_urbano() -> dict:
    """
    Fetch all events from Compas Urbano API and insert new ones into DB.
    
    - Filters: only future events (>= now Colombia UTC-5)
    - Deduplication: by slug
    - Auto-registers organizers as lugares if not exists
    - All events are marked verificado=True
    """
    print("\n[COMPAS URBANO] ========================================")
    print("   Fetching eventos from apicompasurbano.com ...")
    print("========================================================")

    raw_events = await _fetch_compas_eventos()
    if not raw_events:
        print("  [COMPAS] No se obtuvieron eventos de la API")
        return {"nuevos": 0, "duplicados": 0, "errores": 0, "total_api": 0}

    print(f"  [COMPAS] {len(raw_events)} eventos recibidos del API")

    now_co = datetime.utcnow() - timedelta(hours=5)
    stats = {"nuevos": 0, "duplicados": 0, "errores": 0, "total_api": len(raw_events)}

    for ev in raw_events:
        try:
            # ── Título ──
            titulo = (ev.get("nombre") or "").strip()
            if not titulo or len(titulo) < 3:
                continue

            # ── Fecha ──
            fecha = _parse_fecha(ev.get("fechaInicio") or ev.get("fecha_inicio"))
            if not fecha:
                continue
            if fecha < now_co - timedelta(hours=6):   # allow 6h grace period
                continue
            if fecha > now_co + timedelta(days=365):
                continue

            # ── Slug (dedup key) ──
            slug = _slugify(titulo)
            existing = supabase.table("eventos").select("id").eq("slug", slug).execute()
            if existing.data:
                stats["duplicados"] += 1
                continue

            # ── Categoría ──
            cat_id = int(ev.get("categoria") or 0)
            categoria = CATEGORIA_MAP.get(cat_id, "otro")

            # ── Municipio ──
            municipio = _normalizar_municipio(ev.get("municipio") or "medellin")

            # ── Precio ──
            precio_str, es_gratuito = _parse_precio(ev)

            # ── Imágenes ──
            imagen_url = (
                _build_imagen_url(ev.get("thumbnailFoto"))
                or _build_imagen_url(ev.get("foto"))
            )

            # ── GPS ──
            lat, lng = _parse_gps(ev.get("gps"))

            # ── Nombre lugar ──
            nombre_lugar = (ev.get("lugar") or "").strip() or titulo

            # ── Descripción ──
            desc_raw = ev.get("descripcion") or ""
            # Strip HTML tags
            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()[:500] or None

            # ── URL fuente ──
            ev_id = ev.get("id") or ""
            ev_nombre_slug = _slugify(titulo)
            fuente_url = f"{COMPAS_BASE_URL}/eventos/ciudad/{ev_nombre_slug}/{ev_id}" if ev_id else None

            # ── Organizador → lugar ──
            organizador = (ev.get("organizador") or "").strip()
            if organizador:
                _registrar_organizador(organizador, municipio)

            # ── Fecha fin ──
            fecha_fin_raw = ev.get("fechaFin") or ev.get("fecha_fin")
            fecha_fin = _parse_fecha(fecha_fin_raw)

            # ── Insertar evento ──
            evento_data = {
                "titulo": titulo[:200],
                "slug": slug,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
                "categorias": [categoria],
                "categoria_principal": categoria,
                "municipio": municipio,
                "nombre_lugar": nombre_lugar[:255],
                "descripcion": desc,
                "imagen_url": imagen_url,
                "precio": precio_str,
                "es_gratuito": es_gratuito,
                "es_recurrente": False,
                "lat": lat,
                "lng": lng,
                "fuente": "worker_compas_urbano",
                "fuente_url": fuente_url,
                "verificado": True,   # ← fuente oficial verificada
            }

            supabase.table("eventos").insert(evento_data).execute()
            stats["nuevos"] += 1
            print(f"  [NEW] {titulo[:60]} ({municipio}, {fecha.strftime('%d/%m')})")

        except Exception as e:
            stats["errores"] += 1
            print(f"  [ERR] {ev.get('nombre', '?')[:50]}: {e}")
            continue

    print(f"\n[COMPAS URBANO] Completado")
    print(f"  API total: {stats['total_api']}")
    print(f"  Nuevos: {stats['nuevos']}")
    print(f"  Duplicados: {stats['duplicados']}")
    print(f"  Errores: {stats['errores']}")

    # Log en scraping_log
    try:
        supabase.table("scraping_log").insert({
            "fuente": "compas_urbano_api",
            "registros_nuevos": stats["nuevos"],
            "registros_actualizados": 0,
            "errores": stats["errores"],
            "detalle": stats,
        }).execute()
    except Exception:
        pass

    return stats
