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
2. Incluye nombres de espacios, direcciones e Instagram cuando estén disponibles.
3. Si un usuario pregunta "¿qué hay hoy?", prioriza los eventos de HOY. Lista TODOS los eventos_hoy del contexto con detalles (hora, lugar, precio).
4. Si preguntan por un barrio específico, nombra espacios y eventos de ese barrio.
5. Si no tienes datos suficientes, dilo honestamente y sugiere alternativas.
6. Responde en español. Sé conciso pero informativo.
7. NO inventes espacios ni eventos que no estén en el contexto.
8. Cuando cites un evento que tenga imagen_url, menciónalo para que el frontend pueda mostrarlo.

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

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        temperature=0.7,
        system=prompt,
        messages=historial_msgs,
    )

    respuesta = response.content[0].text
    fuentes = _extraer_fuentes(respuesta, contexto)

    # Guardar en memoria_consultas
    supabase.table("memoria_consultas").insert({
        "pregunta": request.mensaje,
        "respuesta": respuesta,
        "contexto": contexto,
    }).execute()

    return ChatResponse(respuesta=respuesta, fuentes=fuentes)


def _obtener_contexto(mensaje: str) -> Dict:
    contexto: Dict = {"espacios": [], "eventos_hoy": [], "eventos_semana": []}

    resp_espacios = (
        supabase.table("lugares")
        .select("id,nombre,slug,categoria_principal,barrio,municipio,descripcion_corta,descripcion,instagram_handle,sitio_web,direccion,nivel_actividad")
        .neq("nivel_actividad", "cerrado")
        .limit(15)
        .execute()
    )
    contexto["espacios"] = resp_espacios.data

    # Today's events (Colombia timezone)
    ahora_co = _now_co()
    hoy = ahora_co.date().isoformat()
    manana = (ahora_co.date() + timedelta(days=1)).isoformat()

    resp_hoy = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,barrio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
        .gte("fecha_inicio", hoy)
        .lt("fecha_inicio", manana)
        .order("fecha_inicio")
        .execute()
    )
    contexto["eventos_hoy"] = resp_hoy.data

    # This week's events
    semana = (ahora_co.date() + timedelta(days=7)).isoformat()
    resp_semana = (
        supabase.table("eventos")
        .select("id,slug,titulo,categoria_principal,fecha_inicio,barrio,nombre_lugar,descripcion,precio,es_gratuito,imagen_url")
        .gte("fecha_inicio", manana)
        .lte("fecha_inicio", semana)
        .order("fecha_inicio")
        .limit(15)
        .execute()
    )
    contexto["eventos_semana"] = resp_semana.data

    return contexto


def _extraer_fuentes(respuesta: str, contexto: Dict) -> List[FuenteCitada]:
    fuentes = []
    resp_lower = respuesta.lower()

    for e in contexto.get("espacios", []):
        if e["nombre"].lower() in resp_lower:
            fuentes.append(FuenteCitada(
                tipo="espacio",
                id=e["id"],
                nombre=e.get("slug", e["nombre"]),
                categoria=e["categoria_principal"],
                barrio=e.get("barrio"),
            ))

    all_events = contexto.get("eventos_hoy", []) + contexto.get("eventos_semana", [])
    for ev in all_events:
        if ev["titulo"].lower() in resp_lower:
            fuentes.append(FuenteCitada(
                tipo="evento",
                id=ev["id"],
                nombre=ev.get("slug", ev["titulo"]),
                categoria=ev["categoria_principal"],
                barrio=ev.get("barrio"),
            ))

    return fuentes
