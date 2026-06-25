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
    nfd = unicodedata.normalize("NFD", clean)
    nfd = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return MUNICIPIO_ALIAS.get(clean) or MUNICIPIO_ALIAS.get(nfd, "medellin")


def _parse_fecha(raw: str) -> Optional[datetime]:
    """Parse Compas Urbano date string: '2026-04-25T20:00:00.0000000-05:00'"""
    if not raw:
        return None
    try:
        clean = re.sub(r"\.\d+", "", raw)
        clean = re.sub(r"[+-]\d{2}:\d{2}$", "", clean)
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _build_imagen_url(foto: str) -> Optional[str]:
    if not foto:
        return None
    foto = foto.strip()
    if foto in ("null", "undefined", ""):
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
        if not isinstance(data, dict):
            return None, None
        lat = float(data.get("lat") or data.get("latitude", 0))
        lng = float(data.get("lng") or data.get("longitude", 0))
        if lat == 0 and lng == 0:
            return None, None
        return lat, lng
    except (ValueError, TypeError):
        return None, None


def _get_fuente_url(ev: dict, ev_id, ev_slug: str) -> Optional[str]:
    """
    Build best source URL for event.
    Priority: external web field → linkModoIngreso → compasurbano fallback.
    The API's 'web' field is the actual event/organization website — most useful.
    """
    web = (ev.get("web") or "").strip()
    if web and web not in ("null", "undefined", ".") and web.lower().startswith("http"):
        return web

    link = (ev.get("linkModoIngreso") or "").strip()
    if link and link not in ("null", "undefined") and link.lower().startswith("http"):
        return link

    if ev_id:
        return f"{COMPAS_BASE_URL}/evento/{ev_slug}/{ev_id}"

    return None


def _get_fecha_fin_real(ev: dict, fecha_inicio: datetime) -> Optional[datetime]:
    """
    Get actual event end date from diasEvento (last date in the list).
    The API's fechaFin field is set to 50 years in the future for recurring events
    and is not a useful end date. Use diasEvento instead.
    """
    dias_raw = (ev.get("diasEvento") or "").strip()
    if dias_raw and dias_raw not in ("null", "undefined"):
        dates = [d.strip() for d in dias_raw.split(",") if d.strip() and len(d.strip()) >= 10]
        if dates:
            try:
                last = max(dates)
                last_dt = datetime.fromisoformat(last[:10])
                # Only use if it's after fecha_inicio and within 3 years
                if last_dt >= fecha_inicio and (last_dt - fecha_inicio).days <= 1095:
                    # Set time to end of day if it's just a date
                    return last_dt.replace(hour=23, minute=59)
            except (ValueError, TypeError):
                pass

    # Fall back to API fechaFin only if it's a reasonable duration (≤ 2 years)
    fecha_fin_raw = ev.get("fechaFin") or ev.get("fecha_fin")
    if fecha_fin_raw:
        ff = _parse_fecha(fecha_fin_raw)
        if ff and (ff - fecha_inicio).days <= 730:
            return ff

    return None


def _parse_hora_inicio(ev: dict, fecha: datetime) -> tuple[datetime, bool]:
    """
    Apply horaInicio field to fecha if available.
    Returns (fecha_con_hora, hora_confirmada).
    The API has a dedicated horaInicio field like "19:00" — use it directly.
    """
    hora_raw = (ev.get("horaInicio") or "").strip()
    if hora_raw and hora_raw not in ("null", "undefined") and ":" in hora_raw:
        try:
            parts = hora_raw.split(":")
            h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            if 0 <= h <= 23 and 0 <= m <= 59:
                return fecha.replace(hour=h, minute=m, second=0), True
        except (ValueError, IndexError):
            pass
    return fecha, False


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
    Fetch all events from Compas Urbano API and upsert into DB.

    - Filters: only future events (fechaInicio >= now Colombia UTC-5)
    - Deduplication: by slug — on duplicate, UPDATE fuente_url to fix broken links
    - Uses 'web' API field as fuente_url (actual event website, not compasurbano page)
    - Uses 'horaInicio' field directly for confirmed event times
    - fecha_fin computed from diasEvento last date, not the API's 50-year placeholder
    - All events are marked verificado=True
    """
    print("\n[COMPAS URBANO] ========================================")
    print("   Fetching eventos from apicompasurbano.com ...")
    print("========================================================")

    raw_events = await _fetch_compas_eventos()
    if not raw_events:
        print("  [COMPAS] No se obtuvieron eventos de la API")
        return {"nuevos": 0, "duplicados": 0, "actualizados": 0, "errores": 0, "total_api": 0}

    print(f"  [COMPAS] {len(raw_events)} eventos recibidos del API")

    from datetime import timezone
    now_co = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
    stats = {"nuevos": 0, "duplicados": 0, "actualizados": 0, "errores": 0, "total_api": len(raw_events)}

    for ev in raw_events:
        try:
            # ── Título ──
            titulo = (ev.get("nombre") or "").strip()
            if not titulo or len(titulo) < 3:
                continue

            # ── Fecha inicio ──
            fecha = _parse_fecha(ev.get("fechaInicio") or ev.get("fecha_inicio"))
            if not fecha:
                continue
            # Skip events that started more than 6 hours ago
            if fecha < now_co - timedelta(hours=6):
                continue
            # Skip events more than 18 months out (unlikely to be confirmed)
            if fecha > now_co + timedelta(days=548):
                continue

            # ── Slug ──
            slug = _slugify(titulo)

            # ── ID Compas Urbano ──
            ev_id = ev.get("id") or ""

            # ── Fuente URL (external web, not compasurbano page) ──
            fuente_url = _get_fuente_url(ev, ev_id, slug)

            # ── Dedup: check existing event by slug ──
            existing = supabase.table("eventos").select("id,fuente_url,fuente").eq("slug", slug).execute()
            if existing.data:
                ex = existing.data[0]
                # Fix broken fuente_url on existing compasurbano events
                if "compas_urbano" in (ex.get("fuente") or ""):
                    existing_url = ex.get("fuente_url") or ""
                    if fuente_url and fuente_url != existing_url:
                        supabase.table("eventos").update({
                            "fuente_url": fuente_url,
                        }).eq("id", ex["id"]).execute()
                        stats["actualizados"] += 1
                        print(f"  [UPD] URL corregida: {titulo[:50]}")
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

            # ── Descripción ── (strip HTML, use detalleHora as fallback)
            desc_raw = ev.get("descripcion") or ev.get("detalleHora") or ""
            desc = re.sub(r"<[^>]+>", "", desc_raw).strip()[:500] or None

            # ── Hora confirmada (from API field, not regex) ──
            fecha, hora_confirmada = _parse_hora_inicio(ev, fecha)

            # ── Fecha fin real (from diasEvento, not 50-year placeholder) ──
            fecha_fin = _get_fecha_fin_real(ev, fecha)

            # ── Es recurrente (multi-día) ──
            dias_raw = (ev.get("diasEvento") or "").strip()
            dias_count = len([d for d in dias_raw.split(",") if d.strip()]) if dias_raw else 1
            es_recurrente = dias_count > 3

            # ── Organizador → lugar ──
            organizador = (ev.get("organizador") or "").strip()
            if organizador:
                _registrar_organizador(organizador, municipio)

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
                "es_recurrente": es_recurrente,
                "hora_confirmada": hora_confirmada,
                "lat": lat,
                "lng": lng,
                "fuente": "worker_compas_urbano",
                "fuente_url": fuente_url,
                "verificado": True,
            }

            supabase.table("eventos").insert(evento_data).execute()
            stats["nuevos"] += 1
            hora_str = fecha.strftime('%H:%M') if hora_confirmada else '?'
            print(f"  [NEW] {titulo[:55]} ({municipio}, {fecha.strftime('%d/%m')} {hora_str})")

        except Exception as e:
            stats["errores"] += 1
            print(f"  [ERR] {ev.get('nombre', '?')[:50]}: {e}")
            continue

    print("\n[COMPAS URBANO] Completado")
    print(f"  API total:    {stats['total_api']}")
    print(f"  Nuevos:       {stats['nuevos']}")
    print(f"  Duplicados:   {stats['duplicados']}")
    print(f"  URL corregidas: {stats['actualizados']}")
    print(f"  Errores:      {stats['errores']}")

    try:
        supabase.table("scraping_log").insert({
            "fuente": "compas_urbano_api",
            "registros_nuevos": stats["nuevos"],
            "registros_actualizados": stats["actualizados"],
            "errores": stats["errores"],
            "detalle": stats,
        }).execute()
    except Exception:
        pass

    return stats
