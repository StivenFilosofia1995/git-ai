from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ResenaCreate(BaseModel):
    tipo: str = Field(..., pattern="^(evento|espacio)$")
    item_id: str
    puntuacion: int = Field(..., ge=1, le=5)
    titulo: Optional[str] = None
    comentario: str = Field(..., min_length=5, max_length=2000)


class ResenaUpdate(BaseModel):
    puntuacion: Optional[int] = Field(None, ge=1, le=5)
    titulo: Optional[str] = None
    comentario: Optional[str] = Field(None, min_length=5, max_length=2000)


class ResenaResponse(BaseModel):
    id: str
    user_id: str
    user_nombre: Optional[str] = None
    tipo: str
    item_id: str
    puntuacion: int
    titulo: Optional[str] = None
    comentario: str
    created_at: str
    updated_at: Optional[str] = None


class ResenaStats(BaseModel):
    promedio: float
    total: int
    distribucion: dict  # {1: count, 2: count, ...}
