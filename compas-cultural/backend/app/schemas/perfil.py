from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


CATEGORIAS_CULTURALES = [
    "teatro",
    "danza",
    "musica",
    "artes_visuales",
    "literatura",
    "cine",
    "hip_hop",
    "jazz",
    "electronica",
    "poesia",
    "fotografia",
    "muralismo",
    "circo",
    "gastronomia_cultural",
    "editorial",
    "freestyle",
]


class PerfilCreate(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    telefono: Optional[str] = None
    bio: Optional[str] = None
    preferencias: List[str] = []
    zona_id: Optional[int] = None
    municipio: str = "medellin"
    ubicacion_barrio: Optional[str] = None
    ubicacion_lat: Optional[float] = None
    ubicacion_lng: Optional[float] = None


class PerfilUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    bio: Optional[str] = None
    preferencias: Optional[List[str]] = None
    zona_id: Optional[int] = None
    municipio: Optional[str] = None
    ubicacion_barrio: Optional[str] = None
    ubicacion_lat: Optional[float] = None
    ubicacion_lng: Optional[float] = None


class PerfilResponse(BaseModel):
    id: str
    user_id: str
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str] = None
    bio: Optional[str] = None
    preferencias: List[str] = []
    zona_id: Optional[int] = None
    municipio: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InteraccionCreate(BaseModel):
    tipo: str  # 'view_evento', 'view_espacio', 'click_zona'
    item_id: str
    categoria: Optional[str] = None
