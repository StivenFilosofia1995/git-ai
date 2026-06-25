from pydantic import BaseModel, Field, computed_field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class CategoriaCultural(str, Enum):
    teatro = "teatro"
    hip_hop = "hip_hop"
    jazz = "jazz"
    musica_en_vivo = "musica_en_vivo"
    electronica = "electronica"
    galeria = "galeria"
    arte_contemporaneo = "arte_contemporaneo"
    libreria = "libreria"
    editorial = "editorial"
    poesia = "poesia"
    filosofia = "filosofia"
    cine = "cine"
    danza = "danza"
    circo = "circo"
    fotografia = "fotografia"
    casa_cultura = "casa_cultura"
    centro_cultural = "centro_cultural"
    festival = "festival"
    batalla_freestyle = "batalla_freestyle"
    muralismo = "muralismo"
    radio_comunitaria = "radio_comunitaria"
    publicacion = "publicacion"
    otro = "otro"

class NivelActividad(str, Enum):
    muy_activo = "muy_activo"
    activo = "activo"
    moderado = "moderado"
    emergente = "emergente"
    historico = "historico"
    cerrado = "cerrado"

class TipoEntidad(str, Enum):
    espacio_fisico = "espacio_fisico"
    colectivo = "colectivo"
    festival = "festival"
    editorial = "editorial"
    publicacion = "publicacion"
    programa_institucional = "programa_institucional"
    red_articuladora = "red_articuladora"
    sello_discografico = "sello_discografico"

class MunicipioVA(str, Enum):
    medellin = "medellin"
    bello = "bello"
    itagui = "itagui"
    envigado = "envigado"
    sabaneta = "sabaneta"
    caldas = "caldas"
    la_estrella = "la_estrella"
    copacabana = "copacabana"
    girardota = "girardota"
    barbosa = "barbosa"

class Coordenadas(BaseModel):
    lat: float
    lng: float

class EspacioCulturalBase(BaseModel):
    nombre: str
    tipo: TipoEntidad
    categorias: List[CategoriaCultural] = []
    categoria_principal: CategoriaCultural
    municipio: MunicipioVA = MunicipioVA.medellin
    barrio: Optional[str] = None
    comuna: Optional[str] = None
    direccion: Optional[str] = None
    descripcion_corta: Optional[str] = None
    descripcion: Optional[str] = None
    enfoque_estrategico: Optional[str] = None
    contexto_historico: Optional[str] = None
    instagram_handle: Optional[str] = None
    instagram_seguidores: Optional[int] = None
    sitio_web: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    facebook: Optional[str] = None
    nivel_actividad: NivelActividad = NivelActividad.activo
    es_underground: bool = False
    es_institucional: bool = False
    modelo_sostenibilidad: Optional[str] = None
    año_fundacion: Optional[int] = None

class EspacioCulturalCreate(EspacioCulturalBase):
    pass

class EspacioCulturalUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[TipoEntidad] = None
    categorias: Optional[List[CategoriaCultural]] = None
    categoria_principal: Optional[CategoriaCultural] = None
    municipio: Optional[MunicipioVA] = None
    barrio: Optional[str] = None
    comuna: Optional[str] = None
    direccion: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    descripcion_corta: Optional[str] = None
    descripcion: Optional[str] = None
    enfoque_estrategico: Optional[str] = None
    contexto_historico: Optional[str] = None
    instagram_handle: Optional[str] = None
    instagram_seguidores: Optional[int] = None
    sitio_web: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    facebook: Optional[str] = None
    nivel_actividad: Optional[NivelActividad] = None
    es_underground: Optional[bool] = None
    es_institucional: Optional[bool] = None
    modelo_sostenibilidad: Optional[str] = None
    año_fundacion: Optional[int] = None


class EspacioCultural(EspacioCulturalBase):
    id: str
    slug: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    fuente_datos: str = "investigacion_base"
    ultima_verificacion: Optional[datetime] = None
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