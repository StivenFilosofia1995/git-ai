"""
Router mock para desarrollo sin base de datos.
Sirve datos de ejemplo realistas del Valle de Aburrá.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from app.mock_data import ZONAS, ESPACIOS, EVENTOS

router = APIRouter()


# ─── Zonas ────────────────────────────────────────────────
@router.get("/zonas/", tags=["zonas"])
async def get_zonas():
    return ZONAS


@router.get("/zonas/{slug}", tags=["zonas"])
async def get_zona(slug: str):
    zona = next((z for z in ZONAS if z["slug"] == slug), None)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return zona


# ─── Espacios ─────────────────────────────────────────────
@router.get("/espacios/", tags=["espacios"])
async def get_espacios(
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    resultado = ESPACIOS
    if municipio:
        resultado = [e for e in resultado if e["municipio"] == municipio]
    if categoria:
        resultado = [e for e in resultado if e["categoria_principal"] == categoria]
    return resultado[offset : offset + limit]


@router.get("/espacios/cerca/", tags=["espacios"])
async def get_espacios_cerca(
    lat: float = Query(...),
    lng: float = Query(...),
    radio_metros: int = Query(default=2000, ge=100, le=10000),
):
    # Retorna todos con distancia simulada
    return [
        {**e, "distancia_metros": int(abs(e["coordenadas"]["lat"] - lat) * 111000)}
        for e in ESPACIOS
        if e.get("coordenadas")
    ]


@router.get("/espacios/{slug}", tags=["espacios"])
async def get_espacio(slug: str):
    espacio = next((e for e in ESPACIOS if e["slug"] == slug), None)
    if not espacio:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    return espacio


# ─── Eventos ──────────────────────────────────────────────
@router.get("/eventos/", tags=["eventos"])
async def get_eventos(
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    resultado = EVENTOS
    if municipio:
        resultado = [e for e in resultado if e["municipio"] == municipio]
    if categoria:
        resultado = [e for e in resultado if e["categoria_principal"] == categoria]
    if es_gratuito is not None:
        resultado = [e for e in resultado if e["es_gratuito"] == es_gratuito]
    return resultado[offset : offset + limit]


@router.get("/eventos/hoy", tags=["eventos"])
async def get_eventos_hoy():
    hoy = datetime.now().date()
    return [
        e for e in EVENTOS
        if datetime.fromisoformat(e["fecha_inicio"]).date() == hoy
    ]


@router.get("/eventos/semana", tags=["eventos"])
async def get_eventos_semana():
    return EVENTOS


@router.get("/eventos/{slug}", tags=["eventos"])
async def get_evento(slug: str):
    evento = next((e for e in EVENTOS if e["slug"] == slug), None)
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return evento


# ─── Búsqueda ─────────────────────────────────────────────
@router.get("/busqueda/", tags=["busqueda"])
async def buscar(
    q: str,
    tipo: str = "todo",
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
):
    q_lower = q.lower()
    resultados = []

    if tipo in ("todo", "espacio"):
        for e in ESPACIOS:
            texto = f"{e['nombre']} {e.get('descripcion', '')} {e.get('barrio', '')} {e['categoria_principal']}".lower()
            if q_lower in texto:
                resultados.append({"tipo": "espacio", "item": e, "similitud": 0.85})

    if tipo in ("todo", "evento"):
        for ev in EVENTOS:
            texto = f"{ev['titulo']} {ev.get('descripcion', '')} {ev.get('nombre_lugar', '')} {ev['categoria_principal']}".lower()
            if q_lower in texto:
                resultados.append({"tipo": "evento", "item": ev, "similitud": 0.80})

    return {
        "resultados": resultados[offset : offset + limit],
        "total": len(resultados),
        "query": q,
    }


# ─── Chat (respuesta simulada) ───────────────────────────
from pydantic import BaseModel
from typing import List


class MensajeMock(BaseModel):
    rol: str
    contenido: str


class ChatRequestMock(BaseModel):
    mensaje: str
    historial: List[MensajeMock] = []


@router.post("/chat/", tags=["chat"])
async def chat_mock(request: ChatRequestMock):
    # Respuesta contextual básica basada en keywords
    msg = request.mensaje.lower()
    
    if any(w in msg for w in ["teatro", "obra", "matacandelas"]):
        respuesta = "🎭 En Medellín hay una escena teatral vibrante. Te recomiendo el **Teatro Matacandelas** en el barrio Prado, uno de los íconos del teatro independiente colombiano desde 1979. También la **Casa Teatro El Poblado** para algo más íntimo."
        fuentes = [
            {"tipo": "espacio", "id": "esp-002", "nombre": "Teatro Matacandelas", "categoria": "teatro", "barrio": "Prado"},
            {"tipo": "espacio", "id": "esp-003", "nombre": "Casa Teatro El Poblado", "categoria": "teatro", "barrio": "El Poblado"},
        ]
    elif any(w in msg for w in ["jazz", "música", "musica", "vivo", "concierto"]):
        respuesta = "🎵 Para música en vivo esta semana, te recomiendo la **Noche de Jazz en La Pascasia** en Laureles (viernes, cover $20.000). Si te gusta el tango, la **Milonga de los Sábados** en la Casa Gardeliana es imperdible."
        fuentes = [
            {"tipo": "evento", "id": "evt-001", "nombre": "Noche de Jazz en La Pascasia", "categoria": "jazz", "barrio": "Laureles"},
            {"tipo": "evento", "id": "evt-006", "nombre": "Milonga de los Sábados", "categoria": "danza", "barrio": "Manrique"},
        ]
    elif any(w in msg for w in ["comuna 13", "hip hop", "hiphop", "graffiti", "mural"]):
        respuesta = "🎨 La **Comuna 13** es un referente mundial del arte urbano. Los **Crew Peligrosos** organizan el Graffiti Tour los sábados y batallas de freestyle quincenales. ¡Es una experiencia imperdible!"
        fuentes = [
            {"tipo": "espacio", "id": "esp-010", "nombre": "Crew Peligrosos", "categoria": "hip_hop", "barrio": "San Javier"},
            {"tipo": "evento", "id": "evt-002", "nombre": "Graffiti Tour Comuna 13", "categoria": "muralismo", "barrio": "San Javier"},
        ]
    elif any(w in msg for w in ["arte", "museo", "galería", "galeria", "exposición", "exposicion"]):
        respuesta = "🖼️ Para arte en Medellín, el **MAMM** (Ciudad del Río) tiene ahora la expo 'Territorios Invisibles'. El **Museo de Antioquia** en Plaza Botero es imprescindible. Y si buscas algo más alternativo, la **Casa Tres Patios** tiene estudios abiertos esta semana."
        fuentes = [
            {"tipo": "espacio", "id": "esp-001", "nombre": "MAMM", "categoria": "arte_contemporaneo", "barrio": "Ciudad del Río"},
            {"tipo": "espacio", "id": "esp-007", "nombre": "Museo de Antioquia", "categoria": "galeria", "barrio": "Centro"},
        ]
    elif any(w in msg for w in ["gratis", "gratuito", "free", "económico"]):
        gratis = [e for e in EVENTOS if e["es_gratuito"]]
        nombres = ", ".join(f"**{e['titulo']}**" for e in gratis[:3])
        respuesta = f"🆓 Hay varios eventos gratuitos esta semana: {nombres}. La Comuna 13 siempre tiene actividades abiertas."
        fuentes = [
            {"tipo": "evento", "id": e["id"], "nombre": e["titulo"], "categoria": e["categoria_principal"], "barrio": e.get("barrio")}
            for e in gratis[:3]
        ]
    elif any(w in msg for w in ["hoy", "haga", "hacer", "recomienda", "plan"]):
        respuesta = "📅 ¡Hoy hay varias opciones! La expo **Territorios Invisibles** en el MAMM, la muestra de fotografía joven en el **Colombo Americano** (entrada libre), y si es viernes, **jazz en La Pascasia**. ¿Qué tipo de actividad te interesa más?"
        fuentes = [
            {"tipo": "evento", "id": "evt-003", "nombre": "Territorios Invisibles", "categoria": "arte_contemporaneo", "barrio": "Ciudad del Río"},
            {"tipo": "evento", "id": "evt-007", "nombre": "Medellín desde el Lente Joven", "categoria": "fotografia", "barrio": "Centro"},
        ]
    else:
        respuesta = f"🎯 Medellín tiene una escena cultural increíble. Hay **{len(ESPACIOS)} espacios culturales** y **{len(EVENTOS)} eventos** esta semana. ¿Te interesa teatro, música en vivo, arte contemporáneo, hip-hop o algo más específico?"
        fuentes = []

    return {"respuesta": respuesta, "fuentes": fuentes}


# ─── Registro (simulado) ─────────────────────────────────
class RegistroMock(BaseModel):
    url: str


@router.post("/registro/", tags=["registro"])
async def registrar_url_mock(request: RegistroMock):
    from app.schemas.registro import detectar_tipo_url
    tipo = detectar_tipo_url(request.url)
    return {
        "id": 1,
        "url": request.url,
        "tipo_url": tipo,
        "estado": "completado",
        "mensaje": f"[MOCK] URL procesada exitosamente como '{tipo}'",
        "created_at": datetime.now().isoformat(),
    }


@router.get("/registro/{solicitud_id}", tags=["registro"])
async def estado_registro_mock(solicitud_id: int):
    return {
        "id": solicitud_id,
        "url": "https://example.com",
        "tipo_url": "sitio_web",
        "estado": "completado",
        "mensaje": "[MOCK] Procesamiento completado",
        "datos_extraidos": {
            "nombre": "Espacio Cultural Demo",
            "descripcion": "Espacio registrado en modo de demostración",
            "categoria": "centro_cultural",
        },
        "espacio_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


# ─── Health ───────────────────────────────────────────────
@router.get("/health/", tags=["health"])
async def health_mock():
    return {"status": "healthy", "service": "compas-cultural-api", "mode": "mock"}
