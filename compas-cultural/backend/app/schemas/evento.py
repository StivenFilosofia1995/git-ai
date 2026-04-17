from pydantic import BaseModel, computed_field
from typing import List, Optional
from datetime import datetime
from .espacio import CategoriaCultural, MunicipioVA, Coordenadas


class EventoBase(BaseModel):
    titulo: str
    espacio_id: Optional[str] = None
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    es_recurrente: bool = False
    patron_recurrencia: Optional[dict] = None
    categorias: List[CategoriaCultural] = []
    categoria_principal: CategoriaCultural
    municipio: MunicipioVA = MunicipioVA.medellin
    barrio: Optional[str] = None
    direccion: Optional[str] = None
    nombre_lugar: Optional[str] = None
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    precio: Optional[str] = None
    es_gratuito: bool = False
    fuente: str
    fuente_url: Optional[str] = None
    fuente_post_id: Optional[str] = None
    verificado: bool = False


class EventoCreate(EventoBase):
    lat: Optional[float] = None
    lng: Optional[float] = None


class EventoUpdate(BaseModel):
    titulo: Optional[str] = None
    espacio_id: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    es_recurrente: Optional[bool] = None
    patron_recurrencia: Optional[dict] = None
    categorias: Optional[List[CategoriaCultural]] = None
    categoria_principal: Optional[CategoriaCultural] = None
    municipio: Optional[MunicipioVA] = None
    barrio: Optional[str] = None
    direccion: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    nombre_lugar: Optional[str] = None
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    precio: Optional[str] = None
    es_gratuito: Optional[bool] = None
    fuente: Optional[str] = None
    fuente_url: Optional[str] = None
    fuente_post_id: Optional[str] = None
    verificado: Optional[bool] = None


class Evento(EventoBase):
    id: str
    slug: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def coordenadas(self) -> Optional[Coordenadas]:
        if self.lat is not None and self.lng is not None:
            return Coordenadas(lat=self.lat, lng=self.lng)
        return None

    class Config:
        from_attributes = True