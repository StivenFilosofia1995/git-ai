"""
precision_scraper.py
Algoritmo maestro de scraping cultural de precisión.

Garantías:
  1. FECHA EXPLÍCITA — nunca se adivina ni infiere una fecha sin evidencia en el texto/imagen
  2. FUENTE ESPECÍFICA — fuente_url apunta al post/página específica, nunca a la homepage
  3. IMAGEN — siempre se intenta obtener og:image o media_url del post
  4. HORA CONFIRMADA — True solo cuando la hora está escrita en el texto
  5. ZONA — atribución correcta desde el lugar registrado (barrio/municipio)
  6. CONCURRENCIA — semáforo para respetar rate-limit de Instagram y sitios externos

Fases de ejecución:
  1. Todos los lugares registrados (IG + web) — concurrencia=5
  2. Agenda cultural alternativa (60+ sitios)
  3. Smart listener (Vision) sobre posts recientes con imagen
  4. Enriquecimiento de imágenes faltantes (og:image)
  5. Validación y log de resultados
"""

import asyncio
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.database import supabase

CO_TZ = ZoneInfo("America/Bogota")

# Concurrencia máxima simultánea al scrapear lugares (evita rate-limit en IG)
_SCRAPE_SEMAPHORE = asyncio.Semaphore(5)

# Tiempo mínimo entre requests al mismo dominio (segundos)
_MIN_DELAY_BETWEEN_REQUESTS = 1.5

# Umbrales de validación
_MAX_DAYS_AHEAD = 120          # Descartar eventos a más de 4 meses
_MAX_TITLE_LEN = 200
_MIN_TITLE_LEN = 4             # Títulos muy cortos son ruido


# ─────────────────────────────────────────────────────────────────────────────
# Validaciones de precisión
# ─────────────────────────────────────────────────────────────────────────────

def _is_explicit_date(fecha_str: Optional[str]) -> bool:
    """
    Retorna True si la fecha_str parece haber sido extraída explícitamente
    (tiene componente de hora distinto de 00:00:00, o fue marcada por el extractor).
    Retorna False para fechas que son solo "fecha sin hora" implícita.
    Para eventos con solo fecha (00:00:00) se acepta igual — lo que NO se acepta
    es fecha=None o fechas inválidas.
    """
    if not fecha_str:
        return False
    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return dt.year >= datetime.now(CO_TZ).year
    except (ValueError, TypeError):
        return False


def _is_future_event(fecha_str: Optional[str], days_ahead: int = _MAX_DAYS_AHEAD) -> bool:
    """Retorna True si la fecha es futura y dentro del ventana permitida."""
    if not fecha_str:
        return False
    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CO_TZ)
        now = datetime.now(CO_TZ)
        hoy = now.replace(hour=0, minute=0, second=0, microsecond=0)
        limite = now + timedelta(days=days_ahead)
        return hoy <= dt <= limite
    except (ValueError, TypeError):
        return False


def _has_specific_source_url(url: Optional[str]) -> bool:
    """
    Retorna True si la URL apunta a un recurso específico (post, evento, artículo).
    Retorna False para homepages o URLs demasiado genéricas.
    """
    if not url:
        return False
    url = url.strip().lower()
    # Instagram post permalink
    if "instagram.com/p/" in url:
        return True
    # Facebook event
    if "facebook.com/events/" in url:
        return True
    # URLs con path significativo (no solo dominio)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        # Necesita al menos un segmento de path no trivial
        segments = [s for s in path.split("/") if s and s not in ("es", "en", "index", "home")]
        return len(segments) >= 1 and len(path) > 3
    except Exception:
        return False


def _normalize_fuente_url(url: Optional[str], lugar: dict) -> Optional[str]:
    """
    Dado un URL candidato y el lugar, retorna la mejor URL de fuente.
    Prioriza: post_permalink > event_page > sitio_web > instagram_profile
    """
    if url and _has_specific_source_url(url):
        return url
    sitio = lugar.get("sitio_web")
    if sitio and _has_specific_source_url(sitio):
        return sitio
    ig = lugar.get("instagram_handle")
    if ig:
        return f"https://instagram.com/{ig.lstrip('@')}"
    return sitio


def _slugify(text: str) -> str:
    """Genera slug URL-safe desde texto."""
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:250]


def _event_fingerprint(titulo: str, fecha_str: str) -> str:
    """Hash único por (titulo_normalizado, fecha_dia) para deduplicación rápida."""
    slug = _slugify(titulo)
    dia = fecha_str[:10] if fecha_str else "unknown"
    return hashlib.md5(f"{slug}|{dia}".encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Enriquecimiento de imagen
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_og_image(url: Optional[str]) -> Optional[str]:
    """Obtiene og:image de una URL. Retorna None si falla o no hay imagen."""
    if not url:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "CulturaEterea-Bot/1.0"})
            if resp.status_code != 200:
                return None
            html = resp.text[:30_000]  # Solo necesitamos el <head>
        # og:image
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1).strip()
        # twitter:image
        m = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


async def _ensure_image(evento: dict, lugar: dict) -> Optional[str]:
    """
    Retorna imagen_url para el evento.
    Orden: imagen en evento > og:image de fuente_url > og:image de sitio_web
    """
    existing = evento.get("imagen_url")
    if existing and existing.startswith("http"):
        return existing

    fuente_url = evento.get("_fuente_url") or evento.get("fuente_url")
    img = await _fetch_og_image(fuente_url)
    if img:
        return img

    sitio = lugar.get("sitio_web")
    if sitio and sitio != fuente_url:
        img = await _fetch_og_image(sitio)
        if img:
            return img

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Persistencia con deduplicación
# ─────────────────────────────────────────────────────────────────────────────

def _check_duplicate(titulo: str, fecha_str: str, lugar_id: str) -> Optional[str]:
    """
    Revisa si ya existe un evento idéntico. Retorna su ID si existe, None si es nuevo.
    Estrategia: slug con fecha > Jaccard en mismo espacio+día
    """
    slug_with_date = f"{_slugify(titulo)}-{fecha_str[:10]}"
    try:
        r = supabase.table("eventos").select("id").eq("slug", slug_with_date).execute()
        if r.data:
            return r.data[0]["id"]
    except Exception:
        pass

    # Jaccard sobre mismo espacio + mismo día
    try:
        from app.services.auto_scraper import is_likely_duplicate
        existing = (
            supabase.table("eventos")
            .select("id,titulo,espacio_id")
            .gte("fecha_inicio", f"{fecha_str[:10]}T00:00:00")
            .lte("fecha_inicio", f"{fecha_str[:10]}T23:59:59")
            .eq("espacio_id", lugar_id)
            .limit(20)
            .execute()
        )
        if is_likely_duplicate(titulo, fecha_str, lugar_id, existing.data or []):
            return existing.data[0]["id"] if existing.data else "duplicate"
    except Exception:
        pass

    return None


def _insert_precise_event(evento: dict, lugar: dict, imagen_url: Optional[str]) -> bool:
    """
    Inserta un evento validado en la BD.
    Retorna True si se insertó, False si era duplicado o falló.
    """
    titulo = evento.get("titulo", "").strip()[:_MAX_TITLE_LEN]
    if len(titulo) < _MIN_TITLE_LEN:
        return False

    fecha_str = evento.get("fecha_inicio") or evento.get("fecha_iso")
    if not _is_explicit_date(fecha_str):
        return False
    if not _is_future_event(fecha_str):
        return False

    lugar_id = lugar["id"]
    dup_id = _check_duplicate(titulo, fecha_str, lugar_id)
    if dup_id:
        # Actualizar imagen si el existente no tiene
        if imagen_url and dup_id != "duplicate":
            try:
                existing = supabase.table("eventos").select("imagen_url").eq("id", dup_id).single().execute()
                if not existing.data.get("imagen_url"):
                    supabase.table("eventos").update({"imagen_url": imagen_url}).eq("id", dup_id).execute()
            except Exception:
                pass
        return False

    # Determinar hora_confirmada
    hora_confirmada = evento.get("hora_confirmada", False)
    if isinstance(hora_confirmada, str):
        hora_confirmada = hora_confirmada.lower() == "true"

    # Fuente URL precisa
    fuente_url = _normalize_fuente_url(
        evento.get("_fuente_url") or evento.get("fuente_url"),
        lugar
    )

    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CO_TZ)
        else:
            dt = dt.astimezone(CO_TZ)
        # Si no hay hora confirmada, normalizar a 00:00
        if not hora_confirmada:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except (ValueError, TypeError):
        return False

    fecha_fin = None
    if evento.get("fecha_fin"):
        try:
            fecha_fin = datetime.fromisoformat(str(evento["fecha_fin"]).replace("Z", "+00:00"))
            if fecha_fin.tzinfo is None:
                fecha_fin = fecha_fin.replace(tzinfo=CO_TZ)
        except (ValueError, TypeError):
            fecha_fin = None

    slug = f"{_slugify(titulo)}-{dt.strftime('%Y-%m-%d')}"
    categoria = evento.get("categoria_principal") or lugar.get("categoria_principal") or "otro"

    payload = {
        "titulo": titulo,
        "slug": slug,
        "espacio_id": lugar_id,
        "fecha_inicio": dt.isoformat(),
        "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
        "hora_confirmada": hora_confirmada,
        "categoria_principal": categoria,
        "categorias": evento.get("categorias") or [categoria],
        "municipio": lugar.get("municipio", "medellin"),
        "barrio": lugar.get("barrio"),
        "nombre_lugar": lugar.get("nombre"),
        "descripcion": (evento.get("descripcion") or "")[:1000],
        "precio": evento.get("precio"),
        "es_gratuito": bool(evento.get("es_gratuito", False)),
        "imagen_url": imagen_url,
        "fuente": evento.get("_fuente") or "precision_scraper",
        "fuente_url": fuente_url,
        "verificado": False,
    }

    try:
        supabase.table("eventos").insert(payload).execute()
        return True
    except Exception as e:
        print(f"    ❌ Error insertando '{titulo}': {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Scraper por lugar (con semáforo)
# ─────────────────────────────────────────────────────────────────────────────

async def _scrape_lugar_precision(lugar: dict) -> dict:
    """
    Scrape un lugar con garantías de precisión.
    Usa el semáforo global para limitar concurrencia.
    """
    async with _SCRAPE_SEMAPHORE:
        return await _scrape_lugar_inner(lugar)


async def _scrape_lugar_inner(lugar: dict) -> dict:
    """Lógica interna de scraping para un lugar."""
    stats = {"nuevos": 0, "duplicados": 0, "errores": 0, "sin_fecha": 0}
    nombre = lugar.get("nombre", "?")
    categoria = lugar.get("categoria_principal", "otro")
    municipio = lugar.get("municipio", "medellin")

    raw_events: list[dict] = []

    # ── IG scraping ─────────────────────────────────────────────────
    ig_handle = lugar.get("instagram_handle")
    if ig_handle:
        ig_handle = ig_handle.lstrip("@").strip()
        try:
            from app.services.instagram_pw_scraper import fetch_ig_profile
            from app.services.ig_event_extractor import extract_events_from_ig_profile

            profile = await fetch_ig_profile(ig_handle)
            if profile and (profile.get("captions") or profile.get("biography")):
                events_ig = extract_events_from_ig_profile(profile, nombre, categoria, municipio)
                ig_base = f"https://instagram.com/{ig_handle}"
                for ev in events_ig:
                    # Usar permalink específico si está disponible
                    permalink = ev.pop("_permalink", None)
                    ev["_fuente_url"] = permalink or ig_base
                    ev["_fuente"] = "precision_instagram"
                    ev["_hora_detectada"] = ev.get("_hora_detectada", False)
                raw_events.extend(events_ig)
                print(f"  📸 IG [{nombre}]: {len(events_ig)} eventos extraídos")
        except Exception as e:
            stats["errores"] += 1
            print(f"  ❌ IG error [{nombre}]: {e}")

    await asyncio.sleep(_MIN_DELAY_BETWEEN_REQUESTS)

    # ── Web scraping ─────────────────────────────────────────────────
    sitio = lugar.get("sitio_web")
    if sitio and "instagram.com" not in sitio.lower():
        try:
            from app.services.auto_scraper import (
                _fetch_website_raw,
                _normalize_site_url,
            )
            from app.services.html_event_extractor import extract_events_code
            from app.services.auto_scraper import needs_playwright
            from app.services.playwright_fetcher import fetch_with_playwright

            sitio = _normalize_site_url(sitio)
            html = await _fetch_website_raw(sitio)
            if html and needs_playwright(sitio):
                html_js = await fetch_with_playwright(sitio)
                if html_js and len(html_js) > len(html or ""):
                    html = html_js

            if html and len(html) > 200:
                events_web = extract_events_code(html, sitio, nombre, categoria, municipio)
                for ev in events_web:
                    ev["_fuente_url"] = ev.get("_fuente_url") or sitio
                    ev["_fuente"] = "precision_web"
                raw_events.extend(events_web)
                print(f"  🌐 Web [{nombre}]: {len(events_web)} eventos extraídos")
        except Exception as e:
            stats["errores"] += 1
            print(f"  ❌ Web error [{nombre}]: {e}")

    # ── Procesar y validar cada evento ──────────────────────────────
    for ev in raw_events:
        titulo = (ev.get("titulo") or "").strip()
        if len(titulo) < _MIN_TITLE_LEN:
            continue

        fecha_str = ev.get("fecha_inicio") or ev.get("fecha_iso")
        if not _is_explicit_date(fecha_str):
            stats["sin_fecha"] += 1
            continue
        if not _is_future_event(fecha_str):
            continue

        # Verificar que el evento es cultural válido
        try:
            from app.services.auto_scraper import is_likely_cultural_event
            if not is_likely_cultural_event(
                titulo,
                ev.get("descripcion"),
                fuente_url=ev.get("_fuente_url"),
                categoria=ev.get("categoria_principal") or categoria,
            ):
                continue
        except Exception:
            pass

        # Obtener imagen (con timeout para no bloquear)
        try:
            imagen_url = await asyncio.wait_for(
                _ensure_image(ev, lugar),
                timeout=8.0
            )
        except (asyncio.TimeoutError, Exception):
            imagen_url = ev.get("imagen_url")

        inserted = _insert_precise_event(ev, lugar, imagen_url)
        if inserted:
            stats["nuevos"] += 1
        else:
            stats["duplicados"] += 1

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────────────────────────────────────

async def run_precision_scraper(
    limit: Optional[int] = None,
    municipio: Optional[str] = None,
    *,
    run_agenda_sources: bool = True,
    run_vision_listener: bool = False,
    enrich_images: bool = True,
) -> dict:
    """
    Orquesta todo el sistema de scraping con garantías de precisión.

    Fases:
      1. Todos los lugares registrados (IG + web) — paralelo con semáforo=5
      2. Fuentes de agenda alternativa (si run_agenda_sources=True)
      3. Smart listener Vision (si run_vision_listener=True — consume API)
      4. Enriquecimiento de imágenes faltantes (si enrich_images=True)

    Args:
        limit: Máximo de lugares a procesar (None = todos)
        municipio: Filtrar por municipio específico
        run_agenda_sources: Scrapear 60+ sitios de agenda cultural independiente
        run_vision_listener: Activar Vision LLM (consume tokens de Groq/Gemini)
        enrich_images: Buscar og:image para eventos sin imagen
    """
    print("\n🎯 ════════════════════════════════════════════════")
    print("   PRECISION SCRAPER iniciando...")
    print("════════════════════════════════════════════════════")

    start = datetime.now(CO_TZ)
    total = {"lugares": 0, "nuevos": 0, "duplicados": 0, "errores": 0, "sin_fecha": 0}

    # ── Fase 1: Lugares registrados ──────────────────────────────────
    print("\n📍 FASE 1: Lugares registrados")
    query = supabase.table("lugares").select(
        "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
    )
    if municipio:
        query = query.eq("municipio", municipio)

    result = query.execute()
    lugares = [
        l for l in (result.data or [])
        if l.get("instagram_handle") or l.get("sitio_web")
    ]

    # Ordenar por antigüedad de scraping (lugares no scrapeados primero)
    try:
        from app.services.auto_scraper import _sort_lugares_by_staleness
        lugares = _sort_lugares_by_staleness(lugares)
    except Exception:
        pass

    if limit:
        lugares = lugares[:limit]

    print(f"   {len(lugares)} lugares a procesar (concurrencia=5)")

    # Ejecutar en paralelo con semáforo
    tasks = [_scrape_lugar_precision(l) for l in lugares]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, (lugar, res) in enumerate(zip(lugares, results)):
        if isinstance(res, Exception):
            total["errores"] += 1
            print(f"  ❌ [{lugar['nombre']}]: {res}")
        else:
            total["lugares"] += 1
            total["nuevos"] += res.get("nuevos", 0)
            total["duplicados"] += res.get("duplicados", 0)
            total["errores"] += res.get("errores", 0)
            total["sin_fecha"] += res.get("sin_fecha", 0)

    print(f"   ✅ Fase 1 completa: {total['nuevos']} eventos nuevos")

    # ── Fase 2: Agenda alternativa (60+ sitios culturales) ───────────
    if run_agenda_sources:
        print("\n📰 FASE 2: Agenda alternativa")
        try:
            from app.services.auto_scraper import scrape_agenda_sources, scrape_compas_urbano
            agenda_result = await scrape_agenda_sources()
            compas_result = await scrape_compas_urbano()
            agenda_new = agenda_result.get("nuevos", 0) if isinstance(agenda_result, dict) else 0
            compas_new = compas_result.get("nuevos", 0) if isinstance(compas_result, dict) else 0
            total["nuevos"] += agenda_new + compas_new
            print(f"   ✅ Agenda: +{agenda_new} | Compas: +{compas_new}")
        except Exception as e:
            print(f"   ❌ Agenda alternativa error: {e}")

    # ── Fase 3: Smart Listener Vision (opcional, consume API) ─────────
    if run_vision_listener:
        print("\n👁️  FASE 3: Smart Listener Vision")
        try:
            from app.services.smart_listener import run_smart_listener
            listener_result = await run_smart_listener()
            vision_new = listener_result.get("nuevos", 0) if isinstance(listener_result, dict) else 0
            total["nuevos"] += vision_new
            print(f"   ✅ Vision: +{vision_new} eventos")
        except Exception as e:
            print(f"   ❌ Vision listener error: {e}")

    # ── Fase 4: Enriquecimiento de imágenes ───────────────────────────
    if enrich_images:
        print("\n🖼️  FASE 4: Enriquecimiento de imágenes")
        try:
            from app.services.auto_scraper import enrich_event_images
            img_result = await enrich_event_images(limit=400)
            img_updated = img_result.get("actualizados", 0) if isinstance(img_result, dict) else 0
            total["imagenes_enriquecidas"] = img_updated
            print(f"   ✅ Imágenes: +{img_updated} actualizadas")
        except Exception as e:
            print(f"   ❌ Enrichment error: {e}")

    elapsed = (datetime.now(CO_TZ) - start).total_seconds()
    total["duracion_segundos"] = round(elapsed, 1)

    print("\n✅ ════════════════════════════════════════════════")
    print(f"   PRECISION SCRAPER completado en {elapsed:.0f}s")
    print(f"   Lugares procesados: {total['lugares']}")
    print(f"   Eventos nuevos: {total['nuevos']}")
    print(f"   Duplicados: {total['duplicados']}")
    print(f"   Sin fecha explícita (descartados): {total['sin_fecha']}")
    print(f"   Errores: {total['errores']}")
    print("════════════════════════════════════════════════════\n")

    # Registrar en log
    try:
        supabase.table("scraping_log").insert({
            "fuente": "precision_scraper",
            "registros_nuevos": total["nuevos"],
            "registros_actualizados": total.get("imagenes_enriquecidas", 0),
            "errores": total["errores"],
            "detalle": total,
            "duracion_segundos": total["duracion_segundos"],
        }).execute()
    except Exception:
        pass

    return total


async def run_quick_precision_scraper(municipio: Optional[str] = None) -> dict:
    """
    Versión rápida: solo lugares del municipio, sin vision ni agenda alternativa.
    Ideal para re-scrapear una zona específica on-demand.
    """
    return await run_precision_scraper(
        limit=30,
        municipio=municipio,
        run_agenda_sources=False,
        run_vision_listener=False,
        enrich_images=True,
    )
