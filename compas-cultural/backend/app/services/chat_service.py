import json
import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
# Anthropic deshabilitado (sin créditos de API)
anthropic = None
from app.config import settings
from app.database import supabase
from app.schemas.chat import ChatRequest, ChatResponse, FuenteCitada
from app.services.gemini_client import gemini_chat
from app.services.ollama_client import ollama_chat
from app.services.ml_utils import (
    multi_field_bm25,
    tokenize as ml_tokenize,
    urgency_score,
    activity_to_numeric,
)

CO_TZ = ZoneInfo("America/Bogota")
EVENT_SELECT_FIELDS = "id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion"

SYSTEM_PROMPT = """Eres ETÉREA, asistente cultural del Valle de Aburrá.
Habla natural, cercana y clara en español colombiano.

OBJETIVO:
- Conversar con naturalidad.
- Recomendar eventos y espacios reales usando SOLO el contexto dado.

REGLAS CLAVE:
- No inventes eventos, lugares, horarios ni precios.
- Si el usuario saluda o conversa, responde breve y humana; no listes eventos sin que lo pida.
- Si el usuario pide planes/eventos (hoy, semana, barrio, categoria), entonces sí recomienda con datos concretos.
- Si `evento_foco` viene en el contexto, responde SOLO sobre ese evento. No listes otros salvo que el usuario lo pida.
- Si la hora no es confiable, di "hora por confirmar".
- Si no hay resultados, di: "No hay eventos registrados para eso. La agenda se actualiza cada día."
- Prioriza claridad sobre cantidad. Mejor 3-6 buenas opciones que un bloque enorme.

FORMATO CUANDO RECOMIENDES EVENTOS:
- Titulo — Lugar, Barrio/Municipio. Fecha y hora. Gratis/Precio.
- Agrega 1 linea corta de contexto si ayuda.

Fecha y hora actual en Colombia: {fecha_actual_co}

Contexto cultural:
{contexto}
"""

# Geographic data for location extraction
MUNICIPIOS_VALLE = {
    "medellín": ["medellín", "medellin", "mde"],
    "itagüí": ["itagüí", "itagui"],
    "envigado": ["envigado"],
    "sabaneta": ["sabaneta"],
    "copacabana": ["copacabana"],
    "bello": ["bello"],
    "girardota": ["girardota"],
    "barbosa": ["barbosa"],
    "la estrella": ["la estrella"],
}

BARRIOS_MEDELLIN_MAP = {
    "el poblado": ["el poblado", "poblado"],
    "centro": ["centro", "downtown"],
    "aranjuez": ["aranjuez"],
    "manrique": ["manrique"],
    "belén": ["belén", "belen"],
    "laureles": ["laureles"],
    "estadio": ["estadio"],
    "la candelaria": ["la candelaria", "candelaria"],
}

VALLE_MUNICIPIOS_NORMALIZED = {
    "medellin", "itagui", "envigado", "sabaneta", "copacabana",
    "bello", "girardota", "barbosa", "la estrella", "la_estrella",
    "caldas",
}

CHAT_EVENT_NEGATIVE_TERMS = {
    "boletin", "boletin filbo", "filbo", "haz clic", "haz click", "click aqui",
    "20%", "off", "descuento", "compra", "promocion", "promoción",
    "devolv", "tickets para todos", "boletos para todos",
}

CHAT_EVENT_POSITIVE_TERMS = {
    "teatro", "concierto", "festival", "taller", "cine", "danza", "charla",
    "funcion", "función", "obra", "recital", "presenta", "musica", "música",
}


def _normalize_str(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_chat_context_prefixes(message: str) -> str:
    clean = message or ""
    clean = re.sub(r'\[zona:\s*[^\]]+\]\s*', '', clean, flags=re.I)
    clean = re.sub(r'\[ubicacion:\s*[^\]]+\]\s*', '', clean, flags=re.I)
    return clean.strip()


def _is_smalltalk_message(message: str) -> bool:
    msg = _normalize_str(_strip_chat_context_prefixes(message))
    if not msg:
        return True
    smalltalk = {
        "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
        "que mas", "como vas", "como estas", "todo bien", "gracias", "ok",
        "que haces", "quien eres", "quien sos", "como te llamas",
    }
    if msg in smalltalk:
        return True
    return len(msg.split()) <= 2 and any(s in msg for s in ["hola", "buenas", "hey"])


def _is_valle_municipio(raw_municipio: Optional[str]) -> bool:
    municipio = _normalize_str(raw_municipio).replace("_", " ")
    if not municipio:
        return True
    if municipio in VALLE_MUNICIPIOS_NORMALIZED:
        return True
    return municipio.replace(" ", "_") in VALLE_MUNICIPIOS_NORMALIZED


def _is_valid_event_for_chat(ev: dict) -> bool:
    title = _normalize_str(ev.get("titulo"))
    desc = _normalize_str(ev.get("descripcion"))
    if len(title) < 6:
        return False
    if not _is_valle_municipio(ev.get("municipio")):
        return False

    blob = f"{title} {desc}".strip()
    neg_hits = sum(1 for t in CHAT_EVENT_NEGATIVE_TERMS if t in blob)
    pos_hits = sum(1 for t in CHAT_EVENT_POSITIVE_TERMS if t in blob)

    # Block obvious promotional/non-agenda records.
    if neg_hits >= 1 and pos_hits == 0:
        return False
    if title.count("http") > 0 or "haz clic" in blob or "click" in blob:
        return False

    return True


def _is_valid_space_for_chat(esp: dict) -> bool:
    name = _normalize_str(esp.get("nombre"))
    if len(name) < 3:
        return False
    return _is_valle_municipio(esp.get("municipio"))


def _to_human_datetime_label(raw_iso: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not raw_iso:
        return None, None
    try:
        dt = datetime.fromisoformat(str(raw_iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CO_TZ)
        else:
            dt = dt.astimezone(CO_TZ)
    except Exception:
        return None, None

    days = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
    months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    fecha = f"{days[dt.weekday()]}, {dt.day} {months[dt.month - 1]}"
    hora = dt.strftime("%I:%M %p").lower()
    return fecha, hora


def _extract_location_from_message(mensaje: str) -> Optional[str]:
    """Extract zone/location (municipality or neighborhood) from user message."""
    import re
    msg_lower = mensaje.lower()
    
    # Check for explicit format [Zona: ...] or [Ubicación: ...]
    zm = re.search(r'\[Zona:\s*([^\]]+)\]', mensaje)
    if zm:
        return zm.group(1).strip()
    
    # Extract natural language location references ("en Itagúí", "de Envigado", etc.)
    for municipio, aliases in MUNICIPIOS_VALLE.items():
        for alias in aliases:
            if re.search(r'(?:en|de|por|desde|para)\s+' + alias + r'\b', msg_lower):
                return municipio
    
    # Check for barrios
    for barrio, aliases in BARRIOS_MEDELLIN_MAP.items():
        for alias in aliases:
            if re.search(r'(?:en|de|por|desde|para)\s+' + alias + r'\b', msg_lower):
                return barrio
    
    return None


def _extract_event_focus_query(message: str) -> Optional[str]:
    clean = _strip_chat_context_prefixes(message)
    quoted = re.search(r'"([^"]{4,180})"', clean)
    if quoted:
        return quoted.group(1).strip()

    patterns = [
        r'detalles solo de este evento:\s*([^\.\n]+)',
        r'mas detalles solo de este evento:\s*([^\.\n]+)',
        r'mas detalles de este evento:\s*([^\.\n]+)',
        r'sobre este evento:\s*([^\.\n]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.I)
        if match:
            candidate = match.group(1).strip().strip('"')
            if len(candidate) >= 4:
                return candidate
    return None


def _buscar_evento_foco(message: str, zona_filtro: Optional[str]) -> Optional[dict]:
    focus_query = _extract_event_focus_query(message)
    if not focus_query:
        return None

    query = supabase.table("eventos").select(EVENT_SELECT_FIELDS).ilike("titulo", f"%{focus_query}%")
    query = _apply_location_filter_to_query(query, zona_filtro)
    resp = query.order("fecha_inicio").limit(5).execute()
    candidates = [e for e in (resp.data or []) if _is_valid_event_for_chat(e)]
    if candidates:
        return candidates[0]

    keywords = _extract_keywords(focus_query, max_keywords=4)
    if not keywords:
        return None
    query = supabase.table("eventos").select(EVENT_SELECT_FIELDS).gte("fecha_inicio", (_now_co() - timedelta(days=1)).isoformat())
    or_filter = ",".join([f"titulo.ilike.%{kw}%" for kw in keywords])
    query = query.or_(or_filter)
    query = _apply_location_filter_to_query(query, zona_filtro)
    resp = query.order("fecha_inicio").limit(10).execute()
    candidates = [e for e in (resp.data or []) if _is_valid_event_for_chat(e)]
    return candidates[0] if candidates else None


def _is_municipality(location: str) -> bool:
    """Check if location is a municipality or a neighborhood."""
    loc = _normalize_str(location)
    for aliases in MUNICIPIOS_VALLE.values():
        norm_aliases = {_normalize_str(a) for a in aliases}
        if loc in norm_aliases:
            return True
    return False


def _get_location_aliases(location: str) -> list[str]:
    """Return normalized aliases for municipality/neighborhood matching."""
    loc = _normalize_str(location)
    aliases: list[str] = []

    for values in MUNICIPIOS_VALLE.values():
        norm_values = [_normalize_str(v) for v in values]
        if loc in norm_values:
            aliases.extend(norm_values)
            break

    if not aliases:
        for values in BARRIOS_MEDELLIN_MAP.values():
            norm_values = [_normalize_str(v) for v in values]
            if loc in norm_values:
                aliases.extend(norm_values)
                break

    if not aliases and loc:
        aliases.append(loc)

    # Deduplicate while preserving order
    out: list[str] = []
    seen = set()
    for a in aliases:
        if not a or a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def _apply_location_filter_to_query(query, location: Optional[str]):
    """Apply location filter to a Supabase query."""
    if not location:
        return query

    aliases = _get_location_aliases(location)
    if not aliases:
        return query

    is_municipality = _is_municipality(location)
    if is_municipality:
        ors = ",".join([f"municipio.ilike.%{a}%" for a in aliases])
        return query.or_(ors)
    else:
        ors = ",".join([f"barrio.ilike.%{a}%" for a in aliases])
        return query.or_(ors)


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def _obtener_espacios(msg_clean: str, zona_filtro: Optional[str]) -> tuple:
    """Get general spaces and spaces matching keywords."""
    espacios = []
    espacios_relevantes = []
    
    query_espacios = supabase.table("lugares").select("id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,descripcion,instagram_handle,sitio_web,direccion,nivel_actividad,telefono,email").neq("nivel_actividad", "cerrado")
    query_espacios = _apply_location_filter_to_query(query_espacios, zona_filtro)
    resp = query_espacios.limit(100).execute()
    espacios = [e for e in (resp.data or []) if _is_valid_space_for_chat(e)]
    
    keywords = _extract_keywords(msg_clean, max_keywords=3)
    if keywords:
        for kw in keywords[:3]:
            query_kw = supabase.table("lugares").select("id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,instagram_handle,sitio_web,direccion,telefono").or_(f"nombre.ilike.%{kw}%,descripcion.ilike.%{kw}%,barrio.ilike.%{kw}%,categoria_principal.ilike.%{kw}%").neq("nivel_actividad", "cerrado")
            query_kw = _apply_location_filter_to_query(query_kw, zona_filtro)
            resp_kw = query_kw.limit(20).execute()
            for e in (resp_kw.data or []):
                if not _is_valid_space_for_chat(e):
                    continue
                if not any(x["id"] == e["id"] for x in espacios_relevantes):
                    espacios_relevantes.append(e)
    
    return espacios, espacios_relevantes, keywords


def _obtener_eventos(zona_filtro: Optional[str]) -> tuple:
    """Get events for today, ongoing, yesterday, and this week."""
    ahora_co = _now_co()
    hoy_inicio = ahora_co.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    hoy_iso = hoy_inicio.isoformat()
    manana_iso = hoy_fin.isoformat()
    ayer_iso = ayer_inicio.isoformat()
    
    query_hoy = supabase.table("eventos").select(EVENT_SELECT_FIELDS).gte("fecha_inicio", hoy_iso).lt("fecha_inicio", manana_iso)
    query_hoy = _apply_location_filter_to_query(query_hoy, zona_filtro)
    eventos_hoy = [e for e in (query_hoy.order("fecha_inicio").limit(50).execute().data or []) if _is_valid_event_for_chat(e)]
    
    query_en_curso = supabase.table("eventos").select(EVENT_SELECT_FIELDS).lt("fecha_inicio", hoy_iso).gte("fecha_fin", hoy_iso)
    query_en_curso = _apply_location_filter_to_query(query_en_curso, zona_filtro)
    eventos_en_curso = [e for e in (query_en_curso.order("fecha_inicio").limit(20).execute().data or []) if _is_valid_event_for_chat(e)]
    
    query_ayer = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
        .gte("fecha_inicio", ayer_iso)
        .lt("fecha_inicio", hoy_iso)
        .is_("fecha_fin", "null")
    )
    query_ayer = _apply_location_filter_to_query(query_ayer, zona_filtro)
    resp_ayer = query_ayer.order("fecha_inicio", desc=True).limit(10).execute()
    eventos_anteriores = [e for e in (resp_ayer.data or []) if _is_valid_event_for_chat(e)]
    
    semana_iso = (hoy_inicio + timedelta(days=7)).isoformat()
    query_semana = supabase.table("eventos").select(EVENT_SELECT_FIELDS).gte("fecha_inicio", manana_iso).lte("fecha_inicio", semana_iso)
    query_semana = _apply_location_filter_to_query(query_semana, zona_filtro)
    eventos_semana = [e for e in (query_semana.order("fecha_inicio").limit(30).execute().data or []) if _is_valid_event_for_chat(e)]
    
    return eventos_hoy, eventos_en_curso, eventos_anteriores, eventos_semana, hoy_iso


def _buscar_eventos_por_keywords(keywords: List[str], hoy_iso: str, zona_filtro: Optional[str], eventos_existentes_ids: set) -> List:
    """Search events by keywords and avoid duplicates."""
    resultados = []
    if keywords:
        for kw in keywords[:3]:
            query = supabase.table("eventos").select("id,slug,titulo,categoria_principal,fecha_inicio,fecha_fin,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url").gte("fecha_inicio", hoy_iso).or_(f"titulo.ilike.%{kw}%,descripcion.ilike.%{kw}%,nombre_lugar.ilike.%{kw}%,categoria_principal.ilike.%{kw}%")
            query = _apply_location_filter_to_query(query, zona_filtro)
            resp = query.order("fecha_inicio").limit(15).execute()
            for ev in (resp.data or []):
                if not _is_valid_event_for_chat(ev):
                    continue
                if ev["id"] not in eventos_existentes_ids:
                    resultados.append(ev)
                    eventos_existentes_ids.add(ev["id"])
    return resultados


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
    fecha_h, hora_h = _to_human_datetime_label(ev.get("fecha_inicio"))
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
        "fecha_humana": fecha_h,
        "hora_humana": hora_h,
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

    if _is_smalltalk_message(user_message):
        max_events = 0
        max_spaces = min(6, max_spaces)

    ctx = {
        "zona_usuario": contexto.get("zona_usuario"),
        "evento_foco": _compact_event(contexto.get("evento_foco")) if contexto.get("evento_foco") else None,
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
    current = _trim_text(request.mensaje, 1000)
    if not msgs or msgs[-1].get("role") != "user" or msgs[-1].get("content") != current:
        msgs.append({"role": "user", "content": current})
    return msgs


def _chat_via_anthropic(system_prompt: str, messages: list) -> Optional[str]:
    if not settings.anthropic_api_key or anthropic is None:
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
    if engine in {"ollama", "auto"}:
        return ["ollama", "groq", "gemini"]
    if engine == "groq":
        return ["groq", "gemini", "ollama"]
    if engine == "gemini":
        return ["gemini", "groq", "ollama"]
    return ["ollama", "groq", "gemini"]


def _generate_llm_response(prompt: str, historial_msgs: list) -> Optional[str]:
    for engine in _engine_order():
        if engine == "ollama":
            respuesta = _chat_via_ollama(prompt, historial_msgs)
        elif engine == "groq":
            respuesta = _chat_via_groq(prompt, historial_msgs)
        elif engine == "gemini":
            respuesta = _chat_via_gemini(prompt, historial_msgs)
        else:
            respuesta = _chat_via_anthropic(prompt, historial_msgs)
        if respuesta:
            return respuesta
    return None


def chat(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
    if _is_smalltalk_message(request.mensaje):
        respuesta = "Hola, soy ETÉREA. Te ayudo a encontrar planes culturales reales en Medellín y el Valle de Aburrá. ¿Qué te gusta más: música, teatro, cine o algo para hoy?"
        return ChatResponse(respuesta=respuesta, fuentes=[])

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
            respuesta = _respuesta_fallback(contexto, request.mensaje)
        respuesta = _normalize_chat_response(respuesta)

    except Exception as exc:
        print(f"[chat_service] Error general: {exc}")
        respuesta = _normalize_chat_response(_respuesta_fallback(contexto, request.mensaje))

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


def _chat_via_ollama(system_prompt: str, messages: list) -> Optional[str]:
    try:
        return ollama_chat(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=settings.chat_max_tokens,
            temperature=settings.chat_temperature,
        )
    except Exception as e:
        print(f"[chat_service] Ollama falló: {e}")
        return None


def _fallback_focus_event_response(evento_foco: dict) -> str:
    fecha_h, hora_h = _to_human_datetime_label(evento_foco.get("fecha_inicio"))
    lugar = evento_foco.get("nombre_lugar") or evento_foco.get("barrio") or evento_foco.get("municipio") or "Medellín"
    precio = "Gratis" if evento_foco.get("es_gratuito") else (evento_foco.get("precio") or "Precio por confirmar")
    descripcion = _trim_text(evento_foco.get("descripcion"), 320)
    detalle = [
        f"{evento_foco.get('titulo', 'Evento')} — {lugar}.",
        f"Fecha: {fecha_h or 'fecha por confirmar'}{f' · {hora_h}' if hora_h else ' · hora por confirmar'}.",
        f"Precio: {precio}.",
    ]
    if descripcion:
        detalle.append(f"Detalle: {descripcion}")
    detalle.append("Si querés, también te cuento cómo llegar, qué otros planes quedan cerca o si parece buen plan para hoy.")
    return "\n".join(detalle)


def _fallback_events_block(title: str, events: list[dict]) -> str:
    lineas = [title]
    for ev in events:
        lineas.append(
            f"- {ev.get('titulo', 'Evento')} · {ev.get('fecha_inicio', '')} · {ev.get('nombre_lugar') or ev.get('barrio') or ev.get('municipio') or 'Medellín'}"
        )
    return "\n".join(lineas)


def _fallback_spaces_block(spaces: list[dict]) -> str:
    lineas = ["Espacios recomendados:"]
    for esp in spaces:
        lineas.append(
            f"- {esp.get('nombre', 'Espacio')} · {esp.get('categoria_principal', 'cultura')} · {esp.get('barrio') or esp.get('municipio') or 'Medellín'}"
        )
    return "\n".join(lineas)


def _event_matches_filters(ev: dict, user_text: str, zona_filtro: Optional[str], keywords: list[str]) -> bool:
    text = _normalize_str(user_text)
    event_blob = _normalize_str(
        f"{ev.get('titulo', '')} {ev.get('categoria_principal', '')} {ev.get('nombre_lugar', '')} {ev.get('barrio', '')} {ev.get('municipio', '')} {ev.get('descripcion', '')}"
    )

    if zona_filtro:
        z = _normalize_str(zona_filtro)
        location_blob = _normalize_str(f"{ev.get('barrio', '')} {ev.get('municipio', '')} {ev.get('nombre_lugar', '')}")
        if z and z not in location_blob:
            return False

    category_tokens = [
        "teatro", "jazz", "hip hop", "hiphop", "cine", "danza", "poesia", "poesia",
        "libreria", "libreria", "galeria", "galeria", "musica", "musica", "conferencia",
    ]
    requested = [t for t in category_tokens if t in text]
    if requested and not any(_normalize_str(t) in event_blob for t in requested):
        return False

    if keywords and not any(_normalize_str(kw) in event_blob for kw in keywords[:4]):
        return False

    return True


def _space_matches_filters(esp: dict, user_text: str, zona_filtro: Optional[str], keywords: list[str]) -> bool:
    text = _normalize_str(user_text)
    blob = _normalize_str(
        f"{esp.get('nombre', '')} {esp.get('categoria_principal', '')} {esp.get('barrio', '')} {esp.get('municipio', '')} {esp.get('descripcion', '')}"
    )

    if zona_filtro:
        z = _normalize_str(zona_filtro)
        location_blob = _normalize_str(f"{esp.get('barrio', '')} {esp.get('municipio', '')} {esp.get('nombre', '')}")
        if z and z not in location_blob:
            return False

    category_tokens = [
        "teatro", "jazz", "hip hop", "hiphop", "cine", "danza", "poesia", "poesia",
        "libreria", "libreria", "galeria", "galeria", "musica", "musica", "conferencia",
    ]
    requested = [t for t in category_tokens if t in text]
    if requested and not any(_normalize_str(t) in blob for t in requested):
        return False

    if keywords and not any(_normalize_str(kw) in blob for kw in keywords[:4]):
        return False

    return True


def _respuesta_fallback(contexto: Dict, user_message: str = "") -> str:
    """Fallback para mantener el chat funcional cuando Claude falla."""
    evento_foco = contexto.get("evento_foco")
    zona_filtro = contexto.get("zona_usuario")
    keywords = _extract_keywords(user_message, max_keywords=4)

    raw_eventos_hoy = contexto.get("eventos_hoy", [])
    raw_eventos_semana = contexto.get("eventos_semana", [])
    raw_espacios = (contexto.get("espacios_relevantes", []) or contexto.get("espacios", []))

    eventos_hoy = [e for e in raw_eventos_hoy if _event_matches_filters(e, user_message, zona_filtro, keywords)][:6]
    eventos_semana = [e for e in raw_eventos_semana if _event_matches_filters(e, user_message, zona_filtro, keywords)][:6]
    espacios = [e for e in raw_espacios if _space_matches_filters(e, user_message, zona_filtro, keywords)][:6]

    if not eventos_hoy and not eventos_semana and not espacios:
        eventos_hoy = raw_eventos_hoy[:4]
        eventos_semana = raw_eventos_semana[:4]
        espacios = raw_espacios[:4]

    bloques = []

    if evento_foco:
        return _fallback_focus_event_response(evento_foco)

    if eventos_hoy:
        bloques.append(_fallback_events_block("Eventos de hoy:", eventos_hoy))

    if eventos_semana:
        bloques.append(_fallback_events_block("Próximos eventos:", eventos_semana))

    if espacios:
        bloques.append(_fallback_spaces_block(espacios))

    if zona_filtro:
        bloques.append(f"Si querés, te sigo filtrando dentro de {zona_filtro} por precio, horario o tipo de plan.")
    else:
        bloques.append("¿Querés que te filtre por barrio, zona o categoría? Contame qué te interesa y te ayudo mejor.")
    return "\n\n".join(bloques) if bloques else "¡Hola! Soy ETÉREA. ¿En qué barrio o municipio estás y qué tipo de experiencias culturales te interesan?"


def _rank_eventos_por_relevancia(
    eventos: list[dict],
    query: str,
    now: datetime,
    top_n: int = 20,
) -> list[dict]:
    """
    Reordena eventos por relevancia ML al mensaje del usuario.

    Score = BM25_multi_campo(query, evento) + urgency_score(días_hasta)

    Asegura que el LLM reciba los eventos MÁS RELEVANTES en las primeras
    posiciones, en lugar de los primeros cronológicamente.
    """
    if not eventos or not query:
        return eventos[:top_n]

    q_tokens = ml_tokenize(query)
    if not q_tokens:
        return eventos[:top_n]

    scored = []
    for ev in eventos:
        bm25 = multi_field_bm25(
            q_tokens,
            {
                "titulo":       (ev.get("titulo") or "", 3.0),
                "nombre_lugar": (ev.get("nombre_lugar") or "", 2.0),
                "categoria":    (ev.get("categoria_principal") or "", 2.5),
                "barrio":       (ev.get("barrio") or "", 1.5),
                "descripcion":  (ev.get("descripcion") or "", 1.0),
                "municipio":    (ev.get("municipio") or "", 1.2),
            },
        )
        days_until = 0.0
        try:
            fecha_str = ev.get("fecha_inicio") or ""
            if fecha_str:
                ev_dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                ev_dt_naive = ev_dt.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
                days_until = max(0.0, (ev_dt_naive - now_naive).total_seconds() / 86400)
        except Exception:
            pass
        urgencia = urgency_score(days_until, weight=1.0, decay=7.0)
        scored.append((ev, bm25 + urgencia))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [ev for ev, _ in scored[:top_n]]


def _rank_espacios_por_relevancia(
    espacios: list[dict],
    query: str,
    top_n: int = 15,
) -> list[dict]:
    """
    Reordena espacios por relevancia BM25 al mensaje del usuario.
    Bonus: activity_to_numeric(nivel_actividad) * 0.3
    """
    if not espacios or not query:
        return espacios[:top_n]

    q_tokens = ml_tokenize(query)
    if not q_tokens:
        return espacios[:top_n]

    scored = []
    for e in espacios:
        bm25 = multi_field_bm25(
            q_tokens,
            {
                "nombre":     (e.get("nombre") or "", 3.0),
                "categoria":  (e.get("categoria_principal") or "", 2.5),
                "barrio":     (e.get("barrio") or "", 1.5),
                "municipio":  (e.get("municipio") or "", 1.2),
                "descripcion":(e.get("descripcion") or e.get("descripcion_corta") or "", 1.0),
            },
        )
        actividad = activity_to_numeric(e.get("nivel_actividad")) * 0.3
        scored.append((e, bm25 + actividad))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [e for e, _ in scored[:top_n]]


def _obtener_contexto(mensaje: str) -> Dict:
    import re
    contexto: Dict = {
        "espacios": [],
        "evento_foco": None,
        "eventos_hoy": [],
        "eventos_en_curso": [],
        "eventos_semana": [],
        "eventos_anteriores": [],
        "espacios_relevantes": [],
    }

    msg_clean = mensaje
    um = re.search(r'\[Ubicación:\s*([\d.-]+),\s*([\d.-]+)\]', mensaje)
    if um:
        msg_clean = re.sub(r'\[Ubicación:[^\]]+\]', '', msg_clean).strip()

    zona_filtro = _extract_location_from_message(mensaje)
    contexto["evento_foco"] = _buscar_evento_foco(msg_clean, zona_filtro)

    # Get spaces and keywords
    espacios, espacios_relevantes, keywords = _obtener_espacios(msg_clean, zona_filtro)

    # ML ranking de espacios por relevancia al mensaje
    now = _now_co()
    contexto["espacios"] = _rank_espacios_por_relevancia(espacios, msg_clean)
    contexto["espacios_relevantes"] = _rank_espacios_por_relevancia(espacios_relevantes, msg_clean)

    # Get events
    eventos_hoy, eventos_en_curso, eventos_anteriores, eventos_semana, hoy_iso = _obtener_eventos(zona_filtro)

    # ML ranking: reordenar eventos por relevancia al mensaje del usuario
    # Asegura que el LLM reciba primero los más relevantes, no solo los más cercanos en fecha
    msg_para_ranking = _strip_chat_context_prefixes(msg_clean)
    contexto["eventos_hoy"] = _rank_eventos_por_relevancia(eventos_hoy, msg_para_ranking, now)
    contexto["eventos_en_curso"] = _rank_eventos_por_relevancia(eventos_en_curso, msg_para_ranking, now)
    contexto["eventos_anteriores"] = _rank_eventos_por_relevancia(eventos_anteriores, msg_para_ranking, now, top_n=10)

    # Search events by keywords
    all_ev_ids = {e["id"] for e in eventos_hoy + eventos_en_curso + eventos_semana}
    eventos_semana_extra = _buscar_eventos_por_keywords(keywords, hoy_iso, zona_filtro, all_ev_ids)
    eventos_semana_todos = eventos_semana + eventos_semana_extra
    contexto["eventos_semana"] = _rank_eventos_por_relevancia(eventos_semana_todos, msg_para_ranking, now)

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
