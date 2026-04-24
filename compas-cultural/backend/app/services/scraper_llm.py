"""
Scraper basado en LLM.
Extrae informacion cultural de URLs usando httpx + BeautifulSoup + Ollama local.
"""
import json
import re
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.gemini_client import gemini_chat
from app.services.groq_client import groq_chat, MODEL_FAST
from app.services.ollama_client import ollama_chat

CO_TZ = ZoneInfo("America/Bogota")

def _now_co() -> datetime:
    return datetime.now(CO_TZ)

EXTRACTION_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Analiza el contenido de esta página web o perfil de Instagram y extrae información cultural estructurada.

URL original: {url}

Contenido extraído:
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
      "descripcion": "descripción del evento (usa el texto del post si viene de Instagram)",
      "barrio": "barrio",
      "nombre_lugar": "dónde se realiza",
      "precio": "precio o 'Entrada libre'",
      "es_gratuito": true/false,
      "es_recurrente": true/false,
      "imagen_url": "URL de la imagen del post si viene de Instagram"
    }}
  ]
}}

Reglas IMPORTANTES para Instagram:
- Si el contenido viene de posts de Instagram (marcados como [POST N]):
  * Analiza CADA post y decide si es un evento (tiene fecha, hora, lugar, convocatoria) o no
  * Si es evento: inclúyelo en "eventos" con toda la info disponible
  * Si NO es evento (promoción, opinión, foto cotidiana): ignóralo, no lo incluyas
  * Para fechas relativas (ej: "este sábado", "25 de abril"): calcula la fecha absoluta desde hoy {fecha_actual}
  * Si no hay fecha clara, usa null en fecha_inicio (igual inclúyelo como evento si es evidente)
  * Para "imagen_url": usa la URL [IMAGE_URL] del mismo post si aparece, o null
- Si el tipo de espacio no está claro pero es Instagram de un colectivo cultural, usa tipo="colectivo"
- Si municipio no está claro, asume "medellin"
- Incluye TANTO el espacio como los eventos (tipo="ambos") cuando sea Instagram de un lugar cultural
- Si el contenido dice que Instagram bloqueó el acceso, IGUAL registra el espacio con los datos del handle:
  * nombre = el handle limpio (ej: "Refugios CO" de @refugios.co)
  * tipo = "colectivo"
  * instagram_handle = @handle
  * municipio = "medellin"
  * Devuelve tipo="espacio" (sin eventos)
- Para fechas, incluye eventos FUTUROS y presentes (a partir de {fecha_actual}); si la fecha es null, NO incluyas el evento.
- Si un evento NO tiene fecha clara, NO lo incluyas. No inventes fechas ni asumas que es hoy.
- Si la página NO tiene contenido cultural (no es IG de un colectivo/espacio/evento), responde: {{"tipo": "ninguno", "razon": "explicación"}}
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


async def _fetch_ig_profile_data(handle: str) -> tuple[str, str | None, list[str], list[str]]:
    """
    Try every available strategy to fetch Instagram profile data.
    Returns (text_for_llm, first_image_url, all_image_urls, permalink_urls).
    Never raises — always returns something usable.
    """
    clean = handle.lstrip("@").strip().split("/")[0]
    profile: dict | None = None

    # 1. Meta Graph API (best quality, needs credentials)
    try:
        from app.services.auto_scraper import _fetch_ig_profile_via_meta_api
        profile = await _fetch_ig_profile_via_meta_api(clean)
    except Exception as e:
        print(f"[scraper_llm] Meta API error: {e}")

    # 2. instagram_pw_scraper cascade (httpx-api → httpx-html → playwright)
    if not profile or not (profile.get("captions") or profile.get("biography")):
        try:
            from app.services.instagram_pw_scraper import fetch_ig_profile
            profile = await fetch_ig_profile(clean)
        except Exception as e:
            print(f"[scraper_llm] PW scraper error: {e}")

    if profile and (profile.get("captions") or profile.get("biography")):
        from app.services.instagram_pw_scraper import profile_to_scraper_text
        text = f"Instagram profile: @{clean}\n\n{profile_to_scraper_text(profile, clean)}"
        images = profile.get("image_urls", [])
        perms = profile.get("permalink_urls", [])
        first_img = images[0] if images else None
        return text[:8000], first_img, images[:8], perms[:8]

    # All strategies failed — return enough for a minimal colectivo record
    text = (
        f"Instagram profile: @{clean}\n"
        f"[Contenido no disponible — Instagram bloqueó el acceso público]\n"
        f"Registrar como colectivo cultural con handle @{clean} en Medellín."
    )
    return text[:8000], None, [], []


async def _fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch page content. For Instagram, uses multi-strategy scraper."""

    # ── Instagram: use full cascade ────────────────────────────────────────
    if "instagram.com" in url:
        ig_handle = _extract_ig_handle(url)
        text, first_img, _, _ = await _fetch_ig_profile_data(ig_handle)
        return text, first_img

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Error al descargar la URL: {e}") from e

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

    og_desc = ""
    og_desc_tag = soup.find("meta", property="og:description")
    if og_desc_tag and og_desc_tag.get("content"):
        og_desc = og_desc_tag["content"]
    og_title = ""
    og_title_tag = soup.find("meta", property="og:title")
    if og_title_tag and og_title_tag.get("content"):
        og_title = og_title_tag["content"]

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # For Facebook pages, prepend OG meta
    if "facebook.com" in url:
        text = f"Facebook page: {url}\nOG Title: {og_title}\nOG Description: {og_desc}\n\n{text}"

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


def _extract_with_llm(url: str, page_text: str) -> dict:
    """Extract cultural data with Ollama-first strategy and provider fallbacks."""
    now_co = _now_co()
    prompt = EXTRACTION_PROMPT.format(
        url=url,
        contenido=page_text,
        fecha_actual=now_co.isoformat(),
    )

    def _parse_json(raw: str) -> dict:
        clean = (raw or "").strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        return json.loads(clean)

    # 1) Ollama local
    raw = ollama_chat(
        system_prompt="Extrae datos culturales y responde solo JSON valido.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.0,
    )
    if raw:
        try:
            return _parse_json(raw)
        except Exception as e:
            print(f"[scraper_llm] Ollama JSON inválido: {e}")

    # 2) Groq fallback
    raw_groq = groq_chat(
        prompt=prompt,
        model=MODEL_FAST,
        max_tokens=1800,
        temperature=0,
        json_mode=True,
    )
    if raw_groq:
        try:
            return _parse_json(raw_groq)
        except Exception as e:
            print(f"[scraper_llm] Groq JSON inválido: {e}")

    # 3) Gemini fallback
    if settings.gemini_api_key:
        raw_gemini = gemini_chat(
            system_prompt="Extrae datos culturales y responde solo JSON valido.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0,
        )
        if raw_gemini:
            try:
                return _parse_json(raw_gemini)
            except Exception as e:
                print(f"[scraper_llm] Gemini JSON inválido: {e}")

    raise RuntimeError("No fue posible extraer datos con Ollama/Groq/Gemini")


async def procesar_solicitud_scraping(solicitud_id: int) -> None:
    """Background task: fetch URL, analyze with LLM, create records."""
    try:
        # Load solicitud
        resp = supabase.table("solicitudes_registro").select("*").eq("id", solicitud_id).single().execute()
        solicitud = resp.data
        if not solicitud:
            return

        url = solicitud["url"]
        is_instagram = "instagram.com" in url

        # Update status
        supabase.table("solicitudes_registro").update({
            "estado": "procesando",
            "mensaje": "Descargando contenido de la URL…",
        }).eq("id", solicitud_id).execute()

        # For Instagram: use full cascade and capture all post images
        ig_profile_images: list[str] = []
        ig_permalink_urls: list[str] = []
        og_image: str | None = None

        if is_instagram:
            ig_handle = _extract_ig_handle(url)
            page_text, og_image, ig_profile_images, ig_permalink_urls = await _fetch_ig_profile_data(ig_handle)
        else:
            page_text, og_image = await _fetch_page(url)

        supabase.table("solicitudes_registro").update({
            "mensaje": "Analizando contenido con inteligencia artificial…",
        }).eq("id", solicitud_id).execute()

        # Analyze with Groq LLM
        data = _extract_with_llm(url, page_text)

        # For Instagram: if LLM says "ninguno" but we have a handle → override and create minimal record
        if data.get("tipo") == "ninguno" and is_instagram:
            ig_handle = _extract_ig_handle(url)
            nombre_limpio = ig_handle.replace(".", " ").replace("_", " ").title()
            data = {
                "tipo": "espacio",
                "espacio": {
                    "nombre": nombre_limpio,
                    "tipo": "colectivo",
                    "categoria_principal": "otro",
                    "categorias": [],
                    "municipio": "medellin",
                    "instagram_handle": f"@{ig_handle}",
                    "sitio_web": url,
                    "descripcion_corta": f"Colectivo cultural @{ig_handle}",
                    "es_underground": True,
                    "es_institucional": False,
                },
                "eventos": [],
            }
            print(f"[scraper_llm] IG fallback: creando colectivo mínimo para @{ig_handle}")

        elif data.get("tipo") == "ninguno":
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
            nombre = esp.get("nombre") or _extract_ig_handle(url).replace(".", " ").replace("_", " ").title()
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
                "sitio_web": esp.get("sitio_web") or url,
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
            if is_instagram:
                handle = _extract_ig_handle(url)
                if not lugar_data["instagram_handle"] and handle:
                    lugar_data["instagram_handle"] = f"@{handle}"
                if not lugar_data["sitio_web"] or "instagram.com" in lugar_data["sitio_web"]:
                    lugar_data["sitio_web"] = url
            insert_resp = supabase.table("lugares").insert(lugar_data).execute()
            if insert_resp.data:
                espacio_id = insert_resp.data[0]["id"]

        # Create events if present
        now = _now_co()
        hoy_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Next week as default date for IG events without a clear date
        proxima_semana = now + timedelta(days=7)

        for idx, ev_data in enumerate(data.get("eventos", [])):
            titulo = ev_data.get("titulo")
            if not titulo:
                continue

            fecha_str = ev_data.get("fecha_inicio")
            fecha_fin_ev: datetime | None = None
            skip_event = False

            if fecha_str:
                try:
                    fecha = datetime.fromisoformat(fecha_str)
                    if fecha.tzinfo is None:
                        fecha = fecha.replace(tzinfo=CO_TZ)
                    # Resolve fecha_fin
                    if ev_data.get("fecha_fin"):
                        try:
                            fecha_fin_ev = datetime.fromisoformat(ev_data["fecha_fin"])
                            if fecha_fin_ev.tzinfo is None:
                                fecha_fin_ev = fecha_fin_ev.replace(tzinfo=CO_TZ)
                        except (ValueError, TypeError):
                            pass
                    # Skip only fully past events
                    if fecha < hoy_inicio:
                        if fecha_fin_ev is None or fecha_fin_ev < hoy_inicio:
                            skip_event = True
                except (ValueError, TypeError):
                    skip_event = True  # Unparseable date — skip
            else:
                # No date at all — skip this event
                skip_event = True
            if skip_event:
                continue

            slug_ev = _slugify(titulo)
            existing_ev = supabase.table("eventos").select("id").eq("slug", slug_ev).execute()
            if existing_ev.data:
                slug_ev = slug_ev + "-" + str(solicitud_id)

            # For IG posts: try to use post-specific image in order (idx matches post order)
            evento_imagen = ev_data.get("imagen_url")
            if not evento_imagen and ig_profile_images:
                evento_imagen = ig_profile_images[idx] if idx < len(ig_profile_images) else ig_profile_images[0]
            if not evento_imagen:
                evento_imagen = og_image

            # For IG posts: use permalink as fuente_url if available
            fuente_url_ev = url
            if ig_permalink_urls and idx < len(ig_permalink_urls) and ig_permalink_urls[idx]:
                fuente_url_ev = ig_permalink_urls[idx]

            evento_data = {
                "titulo": titulo,
                "slug": slug_ev,
                "espacio_id": espacio_id,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": fecha_fin_ev.isoformat() if fecha_fin_ev else ev_data.get("fecha_fin"),
                "categorias": ev_data.get("categorias") or [],
                "categoria_principal": ev_data.get("categoria_principal") or "otro",
                "municipio": ev_data.get("municipio") or (data.get("espacio") or {}).get("municipio") or "medellin",
                "barrio": ev_data.get("barrio"),
                "nombre_lugar": ev_data.get("nombre_lugar") or (data.get("espacio") or {}).get("nombre"),
                "descripcion": ev_data.get("descripcion"),
                "imagen_url": evento_imagen,
                "precio": ev_data.get("precio"),
                "es_gratuito": ev_data.get("es_gratuito", False),
                "es_recurrente": ev_data.get("es_recurrente", False),
                "fuente": "scraping_llm",
                "fuente_url": fuente_url_ev,
                "verificado": False,
                "hora_confirmada": False,
            }
            supabase.table("eventos").insert(evento_data).execute()

        # Enrich datos_extraidos with the slug and nombre for the frontend
        enriched_data = {**data}
        eventos_creados = len(data.get("eventos", []))
        msg_exito = "Colectivo registrado exitosamente."
        if eventos_creados:
            msg_exito = f"Colectivo registrado con {eventos_creados} evento(s) extraído(s)."
        elif is_instagram:
            msg_exito = "Colectivo registrado. Sus eventos aparecerán cuando Instagram permita el acceso."

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
            "mensaje": msg_exito,
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
