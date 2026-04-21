import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict
from app.config import settings
from app.database import supabase
from app.schemas.chat import ChatRequest, ChatResponse, FuenteCitada

CO_TZ = ZoneInfo("America/Bogota")

# -- Response cache (in-memory, TTL 10 min) --
# Key: hash of normalized message → (timestamp, ChatResponse)
_response_cache: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes

# -- Per-user rate limit (in-memory) --
# Key: user_id → list of timestamps
_user_calls: Dict[str, list] = defaultdict(list)
_USER_MAX_PER_HOUR = 20  # Max messages per user per hour

SYSTEM_PROMPT = """Eres ETÉREA — la guía cultural más completa del Valle de Aburrá (Medellín y sus 9 municipios: Bello, Itagüí, Envigado, Sabaneta, Caldas, La Estrella, Copacabana, Girardota, Barbosa).

━━━ IDENTIDAD ━━━
Sos una amiga local que conoce CADA rincón cultural de la ciudad: los teatros del centro, los colectivos de hip-hop de Aranjuez, las galerías de El Poblado, las librerías de Laureles, los espacios autogestionados del Barrio Antioquia, los festivales de Itagüí, todo.
Hablás en español colombiano natural. Usás "vos" y expresiones paisas cuando van al caso ("bacano", "parce", "qué plan tan chévere"). No sos formal ni rígida — sos cercana, entusiasta y directa.

━━━ PRIMERA INTERACCIÓN ━━━
Si el usuario no se ha presentado antes, saludá y preguntá DOS cosas clave:
1. ¿En qué barrio o municipio del Valle de Aburrá estás?
2. ¿Qué tipo de cultura te mueve? (música en vivo, teatro, arte, libros, filosofía, hip-hop, cine, danza, lo underground...)
Ejemplo: "¡Hola! Soy ETÉREA, tu guía cultural del Valle de Aburrá 🌆 ¿En qué zona estás y qué tipo de plan cultural buscás?"

━━━ CÓMO RESPONDER ━━━
SIEMPRE usa los datos del contexto real que te llega. Nunca inventes.

Cuando listés EVENTOS, usa este formato exacto:
🎭 **[Nombre del evento]**
📅 [Día, fecha] a las [hora]
📍 [Nombre del espacio] — [Barrio/Municipio]
💰 [Precio o "Entrada libre"]
📱 [Instagram del espacio si existe]

Cuando listés ESPACIOS CULTURALES, usa:
🏛️ **[Nombre del espacio]**
📍 [Dirección] — [Barrio]
🎯 [Qué tipo de cultura ofrece en 1 línea]
📱 [Instagram] | 🌐 [Web si existe]

━━━ REGLAS CRÍTICAS ━━━
1. NUNCA inventes un evento, espacio, dirección, Instagram o teléfono que no esté en el contexto. Si no tenés el dato, decí "no tengo ese dato en el sistema".
2. Si preguntan "¿qué hay hoy?" → listá TODOS los eventos_hoy del contexto. Si hay muchos, mostrá todos igual.
3. Si preguntan por un barrio o municipio → filtrá y mostrá solo lo de esa zona.
4. Si el contexto tiene 0 eventos para lo que preguntan → decilo claro y ofrecé alternativas: "No tengo eventos de jazz para hoy, pero hay estos eventos de música en vivo esta semana..."
5. Si alguien pregunta algo muy general ("¿qué puedo hacer?") → primero preguntá su zona e intereses, luego recomendá.
6. Para eventos gratuitos → resaltálos siempre ("¡y es GRATIS!").
7. Respondé en el idioma del usuario (si escribe en inglés, respondé en inglés).
8. Longitud ideal: 150-400 palabras. No más largo a menos que haya muchos eventos que listar.
9. Si hay info de Instagram de un espacio → siempre incluidla, es el canal principal de la escena cultural paisa.
10. Cuando registran un lugar nuevo: explicá que el sistema lo va a empezar a rastrear automáticamente cada 6-8 horas para traer sus eventos a la plataforma.

━━━ TU EXPERTISE POR ZONAS ━━━
- Centro/Candelaria: teatros históricos, galerías, librerías de viejo, performances callejeras
- El Poblado: galerías de arte contemporáneo, cine independiente, música electrónica
- Laureles/Estadio: librerías, cafés culturales, jazz, música acústica
- Aranjuez/Manrique: escena hip-hop, freestyle, murales, cultura barrial
- Belén/Guayabal: casas de cultura, teatro comunitario, danza folclórica
- Itagüí/Envigado: festivales municipales, espacios institucionales, rock alternativo
- Bello: hip-hop, reggaeton cultural, casas de cultura, eventos masivos

━━━ FECHA Y HORA ACTUAL EN COLOMBIA ━━━
{fecha_actual_co}

━━━ BASE DE DATOS EN TIEMPO REAL ━━━
{contexto}
"""


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def _cache_key(mensaje: str) -> str:
    """Normalize message and return hash for cache lookup."""
    normalized = mensaje.lower().strip()
    # Remove zone/location metadata
    import re as _re
    normalized = _re.sub(r'\[(?:Zona|Ubicación):[^\]]+\]', '', normalized).strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def _check_user_rate_limit(user_id: str) -> bool:
    """Return True if user is within rate limit, False if exceeded."""
    now = _now_co()
    cutoff = now - timedelta(hours=1)
    # Clean old entries
    _user_calls[user_id] = [t for t in _user_calls[user_id] if t > cutoff]
    if len(_user_calls[user_id]) >= _USER_MAX_PER_HOUR:
        return False
    _user_calls[user_id].append(now)
    return True


def _clean_cache():
    """Remove expired cache entries."""
    now = _now_co()
    expired = [k for k, (ts, _) in _response_cache.items()
               if (now - ts).total_seconds() > _CACHE_TTL_SECONDS]
    for k in expired:
        del _response_cache[k]


def chat(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
    try:
        return _chat_inner(request, user_id)
    except Exception as exc:
        print(f"[chat_service] UNEXPECTED error in chat(): {exc}")
        return ChatResponse(
            respuesta="Tuve un problema inesperado. Intentá de nuevo en un momento.",
            fuentes=[],
        )


def _chat_inner(request: ChatRequest, user_id: str = "anonymous") -> ChatResponse:
    # Per-user rate limit
    if not _check_user_rate_limit(user_id):
        return ChatResponse(
            respuesta="¡Hey! Estás preguntando demasiado rápido. Esperá unos minutos y volvé a intentar. Máximo 20 mensajes por hora.",
            fuentes=[],
        )

    # Check cache for identical/very similar questions (saves API calls)
    _clean_cache()
    ckey = _cache_key(request.mensaje)
    if ckey in _response_cache and not request.historial:
        cached_ts, cached_response = _response_cache[ckey]
        print(f"[chat] Cache hit for '{request.mensaje[:50]}...'")
        return cached_response

    contexto = _obtener_contexto(request.mensaje)
    # Truncate context to avoid massive prompts (max ~15K chars ≈ 4K tokens)
    contexto_json = json.dumps(contexto, ensure_ascii=False, default=str)
    if len(contexto_json) > 15000:
        # Trim spaces first (keep events which are more useful)
        contexto["espacios"] = contexto["espacios"][:8]
        contexto["espacios_relevantes"] = contexto["espacios_relevantes"][:10]
        contexto_json = json.dumps(contexto, ensure_ascii=False, default=str)
    if len(contexto_json) > 15000:
        contexto["eventos_semana"] = contexto["eventos_semana"][:10]
        contexto["eventos_hoy"] = contexto["eventos_hoy"][:15]
        contexto_json = json.dumps(contexto, ensure_ascii=False, default=str)

    historial_msgs = [
        {
            "role": "user" if m.rol == "usuario" else "assistant",
            "content": m.contenido,
        }
        for m in request.historial[-6:]
    ]
    historial_msgs.append({"role": "user", "content": request.mensaje})

    prompt = SYSTEM_PROMPT.format(
        contexto=contexto_json,
        fecha_actual_co=_now_co().strftime("%Y-%m-%d %H:%M"),
    )

    # ── AI: Groq llama-3.1-8b-instant (FREE, 14400 req/day) → static fallback ──
    print(f"[chat] Groq | contexto: {len(contexto_json)} chars")
    respuesta = _chat_via_groq(prompt, historial_msgs) or _respuesta_fallback(contexto)

    fuentes = _extraer_fuentes(respuesta, contexto)

    # Guardar en memoria_consultas (non-blocking — errors should not affect the response)
    try:
        supabase.table("memoria_consultas").insert({
            "pregunta": request.mensaje,
            "respuesta": respuesta[:2000],
        }).execute()
    except Exception as db_exc:
        print(f"[chat_service] memoria_consultas insert failed (non-fatal): {db_exc}")

    result = ChatResponse(respuesta=respuesta, fuentes=fuentes)

    # Cache the response (only for first messages without history)
    if not request.historial:
        _response_cache[ckey] = (_now_co(), result)

    return result


def _chat_via_groq(system_prompt: str, messages: list) -> str | None:
    """Use Groq (FREE) as AI engine for chat.
    Uses llama-3.1-8b-instant: 14,400 req/day (vs 1,000/day of 70b).
    Enough for ~1,400 active users/day on the same free key.
    Returns response text or None if Groq is unavailable/fails.
    """
    if not settings.groq_api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=full_messages,
            max_tokens=700,
            temperature=0.7,
            timeout=40,
        )
        text = resp.choices[0].message.content.strip() if resp.choices else ""
        if text:
            print("[chat] Groq llama-3.1-8b OK")
        return text or None
    except Exception as e:
        print(f"[chat_service] Groq error: {e}")
        return None


def _respuesta_fallback(contexto: Dict) -> str:
    """Fallback para mantener el chat funcional cuando Claude falla."""
    eventos_hoy = contexto.get("eventos_hoy", [])[:5]
    eventos_semana = contexto.get("eventos_semana", [])[:5]
    espacios = (contexto.get("espacios_relevantes", []) or contexto.get("espacios", []))[:5]

    bloques = [
        "Tuve un problema temporal con el motor de IA, pero igual te comparto datos en vivo del sistema:",
    ]

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

    bloques.append("Si querés, preguntame por un barrio, zona o categoría y te filtro resultados exactos.")
    return "\n\n".join(bloques)


def _obtener_contexto(mensaje: str) -> Dict:
    import re
    contexto: Dict = {"espacios": [], "eventos_hoy": [], "eventos_semana": [], "espacios_relevantes": []}
    try:
        return _obtener_contexto_inner(mensaje)
    except Exception as exc:
        print(f"[chat_service] _obtener_contexto error (returning empty): {exc}")
        return contexto


def _obtener_contexto_inner(mensaje: str) -> Dict:
    import re
    contexto: Dict = {"espacios": [], "eventos_hoy": [], "eventos_semana": [], "espacios_relevantes": []}

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

    # Keywords from user query for targeted search
    keywords = [w for w in msg_clean.lower().split() if len(w) > 2 and w not in ("que", "hay", "hoy", "para", "por", "con", "las", "los", "una", "del", "más", "como", "son", "qué", "esta", "este", "esa", "evento", "eventos", "shay")]

    # 1. Search for spaces matching the query (targeted, not all 600+)
    # Only send RELEVANT spaces — not the entire database
    COMPACT_SPACE_FIELDS = "id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,instagram_handle,sitio_web,direccion,telefono"
    
    if keywords:
        for kw in keywords[:3]:
            resp_kw = (
                supabase.table("lugares")
                .select(COMPACT_SPACE_FIELDS)
                .or_(f"nombre.ilike.%{kw}%,descripcion.ilike.%{kw}%,barrio.ilike.%{kw}%,categoria_principal.ilike.%{kw}%")
                .neq("nivel_actividad", "cerrado")
                .limit(15)
                .execute()
            )
            for e in resp_kw.data:
                if not any(x["id"] == e["id"] for x in contexto["espacios_relevantes"]):
                    contexto["espacios_relevantes"].append(e)
    
    # If zone filter, add spaces from that zone
    if zona_filtro:
        zona_parts = zona_filtro.lower().split("–")  # e.g. "Aranjuez – Manrique"
        for part in zona_parts:
            part = part.strip()
            if part:
                resp_zona = (
                    supabase.table("lugares")
                    .select(COMPACT_SPACE_FIELDS)
                    .or_(f"barrio.ilike.%{part}%,municipio.ilike.%{part}%")
                    .neq("nivel_actividad", "cerrado")
                    .limit(15)
                    .execute()
                )
                for e in resp_zona.data:
                    if not any(x["id"] == e["id"] for x in contexto["espacios_relevantes"]):
                        contexto["espacios_relevantes"].append(e)
    
    # If no keywords matched or first-time greeting, send a curated sample (15 most active)
    if not contexto["espacios_relevantes"]:
        resp_sample = (
            supabase.table("lugares")
            .select(COMPACT_SPACE_FIELDS)
            .neq("nivel_actividad", "cerrado")
            .in_("nivel_actividad", ["muy_activo", "activo"])
            .limit(15)
            .execute()
        )
        contexto["espacios"] = resp_sample.data

    # 3. Events today
    ahora_co = _now_co()
    hoy_inicio = ahora_co.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    hoy = hoy_inicio.strftime("%Y-%m-%dT%H:%M:%S")
    manana = hoy_fin.strftime("%Y-%m-%dT%H:%M:%S")

    COMPACT_EVENT_FIELDS = "id,slug,titulo,categoria_principal,fecha_inicio,barrio,municipio,nombre_lugar,precio,es_gratuito"

    resp_hoy = (
        supabase.table("eventos")
        .select(COMPACT_EVENT_FIELDS)
        .gte("fecha_inicio", hoy)
        .lt("fecha_inicio", manana)
        .order("fecha_inicio")
        .limit(20)
        .execute()
    )
    contexto["eventos_hoy"] = resp_hoy.data

    # 4. Events this week
    semana = (hoy_inicio + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    resp_semana = (
        supabase.table("eventos")
        .select(COMPACT_EVENT_FIELDS)
        .gte("fecha_inicio", manana)
        .lte("fecha_inicio", semana)
        .order("fecha_inicio")
        .limit(20)
        .execute()
    )
    contexto["eventos_semana"] = resp_semana.data

    # 5. Search events by keywords too (search engine style)
    if keywords:
        all_ev_ids = {e["id"] for e in contexto["eventos_hoy"] + contexto["eventos_semana"]}
        for kw in keywords[:3]:
            resp_ev_kw = (
                supabase.table("eventos")
                .select(COMPACT_EVENT_FIELDS)
                .gte("fecha_inicio", hoy)
                .or_(f"titulo.ilike.%{kw}%,nombre_lugar.ilike.%{kw}%,categoria_principal.ilike.%{kw}%")
                .order("fecha_inicio")
                .limit(10)
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

    all_events = contexto.get("eventos_hoy", []) + contexto.get("eventos_semana", [])
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
