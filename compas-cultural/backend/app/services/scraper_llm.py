"""
Scraper determinista (sin LLMs).
Extrae informacion cultural de URLs usando httpx + BeautifulSoup + Playwright + Regex.
Mantiene el nombre scraper_llm.py por compatibilidad, pero ya no usa inteligencia artificial.
"""
import traceback
from datetime import datetime
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
        
        # Extraer eventos con regex
        from app.services.instagram_pw_scraper import fetch_ig_profile
        from app.services.ig_event_extractor import extract_events_from_ig_profile
        
        try:
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

        espacio_id = None

        if data.get("espacio"):
            esp = data["espacio"]
            nombre = esp.get("nombre") or url
            slug = _slugify(nombre)

            existing = supabase.table("lugares").select("id").eq("slug", slug).execute()
            if existing.data:
                slug = slug + "-" + str(solicitud_id)

            lugar_data = {
                "nombre": nombre,
                "slug": slug,
                "tipo": esp.get("tipo") or "colectivo",
                "categorias": esp.get("categorias") or [],
                "categoria_principal": esp.get("categoria_principal") or "otro",
                "municipio": esp.get("municipio") or "medellin",
                "descripcion_corta": esp.get("descripcion_corta") or None,
                "instagram_handle": esp.get("instagram_handle") or None,
                "sitio_web": esp.get("sitio_web") or url,
                "es_underground": esp.get("es_underground") or False,
                "fuente_datos": "scraping_codigo",
                "nivel_actividad": "activo",
            }
            insert_resp = supabase.table("lugares").insert(lugar_data).execute()
            if insert_resp.data:
                espacio_id = insert_resp.data[0]["id"]

        now = _now_co()
        hoy_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)

        for ev_data in data.get("eventos", []):
            titulo = ev_data.get("titulo")
            if not titulo:
                continue

            fecha_str = ev_data.get("fecha_inicio")
            if not fecha_str:
                continue
                
            try:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha.tzinfo is None:
                    fecha = fecha.replace(tzinfo=CO_TZ)
                if fecha < hoy_inicio:
                    continue
            except (ValueError, TypeError):
                continue

            slug_ev = _slugify(titulo)
            existing_ev = supabase.table("eventos").select("id").eq("slug", slug_ev).execute()
            if existing_ev.data:
                slug_ev = slug_ev + "-" + str(solicitud_id)

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
                "fuente": "scraping_codigo",
                "fuente_url": url,
                "verificado": False,
                "hora_confirmada": ev_data.get("_hora_detectada", False),
            }
            supabase.table("eventos").insert(evento_data).execute()

        enriched_data = {**data}
        eventos_creados = len(data.get("eventos", []))
        msg_exito = f"Espacio registrado exitosamente con {eventos_creados} evento(s) extraído(s)."

        supabase.table("solicitudes_registro").update({
            "estado": "completado",
            "espacio_id": espacio_id,
            "datos_extraidos": enriched_data,
            "mensaje": msg_exito,
        }).eq("id", solicitud_id).execute()

        if espacio_id:
            try:
                from app.services.auto_scraper import scrape_single_lugar
                await scrape_single_lugar(espacio_id)
            except Exception:
                pass

    except Exception as exc:
        supabase.table("solicitudes_registro").update({
            "estado": "fallido",
            "mensaje": f"Error inesperado: {exc}\n{traceback.format_exc()}"[:1000],
        }).eq("id", solicitud_id).execute()
