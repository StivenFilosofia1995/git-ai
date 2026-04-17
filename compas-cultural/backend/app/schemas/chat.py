from pydantic import BaseModel
from typing import List, Optional

class MensajeChat(BaseModel):
    rol: str  # "usuario" o "compas"
    contenido: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    mensaje: str
    historial: List[MensajeChat] = []

class FuenteCitada(BaseModel):
    tipo: str  # "espacio" o "evento"
    id: str
    nombre: str
    categoria: str
    barrio: Optional[str] = None

class ChatResponse(BaseModel):
    respuesta: str
    fuentes: List[FuenteCitada] = []