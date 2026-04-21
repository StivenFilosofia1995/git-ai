import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
import anthropic
from app.config import settings
from app.database import supabase
from app.schemas.chat import ChatRequest, ChatResponse, FuenteCitada
from app.services.gemini_client import gemini_chat

CO_TZ = ZoneInfo("America/Bogota")

SYSTEM_PROMPT = """Eres ETÉREA, una guía cultural viva del Valle de Aburrá (Medellín y sus 9 municipios vecinos).
Eres cálida, curiosa y hablas como una amiga que conoce cada rincón cultural de la ciudad.

Tu personalidad:
- Siempre preguntás al usuario por su contexto: ¿En qué zona vivís? ¿Qué tipo de arte te mueve? ¿Buscás algo para hoy o para esta semana?
- Si es la primera vez que alguien te habla, presentate brevemente y preguntá: "¿En qué barrio o municipio estás? ¿Qué tipo de experiencias culturales te interesan (música, teatro, arte, libros, filosofía, hip-hop...)?"
- Si ya tenés contexto del usuario, personalizá tus recomendaciones.
- Hablás en español colombiano (vos/voseo paisa es aceptable).

Tu conocimiento abarca:
- Espacios culturales documentados (teatros, galerías, librerías, cafés culturales,
  casas de cultura, colectivos de hip hop, bares de jazz, editoriales, sellos discográficos)
- Agenda de eventos en tiempo real (hoy y esta semana)
- Geografía cultural por barrios, zonas y municipios del Valle de Aburrá
- Escena underground (freestyle rap, fanzines, espacios autogestionados)
- Colectivos artísticos, festivales independientes, redes culturales

Reglas:
1. Respondé SIEMPRE con datos concretos del contexto proporcionado.
2. Incluí nombres de espacios, direcciones, Instagram y sitio web cuando estén disponibles.
3. Si preguntan "¿qué hay hoy?", listá TODOS los eventos_hoy del contexto con hora, lugar y precio. Incluí también los eventos_en_curso (empezaron ayer/antes pero siguen hoy).
4. Los eventos_en_curso son eventos de varios días que aún están activos — mostralos CON UNA ETIQUETA "🔴 En curso" antes del resto.
5. Si hay eventos_anteriores en el contexto, mostralos AL FINAL bajo "📅 Eventos recientes (ya empezaron)", no los omitas.
6. Si preguntan por un barrio, zona o municipio, filtrá resultados de esa ubicación.
7. Si no tenés datos suficientes, decilo honestamente y sugerí alternativas.
8. NO inventes espacios ni eventos que no estén en el contexto.
9. Cuando un usuario registra un lugar nuevo, explicá que el sistema lo va a categorizar automáticamente (librería, casa de cultura, colectivo, etc.) y empezar a rastrear sus eventos diariamente.
10. Si alguien pregunta algo general ("¿qué puedo hacer?"), preguntá sus intereses y zona, y luego recomendá espacios + eventos concretos.
11. Para cada evento/espacio, da toda la info útil: nombre, fecha/hora, lugar, precio, contacto, Instagram.
12. Sé exhaustiva: si hay 10 resultados relevantes, mostrá todos.
13. Podés recomendar por categoría: "Si te gusta la filosofía, mirá Café Filosófico y Fundación Estanislao Zuleta. Si te va el hip-hop, andá a una batalla en Aranjuez..."

Fecha y hora actual en Colombia: {fecha_actual_co}

Contexto cultural (base de datos en tiempo real):
{contexto}
"""


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def chat(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
    contexto = _obtener_contexto(request.mensaje)

    historial_msgs = [
        {
            "role": "user" if m.rol == "usuario" else "assistant",
            "content": m.contenido,
        }
        for m in request.historial[-6:]
    ]
    historial_msgs.append({"role": "user", "content": request.mensaje})

    prompt = SYSTEM_PROMPT.format(
        contexto=json.dumps(contexto, ensure_ascii=False, default=str),
        fecha_actual_co=_now_co().strftime("%Y-%m-%d %H:%M"),
    )

    try:
        # 1. Gemini 2.0 Flash (si tiene key válida)
        respuesta = None
        if settings.gemini_api_key:
            respuesta = gemini_chat(prompt, historial_msgs, max_tokens=1024, temperature=0.7)

        # 2. Claude (Anthropic) — fallback principal
        if not respuesta and settings.anthropic_api_key:
            try:
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=1024,
                    temperature=0.7,
                    system=prompt,
                    messages=historial_msgs,
                )
                respuesta = response.content[0].text
            except Exception as e:
                print(f"[chat_service] Claude falló: {e}")

        # 3. Groq fallback
        if not respuesta:
            respuesta = _chat_via_groq(prompt, historial_msgs)

        # 4. Respuesta local de emergencia
        if not respuesta:
            respuesta = _respuesta_fallback(contexto)

    except Exception as exc:
        print(f"[chat_service] Error general: {exc}")
        respuesta = _respuesta_fallback(contexto)

    fuentes = _extraer_fuentes(respuesta, contexto)

    # Guardar en memoria_consultas
    supabase.table("memoria_consultas").insert({
        "pregunta": request.mensaje,
        "respuesta": respuesta,
        "contexto": contexto,
    }).execute()

    return ChatResponse(respuesta=respuesta, fuentes=fuentes)


def _chat_via_groq(system_prompt: str, messages: list) -> Optional[str]:
    """Fallback: usa Groq (llama-3.3-70b) cuando Claude no está disponible."""
    try:
        from app.services.groq_client import _get_client, MODEL_SMART
        client = _get_client()
        if not client:
            return None
        groq_messages = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model=MODEL_SMART,
            max_tokens=1024,
            temperature=0.7,
            messages=groq_messages,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[chat_service] Groq falló: {e}")
        return None


def _respuesta_fallback(contexto: Dict) -> str:
    """Fallback para mantener el chat funcional cuando Claude falla."""
    eventos_hoy = contexto.get("eventos_hoy", [])[:5]
    eventos_semana = contexto.get("eventos_semana", [])[:5]
    espacios = (contexto.get("espacios_relevantes", []) or contexto.get("espacios", []))[:5]

    bloques = []

    if eventos_hoy:
        lineas = ["Eventos de hoy:"]
        for ev in eventos_hoy:
            lineas.append(
                f"- {ev.get('titulo', 'Evento')} · {ev.get('fecha_inicio', '')} · {ev.get('nombre_lugar') or ev.get('barrio') or ev.get('municipio') or 'Medellín'}"
            )
        bloques.append("\n".join(lineas))

    if eventos_semana:
        lineas = ["Próximos eventos:"]
        for ev in eventos_semana:
            lineas.append(
                f"- {ev.get('titulo', 'Evento')} · {ev.get('fecha_inicio', '')} · {ev.get('nombre_lugar') or ev.get('barrio') or ev.get('municipio') or 'Medellín'}"
            )
        bloques.append("\n".join(lineas))

    if espacios:
        lineas = ["Espacios recomendados:"]
        for esp in espacios:
            lineas.append(
                f"- {esp.get('nombre', 'Espacio')} · {esp.get('categoria_principal', 'cultura')} · {esp.get('barrio') or esp.get('municipio') or 'Medellín'}"
            )
        bloques.append("\n".join(lineas))

    bloques.append("¿Querés que te filtre por barrio, zona o categoría? Contame qué te interesa y te ayudo mejor.")
    return "\n\n".join(bloques) if bloques else "¡Hola! Soy ETÉREA. ¿En qué barrio o municipio estás y qué tipo de experiencias culturales te interesan?"


def _obtener_contexto(mensaje: str) -> Dict:
    import re
    contexto: Dict = {
        "espacios": [],
        "eventos_hoy": [],
        "eventos_en_curso": [],   # multi-day events still running today
        "eventos_semana": [],
        "eventos_anteriores": [], # events from yesterday shown at bottom
        "espacios_relevantes": [],
    }

    # Extract zone/location context from message
    zona_filtro = None
    msg_clean = mensaje
    zm = re.search(r'\[Zona:\s*([^\]]+)\]', mensaje)
    if zm:
        zona_filtro = zm.group(1).strip()
        msg_clean = re.sub(r'\[Zona:[^\]]+\]', '', msg_clean).strip()
    um = re.search(r'\[Ubicación:\s*([\d.-]+),\s*([\d.-]+)\]', mensaje)
    if um:
        msg_clean = re.sub(r'\[Ubicación:[^\]]+\]', '', msg_clean).strip()

    # 1. Get more spaces for comprehensive search (100 instead of 15)
    resp_espacios = (
        supabase.table("lugares")
        .select("id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,descripcion,instagram_handle,sitio_web,direccion,nivel_actividad,telefono,email")
        .neq("nivel_actividad", "cerrado")
        .limit(100)
        .execute()
    )
    contexto["espacios"] = resp_espacios.data

    # 2. Search for spaces matching the query keywords (like a search engine)
    keywords = [w for w in msg_clean.lower().split() if len(w) > 2 and w not in ("que", "hay", "hoy", "para", "por", "con", "las", "los", "una", "del", "más", "como", "son", "qué")]
    if keywords:
        for kw in keywords[:3]:
            resp_kw = (
                supabase.table("lugares")
                .select("id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,instagram_handle,sitio_web,direccion,telefono")
                .or_(f"nombre.ilike.%{kw}%,descripcion.ilike.%{kw}%,barrio.ilike.%{kw}%,categoria_principal.ilike.%{kw}%")
                .neq("nivel_actividad", "cerrado")
                .limit(20)
                .execute()
            )
            for e in resp_kw.data:
                if not any(x["id"] == e["id"] for x in contexto["espacios_relevantes"]):
                    contexto["espacios_relevantes"].append(e)

    # 3. Events today — use .isoformat() to preserve -05:00 offset so Supabase
    #    compares timestamps correctly (strftime strips the tz and Supabase
    #    treats the bare string as UTC, causing an ~5-hour shift).
    ahora_co = _now_co()
    hoy_inicio = ahora_co.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    hoy_iso = hoy_inicio.isoformat()       # "2026-04-21T00:00:00-05:00"
    manana_iso = hoy_fin.isoformat()       # "2026-04-22T00:00:00-05:00"
    ayer_iso = ayer_inicio.isoformat()     # "2026-04-20T00:00:00-05:00"

    resp_hoy = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion")
        .gte("fecha_inicio", hoy_iso)
        .lt("fecha_inicio", manana_iso)
        .order("fecha_inicio")
        .limit(50)
        .execute()
    )
    contexto["eventos_hoy"] = resp_hoy.data

    # 3b. Multi-day / ongoing events: started before today, fecha_fin >= today start
    resp_en_curso = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion")
        .lt("fecha_inicio", hoy_iso)
        .gte("fecha_fin", hoy_iso)
        .order("fecha_inicio")
        .limit(20)
        .execute()
    )
    contexto["eventos_en_curso"] = resp_en_curso.data

    # 3c. Yesterday's events without fecha_fin (single-day, started yesterday)
    #     shown at the bottom so user knows what they missed
    resp_ayer = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
        .gte("fecha_inicio", ayer_iso)
        .lt("fecha_inicio", hoy_iso)
        .is_("fecha_fin", "null")
        .order("fecha_inicio", desc=True)
        .limit(10)
        .execute()
    )
    contexto["eventos_anteriores"] = resp_ayer.data

    # 4. Events this week
    semana_iso = (hoy_inicio + timedelta(days=7)).isoformat()
    resp_semana = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion")
        .gte("fecha_inicio", manana_iso)
        .lte("fecha_inicio", semana_iso)
        .order("fecha_inicio")
        .limit(30)
        .execute()
    )
    contexto["eventos_semana"] = resp_semana.data

    # 5. Search events by keywords too (search engine style)
    if keywords:
        all_ev_ids = {e["id"] for e in contexto["eventos_hoy"] + contexto["eventos_en_curso"] + contexto["eventos_semana"]}
        for kw in keywords[:3]:
            resp_ev_kw = (
                supabase.table("eventos")
                .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
                .gte("fecha_inicio", hoy_iso)
                .or_(f"titulo.ilike.%{kw}%,descripcion.ilike.%{kw}%,nombre_lugar.ilike.%{kw}%,categoria_principal.ilike.%{kw}%")
                .order("fecha_inicio")
                .limit(15)
                .execute()
            )
            for ev in resp_ev_kw.data:
                if ev["id"] not in all_ev_ids:
                    contexto["eventos_semana"].append(ev)
                    all_ev_ids.add(ev["id"])

    # 6. Zone context
    if zona_filtro:
        contexto["zona_usuario"] = zona_filtro

    return contexto


def _extraer_fuentes(respuesta: str, contexto: Dict) -> List[FuenteCitada]:
    fuentes = []
    resp_lower = respuesta.lower()
    seen_ids = set()

    all_espacios = contexto.get("espacios", []) + contexto.get("espacios_relevantes", [])
    for e in all_espacios:
        if e["id"] in seen_ids:
            continue
        nombre_lower = e["nombre"].lower()
        # Match full name or significant portion (3+ char words)
        words = [w for w in nombre_lower.split() if len(w) > 2]
        matched = nombre_lower in resp_lower or any(w in resp_lower for w in words if len(w) > 4)
        if matched:
            seen_ids.add(e["id"])
            fuentes.append(FuenteCitada(
                tipo="espacio",
                id=e["id"],
                nombre=e.get("slug", e["nombre"]),
                categoria=e["categoria_principal"],
                barrio=e.get("barrio"),
                url=f"/espacio/{e.get('slug', e['id'])}",
                instagram=e.get("instagram_handle"),
                sitio_web=e.get("sitio_web"),
            ))

    all_events = (contexto.get("eventos_en_curso", []) + contexto.get("eventos_hoy", [])
                  + contexto.get("eventos_anteriores", []) + contexto.get("eventos_semana", []))
    for ev in all_events:
        if ev["id"] in seen_ids:
            continue
        titulo_lower = ev["titulo"].lower()
        words = [w for w in titulo_lower.split() if len(w) > 2]
        matched = titulo_lower in resp_lower or any(w in resp_lower for w in words if len(w) > 4)
        if matched:
            seen_ids.add(ev["id"])
            fuentes.append(FuenteCitada(
                tipo="evento",
                id=ev["id"],
                nombre=ev.get("slug", ev["titulo"]),
                categoria=ev["categoria_principal"],
                barrio=ev.get("barrio"),
                url=f"/evento/{ev.get('slug', ev['id'])}",
                imagen_url=ev.get("imagen_url"),
            ))

    return fuentes
