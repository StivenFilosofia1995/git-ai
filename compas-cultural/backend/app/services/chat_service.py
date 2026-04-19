import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict
import anthropic
from app.config import settings
from app.database import supabase
from app.schemas.chat import ChatRequest, ChatResponse, FuenteCitada

CO_TZ = ZoneInfo("America/Bogota")

# -- Daily usage tracking (in-memory, resets on restart) --
_daily_api_calls = {"date": "", "count": 0}
MAX_DAILY_CALLS = 200  # Max Claude API calls per day

# -- Response cache (in-memory, TTL 10 min) --
# Key: hash of normalized message → (timestamp, ChatResponse)
_response_cache: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes

# -- Per-user rate limit (in-memory) --
# Key: user_id → list of timestamps
_user_calls: Dict[str, list] = defaultdict(list)
_USER_MAX_PER_HOUR = 20  # Max messages per user per hour

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
3. Si preguntan "¿qué hay hoy?", listá TODOS los eventos_hoy del contexto con hora, lugar y precio.
4. Si preguntan por un barrio, zona o municipio, filtrá resultados de esa ubicación.
5. Si no tenés datos suficientes, decilo honestamente y sugerí alternativas.
6. NO inventes espacios ni eventos que no estén en el contexto.
7. Cuando un usuario registra un lugar nuevo, explicá que el sistema lo va a categorizar automáticamente (librería, casa de cultura, colectivo, etc.) y empezar a rastrear sus eventos cada 6 horas.
8. Si alguien pregunta algo general ("¿qué puedo hacer?"), preguntá sus intereses y zona, y luego recomendá espacios + eventos concretos.
9. Para cada evento/espacio, da toda la info útil: nombre, fecha/hora, lugar, precio, contacto, Instagram.
10. Sé exhaustiva: si hay 10 resultados relevantes, mostrá todos.
11. Podés recomendar por categoría: "Si te gusta la filosofía, mirá Café Filosófico y Fundación Estanislao Zuleta. Si te va el hip-hop, andá a una batalla en Aranjuez..."

Fecha y hora actual en Colombia: {fecha_actual_co}

Contexto cultural (base de datos en tiempo real):
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

    # Validate API key before even trying
    if not settings.anthropic_api_key or settings.anthropic_api_key.strip() == "":
        print("[chat_service] ANTHROPIC_API_KEY no configurada — usando fallback")
        respuesta = _respuesta_fallback(contexto)
    else:
        try:
            # Check daily budget
            today = _now_co().strftime("%Y-%m-%d")
            if _daily_api_calls["date"] != today:
                _daily_api_calls["date"] = today
                _daily_api_calls["count"] = 0

            if _daily_api_calls["count"] >= MAX_DAILY_CALLS:
                print(f"[chat_service] Daily API limit reached ({MAX_DAILY_CALLS} calls)")
                respuesta = _respuesta_fallback(contexto)
            else:
                # Use model from env var, default to claude-3-5-haiku-20241022
                model = (settings.anthropic_model or "claude-3-5-haiku-20241022").strip()
                if not model:
                    model = "claude-3-5-haiku-20241022"
                print(f"[chat] Usando modelo: {model}")
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=700,
                    temperature=0.7,
                    system=prompt,
                    messages=historial_msgs,
                )
                _daily_api_calls["count"] += 1
                respuesta = response.content[0].text if response.content else ""
                if not respuesta:
                    respuesta = _respuesta_fallback(contexto)
                print(f"[chat] OK — API call #{_daily_api_calls['count']}/{MAX_DAILY_CALLS} today")
        except anthropic.AuthenticationError as exc:
            print(f"[chat_service] ANTHROPIC_API_KEY inválida o expirada: {exc}")
            respuesta = _respuesta_fallback(contexto)
        except anthropic.NotFoundError as exc:
            print(f"[chat_service] Modelo no encontrado: {exc}")
            # Retry with guaranteed fallback model
            try:
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=700,
                    system=prompt,
                    messages=historial_msgs,
                )
                respuesta = response.content[0].text if response.content else ""
                if not respuesta:
                    respuesta = _respuesta_fallback(contexto)
            except Exception:
                respuesta = _respuesta_fallback(contexto)
        except Exception as exc:
            print(f"[chat_service] Claude error: {type(exc).__name__}: {exc}")
            respuesta = _respuesta_fallback(contexto)

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

    # 3. Events today
    ahora_co = _now_co()
    hoy_inicio = ahora_co.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    hoy = hoy_inicio.strftime("%Y-%m-%dT%H:%M:%S")
    manana = hoy_fin.strftime("%Y-%m-%dT%H:%M:%S")

    resp_hoy = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion")
        .gte("fecha_inicio", hoy)
        .lt("fecha_inicio", manana)
        .order("fecha_inicio")
        .limit(50)
        .execute()
    )
    contexto["eventos_hoy"] = resp_hoy.data

    # 4. Events this week
    semana = (hoy_inicio + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    resp_semana = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url,direccion")
        .gte("fecha_inicio", manana)
        .lte("fecha_inicio", semana)
        .order("fecha_inicio")
        .limit(30)
        .execute()
    )
    contexto["eventos_semana"] = resp_semana.data

    # 5. Search events by keywords too (search engine style)
    if keywords:
        all_ev_ids = {e["id"] for e in contexto["eventos_hoy"] + contexto["eventos_semana"]}
        for kw in keywords[:3]:
            resp_ev_kw = (
                supabase.table("eventos")
                .select("id,slug,titulo,categoria_principal,fecha_inicio,barrio,municipio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
                .gte("fecha_inicio", hoy)
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
