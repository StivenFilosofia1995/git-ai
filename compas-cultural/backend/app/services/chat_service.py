import json
from datetime import datetime, timedelta
from typing import List, Dict
import anthropic
from app.config import settings
from app.database import supabase
from app.schemas.chat import ChatRequest, ChatResponse, FuenteCitada

SYSTEM_PROMPT = """Eres ETÉREA, un asistente cultural especializado en el ecosistema artístico
del Valle de Aburrá (Medellín y municipios del área metropolitana).

Tu conocimiento abarca:
- Espacios culturales documentados (teatros, galerías, librerías,
  casas de cultura, colectivos de hip hop, bares de jazz, editoriales)
- Agenda de eventos en tiempo real
- Geografía cultural por barrios y zonas
- Historia del ecosistema cultural
- Escena underground (freestyle rap, fanzines, espacios autogestionados)

Reglas:
1. Responde SIEMPRE con datos concretos del contexto proporcionado.
2. Incluye nombres de espacios, direcciones, Instagram y sitio web cuando estén disponibles.
3. Si un usuario pregunta "¿qué hay hoy?", prioriza los eventos de HOY. Lista TODOS los eventos_hoy del contexto con detalles (hora, lugar, precio).
4. Si preguntan por un barrio específico, nombra espacios y eventos de ese barrio.
5. Si no tienes datos suficientes, dilo honestamente y sugiere alternativas.
6. Responde en español. Sé conciso pero informativo.
7. NO inventes espacios ni eventos que no estén en el contexto.
8. Cuando cites un evento que tenga imagen_url, menciónalo para que el frontend pueda mostrarlo.
9. SIEMPRE incluye el Instagram handle (con @) y sitio web de los espacios/eventos cuando estén disponibles.
10. Si el usuario especifica una zona o ubicación, prioriza resultados de esa zona.
11. Funciona como un buscador cultural: sé exhaustivo en tus resultados. Si hay 10 eventos relevantes, muestra todos, no solo 3.
12. Para cada evento o espacio, da toda la info útil: nombre, fecha/hora, lugar, dirección, precio, categoría, contacto.

Fecha y hora actual en Colombia: {fecha_actual_co}

Contexto cultural (base de datos en tiempo real):
{contexto}
"""


def _now_co() -> datetime:
    """Current time in Colombia (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)


def chat(request: ChatRequest) -> ChatResponse:
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
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            temperature=0.7,
            system=prompt,
            messages=historial_msgs,
        )
        respuesta = response.content[0].text
    except Exception as exc:
        print(f"[chat_service] Claude no disponible, usando fallback local: {exc}")
        respuesta = _respuesta_fallback(contexto)

    fuentes = _extraer_fuentes(respuesta, contexto)

    # Guardar en memoria_consultas
    supabase.table("memoria_consultas").insert({
        "pregunta": request.mensaje,
        "respuesta": respuesta,
        "contexto": contexto,
    }).execute()

    return ChatResponse(respuesta=respuesta, fuentes=fuentes)


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
    hoy = ahora_co.date().isoformat()
    manana = (ahora_co.date() + timedelta(days=1)).isoformat()

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
    semana = (ahora_co.date() + timedelta(days=7)).isoformat()
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
