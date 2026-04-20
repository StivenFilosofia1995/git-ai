"""
Scraper basado en Groq AI (gratis) + Smart Listener.
Extrae información cultural de URLs usando:
- Meta Graph API (Instagram Business Discovery) + Groq Vision (flyer images)
- httpx + BeautifulSoup + Groq Llama (websites)
- RSS auto-discovery
Claude se usa SOLO como fallback si Groq falla.
"""
import json
import re
import asyncio
import traceback
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import supabase
from app.services.groq_client import groq_chat, parse_json_response, MODEL_FAST, MODEL_SMART

EXTRACTION_PROMPT = """Eres un experto en cultura urbana del Valle de Aburrá (Medellín, Colombia).
Hoy es {fecha_actual}.

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
    "categoria_principal": "teatro | hip_hop | jazz | rock | musica_en_vivo | electronica | galeria | arte_contemporaneo | libreria | editorial | poesia | filosofia | cine | danza | circo | fotografia | casa_cultura | centro_cultural | festival | batalla_freestyle | muralismo | radio_comunitaria | publicacion | otro",
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
- "Este sábado", "mañana", "el viernes" → calcula la fecha real desde hoy.
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


def _extract_ig_handle(url: str) -> str:
    """Extract Instagram handle from a URL."""
    clean = url.split("?")[0].split("#")[0].rstrip("/")
    parts = clean.split("/")
    for i, part in enumerate(parts):
        if "instagram.com" in part and i + 1 < len(parts):
            return parts[i + 1]
    return parts[-1] if parts else ""


async def _fetch_page(url: str) -> tuple[str, str | None]:
    """Fetch page content with httpx and extract text with BS4. Returns (text, og_image_url)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

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

    if "instagram.com" in url:
        ig_handle = _extract_ig_handle(url)
        text = f"Instagram profile: @{ig_handle}\nOG Title: {og_title}\nOG Description: {og_desc}\n\n{text}"

    return text[:8000], og_image


async def _fetch_instagram_smart(url: str) -> tuple[dict | None, list[dict]]:
    """Smart Instagram extraction using Meta Graph API + Claude Vision.
    Returns (espacio_data, events_list).
    """
    handle = _extract_ig_handle(url)
    if not handle:
        return None, []

    from app.services.smart_listener import fetch_ig_posts_with_images, analyze_image_with_vision, _analyze_caption_only, _might_be_event_post

    # Fetch posts via Meta Graph API
    posts = await fetch_ig_posts_with_images(handle)

    espacio_data = None
    events = []

    if posts:
        # Extract espacio info from bio/first posts
        bio_text = ""
        all_captions = []
        for p in posts:
            cap = p.get("caption", "")
            if cap:
                all_captions.append(cap)

        combined_text = "\n---\n".join(all_captions[:5])

        # Use Claude to extract espacio info from combined captions
        if combined_text:
            espacio_data = await _extract_espacio_from_ig(handle, combined_text)

        # Extract events from posts (Vision + text)
        vision_count = 0
        max_vision = 5

        for post in posts:
            caption = post.get("caption", "")
            image_url = post.get("image_url", "")
            permalink = post.get("permalink", "")

            # Skip old posts
            timestamp = post.get("timestamp", "")
            if timestamp:
                try:
                    post_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00").split("+")[0])
                    if post_date < datetime.utcnow() - timedelta(days=30):
                        continue
                except (ValueError, TypeError):
                    pass

            if not _might_be_event_post(caption) and not image_url:
                continue

            # Use Vision for image posts
            if image_url and vision_count < max_vision:
                evs = await analyze_image_with_vision(
                    image_url, caption,
                    espacio_data.get("nombre", handle) if espacio_data else handle,
                    espacio_data.get("municipio", "medellin") if espacio_data else "medellin",
                )
                vision_count += 1
                for ev in evs:
                    ev["fuente_url"] = permalink
                    ev["imagen_url"] = image_url
                events.extend(evs)
                if evs:
                    continue

            # Text-only for substantial captions
            if caption and len(caption) > 50:
                evs = await _analyze_caption_only(
                    caption,
                    espacio_data.get("nombre", handle) if espacio_data else handle,
                    espacio_data.get("municipio", "medellin") if espacio_data else "medellin",
                )
                for ev in evs:
                    ev["fuente_url"] = permalink
                    if image_url:
                        ev["imagen_url"] = image_url
                events.extend(evs)

    else:
        # Meta API failed — try basic page scrape for at least the OG data
        try:
            page_text, og_image = await _fetch_page(url)
            if page_text and len(page_text) > 50:
                espacio_data = {
                    "nombre": handle,
                    "instagram_handle": f"@{handle}",
                    "tipo": "colectivo",
                    "municipio": "medellin",
                }
        except Exception:
            pass

    return espacio_data, events


async def _extract_espacio_from_ig(handle: str, captions_text: str) -> dict | None:
    """Extract espacio/colectivo info from Instagram captions + bio using Groq (free)."""
    default = {"nombre": handle, "instagram_handle": f"@{handle}", "tipo": "colectivo", "municipio": "medellin"}

    if not settings.groq_api_key and not settings.anthropic_api_key:
        return default

    # Try to fetch bio from Meta API for richer context
    bio_text = ""
    try:
        if settings.meta_access_token and settings.meta_ig_business_account_id:
            async with httpx.AsyncClient(timeout=10) as client:
                ig_account_id = settings.meta_ig_business_account_id
                resp = await client.get(
                    f"https://graph.facebook.com/v21.0/{ig_account_id}",
                    params={
                        "fields": f"business_discovery.fields(biography,name,website,followers_count).username({handle})",
                        "access_token": settings.meta_access_token,
                    }
                )
                if resp.status_code == 200:
                    bd = resp.json().get("business_discovery", {})
                    bio = bd.get("biography", "")
                    name = bd.get("name", "")
                    website = bd.get("website", "")
                    followers = bd.get("followers_count", 0)
                    if bio:
                        bio_text = f"\nBIO de Instagram: {bio}"
                    if name:
                        bio_text += f"\nNombre de perfil: {name}"
                    if website:
                        bio_text += f"\nSitio web: {website}"
                    if followers:
                        bio_text += f"\nSeguidores: {followers}"
    except Exception:
        pass

    now_co = datetime.utcnow() - timedelta(hours=5)
    prompt = f"""Analiza estos posts de Instagram de @{handle} y extrae información del espacio/colectivo cultural.
{bio_text}

Posts recientes:
---
{captions_text[:4000]}
---

Responde con JSON:
{{
  "nombre": "nombre REAL del espacio/colectivo (usa el nombre de perfil o el que aparezca consistentemente en posts, NO uses @{handle} si hay un nombre mejor)",
  "tipo": "espacio_fisico | colectivo | festival | editorial | sello_discografico | plataforma_digital | red_articuladora | programa_institucional | otro",
  "categoria_principal": "teatro|hip_hop|jazz|rock|musica_en_vivo|electronica|galeria|arte_contemporaneo|libreria|poesia|fotografia|festival|taller|conferencia|filosofia|otro",
  "categorias": ["lista de TODAS las categorias que apliquen"],
  "municipio": "medellin|bello|itagui|envigado|sabaneta|caldas|la_estrella|copacabana|girardota|barbosa",
  "barrio": "barrio si se menciona en bio/posts, o null",
  "direccion": "dirección física si se menciona, o null",
  "descripcion_corta": "descripción concisa e informativa de qué es y qué hace (máx 250 chars)",
  "sitio_web": "URL del sitio web si aparece en bio, o null",
  "es_underground": true/false,
  "es_institucional": true/false
}}

REGLAS:
- Si la bio menciona dirección o barrio, extráelo.
- Si mencionan "Medellín", "Envigado", "Itagüí", etc., usa ese municipio.
- "underground" = independiente/alternativo, sin apoyo gubernamental.
- "institucional" = bibliotecas públicas, museos, centros culturales municipales.
- Infiere el tipo: organizan eventos → colectivo, lugar físico → espacio_fisico, publican libros → editorial.

Solo JSON, sin texto adicional.
"""
    try:
        raw = None

        # ── PRIMARY: Groq (free) ──
        if settings.groq_api_key:
            raw = await asyncio.to_thread(groq_chat, prompt, MODEL_FAST, 800, 0, True)

        # ── FALLBACK: Claude Haiku ──
        if not raw and settings.anthropic_api_key:
            import anthropic
            def _claude_call():
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=800, temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
            raw = await asyncio.to_thread(_claude_call)

        data = parse_json_response(raw)
        if data and isinstance(data, dict):
            data["instagram_handle"] = f"@{handle}"
            return data
        return default
    except Exception as e:
        print(f"  [IG Espacio] Error: {e}")
        return default


def _extract_with_llm(url: str, page_text: str) -> dict:
    """Send page text to Groq (free) for cultural data extraction. Falls back to Claude."""
    now_co = datetime.utcnow() - timedelta(hours=5)
    prompt = EXTRACTION_PROMPT.format(
        url=url,
        contenido=page_text,
        fecha_actual=now_co.strftime("%Y-%m-%d %H:%M"),
    )

    # ── PRIMARY: Groq (free) ──
    if settings.groq_api_key:
        raw = groq_chat(prompt, MODEL_SMART, 1500, 0.1, True)
        data = parse_json_response(raw)
        if data:
            return data

    # ── FALLBACK: Claude ──
    if settings.anthropic_api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1500, temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        data = parse_json_response(raw)
        if data:
            return data

    return {"tipo": "ninguno", "razon": "No AI provider available"}


async def procesar_solicitud_scraping(solicitud_id: int) -> None:
    """Background task: fetch URL, analyze with Smart Listener + Claude Vision."""
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
            "mensaje": "Conectando con la fuente…" if is_instagram else "Descargando contenido de la URL…",
        }).eq("id", solicitud_id).execute()

        data = None
        og_image = None
        ig_events = []

        if is_instagram:
            # ═══ SMART INSTAGRAM FLOW ═══
            # Use Meta Graph API + Claude Vision instead of basic scraping
            supabase.table("solicitudes_registro").update({
                "mensaje": "Leyendo posts de Instagram con IA visual…",
            }).eq("id", solicitud_id).execute()

            espacio_data, ig_events = await _fetch_instagram_smart(url)

            if espacio_data:
                # Build data structure compatible with the rest of the function
                data = {
                    "tipo": "ambos" if ig_events else "espacio",
                    "espacio": espacio_data,
                    "eventos": [],  # We'll insert ig_events separately
                }
            else:
                # Fallback: try basic page scrape
                try:
                    page_text, og_image = await _fetch_page(url)
                    supabase.table("solicitudes_registro").update({
                        "mensaje": "Analizando contenido con inteligencia artificial…",
                    }).eq("id", solicitud_id).execute()
                    data = await asyncio.to_thread(_extract_with_llm, url, page_text)
                except Exception:
                    # Last resort: create minimal espacio from handle
                    handle = _extract_ig_handle(url)
                    data = {
                        "tipo": "espacio",
                        "espacio": {
                            "nombre": handle,
                            "tipo": "colectivo",
                            "instagram_handle": f"@{handle}",
                            "municipio": "medellin",
                            "descripcion_corta": f"Colectivo cultural @{handle}",
                        },
                        "eventos": [],
                    }
        else:
            # ═══ WEBSITE FLOW ═══
            page_text, og_image = await _fetch_page(url)

            supabase.table("solicitudes_registro").update({
                "mensaje": "Analizando contenido con inteligencia artificial…",
            }).eq("id", solicitud_id).execute()

            data = await asyncio.to_thread(_extract_with_llm, url, page_text)

            # Also try RSS discovery for automatic future listening
            try:
                from app.services.smart_listener import discover_rss_feed
                feed_url = await discover_rss_feed(url)
                if feed_url:
                    print(f"  [RSS] Feed descubierto: {feed_url}")
                    # Store feed URL for future auto-scraping
                    if data and data.get("espacio"):
                        data["espacio"]["rss_feed"] = feed_url
            except Exception:
                pass

        if not data:
            supabase.table("solicitudes_registro").update({
                "estado": "fallido",
                "mensaje": "No se pudo extraer información de esta URL.",
            }).eq("id", solicitud_id).execute()
            return

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
            enriched_data["fuente"] = "smart_listener" if is_instagram else "scraping_llm"

        # Insert events from Smart Listener (Vision/caption analysis)
        now_co = datetime.utcnow() - timedelta(hours=5)
        ig_events_inserted = 0
        for ev in ig_events:
            titulo = ev.get("titulo")
            if not titulo:
                continue
            fecha_str = ev.get("fecha_inicio")
            if not fecha_str:
                continue
            try:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha < now_co:
                    continue
            except (ValueError, TypeError):
                continue

            slug_ev = _slugify(titulo)
            existing_ev = supabase.table("eventos").select("id").eq("slug", slug_ev).execute()
            if existing_ev.data:
                continue  # Skip duplicate

            evento_data = {
                "titulo": titulo[:200],
                "slug": slug_ev,
                "espacio_id": espacio_id,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": ev.get("fecha_fin"),
                "categorias": ev.get("categorias") or [],
                "categoria_principal": ev.get("categoria_principal") or "otro",
                "municipio": ev.get("municipio") or (data.get("espacio") or {}).get("municipio") or "medellin",
                "barrio": ev.get("barrio"),
                "nombre_lugar": ev.get("nombre_lugar") or (data.get("espacio") or {}).get("nombre"),
                "descripcion": ev.get("descripcion"),
                "imagen_url": ev.get("imagen_url"),
                "precio": ev.get("precio"),
                "es_gratuito": ev.get("es_gratuito", False),
                "es_recurrente": False,
                "fuente": ev.get("fuente", "smart_listener_vision"),
                "fuente_url": ev.get("fuente_url") or solicitud["url"],
                "verificado": False,
            }
            try:
                supabase.table("eventos").insert(evento_data).execute()
                ig_events_inserted += 1
            except Exception as e:
                print(f"  [REG] Error inserting event: {e}")

        total_events = len(data.get("eventos", [])) + ig_events_inserted
        enriched_data["eventos_encontrados"] = total_events

        supabase.table("solicitudes_registro").update({
            "estado": "completado",
            "espacio_id": espacio_id,
            "datos_extraidos": enriched_data,
            "mensaje": f"✓ Espacio registrado{f' + {total_events} evento(s) encontrado(s)' if total_events else ''}. La IA escuchará automáticamente nuevos eventos.",
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
        _marcar_error(solicitud_id, "Error al interpretar la respuesta de IA. Intenta de nuevo.")
    except Exception as exc:
        _marcar_error(solicitud_id, f"Error inesperado: {exc}\n{traceback.format_exc()}")


def _marcar_error(solicitud_id: int, mensaje: str) -> None:
    supabase.table("solicitudes_registro").update({
        "estado": "fallido",
        "mensaje": mensaje[:1000],
    }).eq("id", solicitud_id).execute()
