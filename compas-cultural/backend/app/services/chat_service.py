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
EVENT_SELECT_FIELDS = "id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion"

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
14. Si te hacen una pregunta general (no cultural), respondela con naturalidad y claridad; si aplica, conectala luego con una recomendación cultural útil.
15. Escribí como persona real: frases cortas, tono cercano, sin sonar a manual técnico.
16. No repitas reglas ni plantillas. Evitá bloques excesivamente largos; priorizá claridad.
17. Si la persona solo quiere conversar, conversá normal y recién después ofrecé ayuda cultural.

Fecha y hora actual en Colombia: {fecha_actual_co}

Contexto cultural (base de datos en tiempo real):
{contexto}
"""


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def _trim_text(value: Optional[str], max_len: int) -> str:
    text = (value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _normalize_chat_response(text: Optional[str]) -> str:
    """Small post-process to keep responses natural and readable."""
    out = (text or "").strip()
    if not out:
        return "Estoy aquí para ayudarte. ¿Qué te gustaría explorar hoy?"
    # Avoid overlong walls of text in chat UI.
    if len(out) > 2600:
        out = out[:2600].rstrip() + "…"
    return out


def _extract_keywords(text: str, max_keywords: int = 3) -> List[str]:
    """Extract safe keywords for PostgREST ilike/or filters."""
    import re

    stopwords = {
        "que", "hay", "hoy", "para", "por", "con", "las", "los", "una", "del",
        "mas", "más", "como", "son", "qué", "hola", "buenas", "buenos", "dias", "días",
    }
    tokens = re.findall(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ]+", (text or "").lower())
    cleaned: List[str] = []
    seen: set[str] = set()
    for t in tokens:
        if len(t) <= 2 or t in stopwords:
            continue
        if t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
        if len(cleaned) >= max_keywords:
            break
    return cleaned


def _price_label(ev: dict) -> str:
    if ev.get("es_gratuito") is True:
        return "gratis"
    precio = (ev.get("precio") or "").strip()
    return precio or "pago"


def _compact_event(ev: dict) -> dict:
    return {
        "id": ev.get("id"),
        "slug": ev.get("slug"),
        "titulo": _trim_text(ev.get("titulo"), 120),
        "categoria": ev.get("categoria_principal"),
        "fecha_inicio": ev.get("fecha_inicio"),
        "fecha_fin": ev.get("fecha_fin"),
        "municipio": ev.get("municipio"),
        "barrio": ev.get("barrio"),
        "lugar": _trim_text(ev.get("nombre_lugar"), 90),
        "precio": _price_label(ev),
        "direccion": _trim_text(ev.get("direccion"), 110),
        "descripcion": _trim_text(ev.get("descripcion"), 260),
    }


def _compact_space(esp: dict) -> dict:
    return {
        "id": esp.get("id"),
        "slug": esp.get("slug"),
        "nombre": _trim_text(esp.get("nombre"), 90),
        "categoria": esp.get("categoria_principal"),
        "municipio": esp.get("municipio"),
        "barrio": esp.get("barrio"),
        "direccion": _trim_text(esp.get("direccion"), 100),
        "instagram": esp.get("instagram_handle"),
        "sitio_web": esp.get("sitio_web"),
        "descripcion": _trim_text(esp.get("descripcion_corta") or esp.get("descripcion"), 220),
    }


def _compact_context(contexto: Dict, user_message: str) -> Dict:
    max_events = settings.chat_context_events_limit
    max_spaces = settings.chat_context_spaces_limit

    ctx = {
        "zona_usuario": contexto.get("zona_usuario"),
        "eventos_en_curso": [_compact_event(e) for e in (contexto.get("eventos_en_curso") or [])[:max_events]],
        "eventos_hoy": [_compact_event(e) for e in (contexto.get("eventos_hoy") or [])[:max_events]],
        "eventos_semana": [_compact_event(e) for e in (contexto.get("eventos_semana") or [])[:max_events]],
        "eventos_anteriores": [_compact_event(e) for e in (contexto.get("eventos_anteriores") or [])[:10]],
    }

    espacios_relevantes = contexto.get("espacios_relevantes") or []
    espacios_generales = contexto.get("espacios") or []
    if espacios_relevantes:
        selected = espacios_relevantes[:max_spaces]
    else:
        selected = espacios_generales[:max_spaces]
    ctx["espacios"] = [_compact_space(e) for e in selected]

    # For broad requests, keep some extra variety from general spaces.
    msg = (user_message or "").lower()
    broad = any(t in msg for t in ["qué hay", "que hay", "plan", "recomienda", "recomendame", "hoy", "fin de semana"])
    if broad and not espacios_relevantes:
        ctx["espacios"] = [_compact_space(e) for e in espacios_generales[: max_spaces + 10]]

    return ctx


def _build_historial_msgs(request: ChatRequest) -> List[Dict[str, str]]:
    max_msgs = settings.chat_history_messages
    msgs = []
    for m in request.historial[-max_msgs:]:
        role = "user" if m.rol == "usuario" else "assistant"
        content = _trim_text(m.contenido, 450)
        if content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": _trim_text(request.mensaje, 1000)})
    return msgs


def _chat_via_anthropic(system_prompt: str, messages: list) -> Optional[str]:
    if not settings.anthropic_api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.chat_max_tokens,
            temperature=settings.chat_temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        print(f"[chat_service] Claude falló: {e}")
        return None


def _chat_via_gemini(system_prompt: str, messages: list) -> Optional[str]:
    if not settings.gemini_api_key:
        return None
    try:
        return gemini_chat(
            system_prompt,
            messages,
            max_tokens=settings.chat_max_tokens,
            temperature=settings.chat_temperature,
        )
    except Exception as e:
        print(f"[chat_service] Gemini falló: {e}")
        return None


def _engine_order() -> List[str]:
    engine = (settings.chat_engine or "auto").lower()
    if engine == "groq":
        return ["groq", "gemini", "anthropic"]
    if engine == "gemini":
        return ["gemini", "groq", "anthropic"]
    if engine == "anthropic":
        return ["anthropic", "groq", "gemini"]
    return ["groq", "gemini", "anthropic"]


def _generate_llm_response(prompt: str, historial_msgs: list) -> Optional[str]:
    for engine in _engine_order():
        if engine == "groq":
            respuesta = _chat_via_groq(prompt, historial_msgs)
        elif engine == "gemini":
            respuesta = _chat_via_gemini(prompt, historial_msgs)
        else:
            respuesta = _chat_via_anthropic(prompt, historial_msgs)
        if respuesta:
            return respuesta
    return None


def chat(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
    contexto = _obtener_contexto(request.mensaje)

    contexto_compacto = _compact_context(contexto, request.mensaje)
    historial_msgs = _build_historial_msgs(request)

    prompt = SYSTEM_PROMPT.format(
        contexto=json.dumps(contexto_compacto, ensure_ascii=False, default=str),
        fecha_actual_co=_now_co().strftime("%Y-%m-%d %H:%M"),
    )

    try:
        respuesta = _generate_llm_response(prompt, historial_msgs)

        if not respuesta:
            respuesta = _respuesta_fallback(contexto)
        respuesta = _normalize_chat_response(respuesta)

    except Exception as exc:
        print(f"[chat_service] Error general: {exc}")
        respuesta = _normalize_chat_response(_respuesta_fallback(contexto))

    fuentes = _extraer_fuentes(respuesta, contexto)

    # Guardar en memoria_consultas
    try:
        supabase.table("memoria_consultas").insert({
            "pregunta": request.mensaje,
            "respuesta": respuesta,
            "contexto": {**contexto_compacto, "user_id": user_id},
        }).execute()
    except Exception as e:
        print(f"[chat_service] No se pudo guardar memoria_consultas: {e}")

    return ChatResponse(respuesta=respuesta, fuentes=fuentes)


def _chat_via_groq(system_prompt: str, messages: list) -> Optional[str]:
    """Primary chat via Groq with token-safe defaults."""
    try:
        from app.services.groq_client import _get_client, MODEL_SMART
        client = _get_client()
        if not client:
            return None
        groq_messages = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model=MODEL_SMART,
            max_tokens=settings.chat_max_tokens,
            temperature=settings.chat_temperature,
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
    keywords = _extract_keywords(msg_clean, max_keywords=3)
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
        .select(EVENT_SELECT_FIELDS)
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
        .select(EVENT_SELECT_FIELDS)
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
        .select(EVENT_SELECT_FIELDS)
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
