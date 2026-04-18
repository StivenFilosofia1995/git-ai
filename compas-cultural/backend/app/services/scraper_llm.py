"""
Scraper basado en Claude LLM.
Extrae información cultural de URLs usando httpx + BeautifulSoup + Claude.
"""
import json
import re
import traceback
from datetime import datetime

import anthropic
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase

_CLIENT = anthropic.Anthropic(api_key=settings.anthropic_api_key)

EXTRACTION_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Analiza el contenido de esta página web y extrae información cultural estructurada.

URL original: {url}

Contenido extraído de la página:
---
{contenido}
---

Extrae la información en formato JSON con esta estructura exacta:
{{
  "tipo": "espacio" | "evento" | "ambos",
  "espacio": {{
    "nombre": "nombre del espacio o lugar",
    "tipo": "espacio_fisico | colectivo | festival | editorial | publicacion | programa_institucional | red_articuladora | sello_discografico",
    "categoria_principal": "teatro | hip_hop | jazz | musica_en_vivo | electronica | galeria | arte_contemporaneo | libreria | editorial | poesia | filosofia | cine | danza | circo | fotografia | casa_cultura | centro_cultural | festival | batalla_freestyle | muralismo | radio_comunitaria | publicacion | otro",
    "categorias": ["lista de categorias aplicables"],
    "municipio": "medellin | bello | itagui | envigado | sabaneta | caldas | la_estrella | copacabana | girardota | barbosa",
    "barrio": "nombre del barrio",
    "direccion": "dirección física",
    "descripcion_corta": "máximo 300 caracteres",
    "descripcion": "descripción completa",
    "instagram_handle": "@handle sin URL",
    "sitio_web": "URL del sitio",
    "telefono": "teléfono de contacto",
    "email": "correo electrónico",
    "es_underground": true/false,
    "es_institucional": true/false
  }},
  "eventos": [
    {{
      "titulo": "nombre del evento",
      "categoria_principal": "mismas opciones que arriba",
      "categorias": ["lista"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS (si es posible determinar la fecha)",
      "fecha_fin": "YYYY-MM-DDTHH:MM:SS (opcional)",
      "descripcion": "descripción del evento",
      "barrio": "barrio",
      "nombre_lugar": "dónde se realiza",
      "precio": "precio o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": "URL de la imagen o póster del evento (si existe)"
    }}
  ]
}}

Reglas:
- Si no puedes determinar un campo, usa null.
- Para fechas, solo incluye eventos FUTUROS (después de {fecha_actual}).
- Si la página NO tiene contenido cultural, responde: {{"tipo": "ninguno", "razon": "explicación"}}
- Responde SOLO con el JSON, sin texto adicional.
"""


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàäâ]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöô]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"[ñ]", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


async def _fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch page content with httpx and extract text with BS4. Returns (text, og_image_url)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract OG image before removing tags
    og_image = None
    og_tag = soup.find("meta", property="og:image")
    if og_tag and og_tag.get("content"):
        og_image = og_tag["content"]
    if not og_image:
        twitter_tag = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_tag and twitter_tag.get("content"):
            og_image = twitter_tag["content"]

    # Extract OG description for Instagram pages (often the only useful data)
    og_desc = ""
    og_desc_tag = soup.find("meta", property="og:description")
    if og_desc_tag and og_desc_tag.get("content"):
        og_desc = og_desc_tag["content"]
    og_title = ""
    og_title_tag = soup.find("meta", property="og:title")
    if og_title_tag and og_title_tag.get("content"):
        og_title = og_title_tag["content"]

    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # For Instagram URLs, the page is usually a login wall — enrich with OG meta
    if "instagram.com" in url:
        ig_handle = _extract_ig_handle(url)
        text = f"Instagram profile: @{ig_handle}\nOG Title: {og_title}\nOG Description: {og_desc}\n\n{text}"

    # Limit to 8000 chars to stay within Claude context
    return text[:8000], og_image


def _extract_ig_handle(url: str) -> str:
    """Extract Instagram handle from a URL."""
    # Clean query params and fragments
    clean = url.split("?")[0].split("#")[0].rstrip("/")
    parts = clean.split("/")
    # instagram.com/username or instagram.com/username/
    for i, part in enumerate(parts):
        if "instagram.com" in part and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else ""


def _extract_with_claude(url: str, page_text: str) -> dict:
    """Send page text to Claude for cultural data extraction."""
    prompt = EXTRACTION_PROMPT.format(
        url=url,
        contenido=page_text,
        fecha_actual=datetime.utcnow().isoformat(),
    )

    response = _CLIENT.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Try to extract JSON from response (Claude sometimes wraps in ```json)
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


async def procesar_solicitud_scraping(solicitud_id: int) -> None:
    """Background task: fetch URL, analyze with Claude, create records."""
    try:
        # Load solicitud
        resp = supabase.table("solicitudes_registro").select("*").eq("id", solicitud_id).single().execute()
        solicitud = resp.data
        if not solicitud:
            return

        # Update status
        supabase.table("solicitudes_registro").update({
            "estado": "procesando",
            "mensaje": "Descargando contenido de la URL…",
        }).eq("id", solicitud_id).execute()

        # Fetch page
        page_text, og_image = await _fetch_page(solicitud["url"])

        supabase.table("solicitudes_registro").update({
            "mensaje": "Analizando contenido con inteligencia artificial…",
        }).eq("id", solicitud_id).execute()

        # Analyze with Claude
        data = _extract_with_claude(solicitud["url"], page_text)

        if data.get("tipo") == "ninguno":
            supabase.table("solicitudes_registro").update({
                "estado": "fallido",
                "datos_extraidos": data,
                "mensaje": f"No se encontró contenido cultural: {data.get('razon', 'desconocido')}",
            }).eq("id", solicitud_id).execute()
            return

        espacio_id = None

        # Create lugar if present
        if data.get("espacio") and data["tipo"] in ("espacio", "ambos"):
            esp = data["espacio"]
            nombre = esp.get("nombre", "Sin nombre")
            slug = _slugify(nombre)

            # Check for duplicates
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
                "barrio": esp.get("barrio") or None,
                "direccion": esp.get("direccion") or None,
                "descripcion_corta": (esp.get("descripcion_corta") or "")[:300] or None,
                "descripcion": esp.get("descripcion") or None,
                "instagram_handle": esp.get("instagram_handle") or None,
                "sitio_web": esp.get("sitio_web") or solicitud["url"],
                "telefono": esp.get("telefono") or None,
                "email": esp.get("email") or None,
                "es_underground": esp.get("es_underground") or False,
                "es_institucional": esp.get("es_institucional") or False,
                "fuente_datos": "scraping_llm",
                "nivel_actividad": "activo",
            }
            # Ensure municipio is never null (DB NOT NULL constraint)
            if not lugar_data["municipio"]:
                lugar_data["municipio"] = "medellin"

            # If source is Instagram, ensure handle is set
            if "instagram.com" in solicitud["url"]:
                if not lugar_data["instagram_handle"]:
                    handle = _extract_ig_handle(solicitud["url"])
                    if handle:
                        lugar_data["instagram_handle"] = f"@{handle}"
                if not lugar_data["sitio_web"] or "instagram.com" in lugar_data["sitio_web"]:
                    lugar_data["sitio_web"] = solicitud["url"]
            insert_resp = supabase.table("lugares").insert(lugar_data).execute()
            if insert_resp.data:
                espacio_id = insert_resp.data[0]["id"]

        # Create events if present
        now = datetime.utcnow()
        for ev_data in data.get("eventos", []):
            titulo = ev_data.get("titulo")
            if not titulo:
                continue

            fecha_str = ev_data.get("fecha_inicio")
            if fecha_str:
                try:
                    fecha = datetime.fromisoformat(fecha_str)
                    if fecha < now:
                        continue
                except (ValueError, TypeError):
                    fecha = now
            else:
                fecha = now

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
                "municipio": ev_data.get("municipio") or (data.get("espacio") or {}).get("municipio") or "medellin",
                "barrio": ev_data.get("barrio"),
                "nombre_lugar": ev_data.get("nombre_lugar"),
                "descripcion": ev_data.get("descripcion"),
                "imagen_url": ev_data.get("imagen_url") or og_image,
                "precio": ev_data.get("precio"),
                "es_gratuito": ev_data.get("es_gratuito", False),
                "es_recurrente": ev_data.get("es_recurrente", False),
                "fuente": "scraping_llm",
                "fuente_url": solicitud["url"],
                "verificado": False,
            }
            supabase.table("eventos").insert(evento_data).execute()

        # Enrich datos_extraidos with the slug and nombre for the frontend
        enriched_data = {**data}
        if data.get("espacio"):
            esp_name = data["espacio"].get("nombre", "")
            enriched_data["slug"] = _slugify(esp_name) if esp_name else None
            # If we created a lugar, use the actual slug that was inserted
            if espacio_id:
                try:
                    lugar_row = supabase.table("lugares").select("slug").eq("id", espacio_id).single().execute()
                    if lugar_row.data:
                        enriched_data["slug"] = lugar_row.data["slug"]
                except Exception:
                    pass
            enriched_data["nombre"] = data["espacio"].get("nombre")
            enriched_data["categoria_sugerida"] = data["espacio"].get("categoria_principal")
            enriched_data["instagram_handle"] = data["espacio"].get("instagram_handle")
            enriched_data["sitio_web"] = data["espacio"].get("sitio_web")
            enriched_data["descripcion_corta"] = data["espacio"].get("descripcion_corta")
            enriched_data["fuente"] = "scraping_llm"

        supabase.table("solicitudes_registro").update({
            "estado": "completado",
            "espacio_id": espacio_id,
            "datos_extraidos": enriched_data,
            "mensaje": "Datos extraídos exitosamente con IA.",
        }).eq("id", solicitud_id).execute()

        # Conectar el espacio recién creado al sistema de scraping activo
        if espacio_id:
            try:
                from app.services.auto_scraper import scrape_single_lugar
                await scrape_single_lugar(espacio_id)
            except Exception:
                pass  # No bloquear si falla el primer scrape

    except httpx.HTTPError as exc:
        _marcar_error(solicitud_id, f"Error al descargar la URL: {exc}")
    except json.JSONDecodeError:
        _marcar_error(solicitud_id, "Error al interpretar la respuesta de IA.")
    except Exception as exc:
        _marcar_error(solicitud_id, f"Error inesperado: {exc}\n{traceback.format_exc()}")


def _marcar_error(solicitud_id: int, mensaje: str) -> None:
    supabase.table("solicitudes_registro").update({
        "estado": "fallido",
        "mensaje": mensaje[:1000],
    }).eq("id", solicitud_id).execute()
