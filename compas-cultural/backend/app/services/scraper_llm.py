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
      "es_recurrente": true/false
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


async def _fetch_page(url: str) -> str:
    """Fetch page content with httpx and extract text with BS4."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Limit to 8000 chars to stay within Claude context
    return text[:8000]


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
        page_text = await _fetch_page(solicitud["url"])

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
                "tipo": esp.get("tipo", "espacio_fisico"),
                "categorias": esp.get("categorias", []),
                "categoria_principal": esp.get("categoria_principal", "otro"),
                "municipio": esp.get("municipio", "medellin"),
                "barrio": esp.get("barrio"),
                "direccion": esp.get("direccion"),
                "descripcion_corta": esp.get("descripcion_corta"),
                "descripcion": esp.get("descripcion"),
                "instagram_handle": esp.get("instagram_handle"),
                "sitio_web": esp.get("sitio_web") or solicitud["url"],
                "telefono": esp.get("telefono"),
                "email": esp.get("email"),
                "es_underground": esp.get("es_underground", False),
                "es_institucional": esp.get("es_institucional", False),
                "fuente_datos": "scraping_llm",
                "nivel_actividad": "activo",
            }
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
                "categorias": ev_data.get("categorias", []),
                "categoria_principal": ev_data.get("categoria_principal", "otro"),
                "municipio": data.get("espacio", {}).get("municipio", "medellin"),
                "barrio": ev_data.get("barrio"),
                "nombre_lugar": ev_data.get("nombre_lugar"),
                "descripcion": ev_data.get("descripcion"),
                "precio": ev_data.get("precio"),
                "es_gratuito": ev_data.get("es_gratuito", False),
                "es_recurrente": ev_data.get("es_recurrente", False),
                "fuente": "scraping_llm",
                "fuente_url": solicitud["url"],
                "verificado": False,
            }
            supabase.table("eventos").insert(evento_data).execute()

        supabase.table("solicitudes_registro").update({
            "estado": "completado",
            "espacio_id": espacio_id,
            "datos_extraidos": data,
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
