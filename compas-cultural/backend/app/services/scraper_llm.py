"""
Scraper determinista (sin LLMs).
Extrae informacion cultural de URLs usando httpx + BeautifulSoup + Playwright + Regex.
Mantiene el nombre scraper_llm.py por compatibilidad, pero ya no usa inteligencia artificial.
"""
import re
import traceback
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup

from app.database import supabase
from app.services.html_event_extractor import extract_events_code

CO_TZ = ZoneInfo("America/Bogota")

def _now_co() -> datetime:
    return datetime.now(CO_TZ)

def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[áàäâ]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöô]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]

def _extract_ig_handle(url: str) -> str:
    """Extract Instagram handle from a URL."""
    clean = url.split("?")[0].split("#")[0].rstrip("/")
    parts = clean.split("/")
    for i, part in enumerate(parts):
        if "instagram.com" in part and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else ""


def _normalize_url(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None
    value = str(raw_url).strip()
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme or "https"
    path = parsed.path.rstrip("/")
    return f"{scheme}://{parsed.netloc.lower()}{path}"


def _build_event_slug_with_date(titulo: str, fecha: datetime) -> str:
    return f"{_slugify(titulo)}-{fecha.strftime('%Y-%m-%d')}"


def _find_existing_lugar(
    *,
    slug: str,
    instagram_handle: Optional[str],
    sitio_web: Optional[str],
) -> Optional[str]:
    """Find an existing lugar by strongest identifiers first."""
    clean_handle = (instagram_handle or "").strip().lstrip("@").lower()
    if clean_handle:
        try:
            existing = (
                supabase.table("lugares")
                .select("id")
                .or_(f"instagram_handle.eq.@{clean_handle},instagram_handle.eq.{clean_handle}")
                .limit(1)
                .execute()
            )
            if existing.data:
                return existing.data[0]["id"]
        except Exception:
            pass

    if sitio_web:
        normalized_target = _normalize_url(sitio_web)
        try:
            rows = (
                supabase.table("lugares")
                .select("id,sitio_web")
                .not_.is_("sitio_web", "null")
                .limit(500)
                .execute()
            )
            for row in (rows.data or []):
                if _normalize_url(row.get("sitio_web")) == normalized_target:
                    return row["id"]
        except Exception:
            pass

    try:
        existing_slug = supabase.table("lugares").select("id").eq("slug", slug).limit(1).execute()
        if existing_slug.data:
            return existing_slug.data[0]["id"]
    except Exception:
        pass

    return None


def _upsert_lugar(espacio: dict, fallback_url: str) -> str:
    """Create or update a lugar and return its id."""
    nombre = (espacio.get("nombre") or fallback_url).strip()[:150]
    slug = _slugify(nombre)
    instagram_handle = espacio.get("instagram_handle") or None
    sitio_web = espacio.get("sitio_web") or fallback_url

    existing_id = _find_existing_lugar(
        slug=slug,
        instagram_handle=instagram_handle,
        sitio_web=sitio_web,
    )

    lugar_data = {
        "nombre": nombre,
        "slug": slug,
        "tipo": espacio.get("tipo") or "colectivo",
        "categorias": espacio.get("categorias") or [],
        "categoria_principal": espacio.get("categoria_principal") or "otro",
        "municipio": espacio.get("municipio") or "medellin",
        "descripcion_corta": espacio.get("descripcion_corta") or None,
        "instagram_handle": instagram_handle,
        "sitio_web": sitio_web,
        "es_underground": bool(espacio.get("es_underground") or False),
        "fuente_datos": "scraping_codigo",
        "nivel_actividad": "activo",
    }

    if existing_id:
        update_payload = {
            k: v
            for k, v in lugar_data.items()
            if v is not None and v != ""
        }
        supabase.table("lugares").update(update_payload).eq("id", existing_id).execute()
        return existing_id

    insert_resp = supabase.table("lugares").insert(lugar_data).execute()
    if not insert_resp.data:
        raise RuntimeError("No se pudo crear el lugar en Supabase")
    return insert_resp.data[0]["id"]


def _insert_fallback_events(eventos: list[dict], *, espacio_id: str, fuente_url: str) -> int:
    """Insert deterministic extracted events if robust scraper found none."""
    inserted = 0
    now = _now_co()
    hoy_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for ev_data in eventos:
        titulo = (ev_data.get("titulo") or "").strip()
        fecha_str = ev_data.get("fecha_inicio")
        if not titulo or not fecha_str:
            continue

        try:
            fecha = datetime.fromisoformat(fecha_str)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=CO_TZ)
            else:
                fecha = fecha.astimezone(CO_TZ)
            if fecha < hoy_inicio:
                continue
        except (ValueError, TypeError):
            continue

        slug_ev = _build_event_slug_with_date(titulo, fecha)
        existing_ev = supabase.table("eventos").select("id").eq("slug", slug_ev).limit(1).execute()
        if existing_ev.data:
            continue

        evento_data = {
            "titulo": titulo,
            "slug": slug_ev,
            "espacio_id": espacio_id,
            "fecha_inicio": fecha.isoformat(),
            "fecha_fin": ev_data.get("fecha_fin"),
            "categorias": ev_data.get("categorias") or [],
            "categoria_principal": ev_data.get("categoria_principal") or "otro",
            "municipio": "medellin",
            "descripcion": ev_data.get("descripcion"),
            "imagen_url": ev_data.get("imagen_url"),
            "precio": ev_data.get("precio"),
            "es_gratuito": ev_data.get("es_gratuito", False),
            "fuente": "scraping_codigo_fallback",
            "fuente_url": fuente_url,
            "verificado": False,
            "hora_confirmada": False,
        }
        supabase.table("eventos").insert(evento_data).execute()
        inserted += 1

    return inserted


def _count_upcoming_events_for_lugar(espacio_id: str) -> int:
    hoy = _now_co().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    try:
        res = (
            supabase.table("eventos")
            .select("id", count="exact")
            .eq("espacio_id", espacio_id)
            .gte("fecha_inicio", hoy)
            .limit(1)
            .execute()
        )
        return int(res.count or 0)
    except Exception:
        return 0


def _sync_lugar_to_scraping_radar(lugar_id: str) -> None:
    """Ensure the lugar is tracked by smart scraping radar."""
    try:
        now_iso = _now_co().isoformat()
        supabase.table("scraping_state").upsert(
            {
                "lugar_id": lugar_id,
                "last_scraped_at": now_iso,
                "events_found": 0,
                "consecutive_empty": 0,
            },
            on_conflict="lugar_id",
        ).execute()
    except Exception:
        # Radar sync should not block registration flow if table is unavailable.
        pass

async def _extract_deterministically(url: str, is_instagram: bool) -> dict:
    """Extrae eventos usando código duro en lugar de LLMs."""
    data = {
        "tipo": "ambos",
        "espacio": None,
        "eventos": []
    }

    if is_instagram:
        ig_handle = _extract_ig_handle(url)
        clean_handle = ig_handle.replace(".", " ").replace("_", " ").title()
        
        data["espacio"] = {
            "nombre": clean_handle,
            "tipo": "colectivo",
            "categoria_principal": "otro",
            "categorias": [],
            "municipio": "medellin",
            "instagram_handle": f"@{ig_handle}",
            "sitio_web": url,
            "descripcion_corta": f"Colectivo cultural @{ig_handle}",
            "es_underground": True,
            "es_institucional": False,
        }
        
        # Extraer eventos con regex (prioridad: Meta API token -> Playwright fallback)
        from app.services.instagram_pw_scraper import fetch_ig_profile
        from app.services.ig_event_extractor import extract_events_from_ig_profile
        from app.services.auto_scraper import _fetch_ig_profile_via_meta_api
        
        try:
            profile = await _fetch_ig_profile_via_meta_api(ig_handle)
            if not profile:
                profile = await fetch_ig_profile(ig_handle)
            if profile and profile.get("captions"):
                events = extract_events_from_ig_profile(profile, clean_handle, "otro", "medellin")
                data["eventos"] = events
        except Exception as e:
            print(f"[scraper_llm] PW scraper error: {e}")
            
    else:
        # Extraer eventos de web con BeautifulSoup
        try:
            from app.services.playwright_fetcher import fetch_with_playwright, needs_playwright
            html = None
            if needs_playwright(url):
                html = await fetch_with_playwright(url)
            
            if not html:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    html = resp.text
            
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string if soup.title else url.split("//")[-1].split("/")[0]
            
            data["espacio"] = {
                "nombre": title[:100],
                "tipo": "espacio_fisico",
                "categoria_principal": "otro",
                "categorias": [],
                "municipio": "medellin",
                "sitio_web": url,
                "descripcion_corta": "Espacio cultural extraído desde la web.",
                "es_underground": False,
                "es_institucional": False,
            }
            
            events = extract_events_code(html, url, title, "otro", "medellin")
            if events:
                data["eventos"] = events
        except Exception as e:
            print(f"[scraper_llm] Web scraper error: {e}")

    return data

async def procesar_solicitud_scraping(solicitud_id: int) -> None:
    """Procesa una solicitud de usuario usando scrapers deterministas."""
    try:
        resp = supabase.table("solicitudes_registro").select("*").eq("id", solicitud_id).single().execute()
        solicitud = resp.data
        if not solicitud:
            return

        url = solicitud["url"]
        is_instagram = "instagram.com" in url

        supabase.table("solicitudes_registro").update({
            "estado": "procesando",
            "mensaje": "Analizando contenido con extractores de código determinista…",
        }).eq("id", solicitud_id).execute()

        # Extraer usando código
        data = await _extract_deterministically(url, is_instagram)

        if not data.get("eventos") and not is_instagram:
            supabase.table("solicitudes_registro").update({
                "estado": "fallido",
                "datos_extraidos": data,
                "mensaje": "No se encontraron eventos culturales en esta URL.",
            }).eq("id", solicitud_id).execute()
            return

        espacio = data.get("espacio") or {}
        if is_instagram and not espacio.get("instagram_handle"):
            handle = _extract_ig_handle(url)
            clean = re.sub(r"[^A-Za-z0-9._]", "", handle)
            espacio["instagram_handle"] = f"@{clean}" if clean else None
            espacio["nombre"] = espacio.get("nombre") or (clean or "Colectivo cultural")
            espacio["tipo"] = espacio.get("tipo") or "colectivo"

        if not espacio:
            raise RuntimeError("No se pudo extraer información base del colectivo/espacio")

        espacio_id = _upsert_lugar(espacio, url)
        _sync_lugar_to_scraping_radar(espacio_id)

        scraper_stats = None
        try:
            from app.services.auto_scraper import scrape_single_lugar
            scraper_stats = await scrape_single_lugar(espacio_id)
        except Exception as e:
            print(f"[scraper_llm] robust scrape error: {e}")

        fallback_inserted = 0
        if int((scraper_stats or {}).get("nuevos") or 0) == 0:
            fallback_inserted = _insert_fallback_events(
                data.get("eventos", []),
                espacio_id=espacio_id,
                fuente_url=url,
            )

        total_eventos_visibles = _count_upcoming_events_for_lugar(espacio_id)

        lugar_resp = (
            supabase.table("lugares")
            .select("id,slug,nombre,tipo,categoria_principal,instagram_handle,sitio_web,descripcion_corta")
            .eq("id", espacio_id)
            .single()
            .execute()
        )
        lugar = lugar_resp.data or {}
        ig_value = (lugar.get("instagram_handle") or "").strip()

        enriched_data = {
            **data,
            # Flat keys consumed by frontend registration result.
            "id": lugar.get("id") or espacio_id,
            "slug": lugar.get("slug"),
            "nombre": lugar.get("nombre") or espacio.get("nombre"),
            "tipo": lugar.get("tipo") or espacio.get("tipo"),
            "categoria_sugerida": lugar.get("categoria_principal") or espacio.get("categoria_principal"),
            "instagram_handle": ig_value.lstrip("@") if ig_value else None,
            "sitio_web": lugar.get("sitio_web") or espacio.get("sitio_web") or url,
            "descripcion_corta": lugar.get("descripcion_corta") or espacio.get("descripcion_corta"),
            "fuente": "scraping_codigo",
            "scraper_stats": scraper_stats or {},
            "fallback_eventos_insertados": fallback_inserted,
            "eventos_totales_lugar": total_eventos_visibles,
        }
        msg_exito = (
            "Espacio registrado/actualizado exitosamente. "
            f"Eventos nuevos scrapeados: {int((scraper_stats or {}).get('nuevos') or 0)}. "
            f"Fallback insertados: {fallback_inserted}. "
            f"Eventos próximos visibles en agenda para este lugar: {total_eventos_visibles}."
        )

        supabase.table("solicitudes_registro").update({
            "estado": "completado",
            "espacio_id": espacio_id,
            "datos_extraidos": enriched_data,
            "mensaje": msg_exito,
        }).eq("id", solicitud_id).execute()

    except Exception as exc:
        supabase.table("solicitudes_registro").update({
            "estado": "fallido",
            "mensaje": f"Error inesperado: {exc}\n{traceback.format_exc()}"[:1000],
        }).eq("id", solicitud_id).execute()
