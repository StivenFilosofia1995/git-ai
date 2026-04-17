from pydantic import BaseModel
from .espacio import MunicipioVA


class ZonaCulturalBase(BaseModel):
    nombre: str
    slug: str
    descripcion: str | None = None
    vocacion: str | None = None
    municipio: MunicipioVA = MunicipioVA.medellin


class ZonaCultural(ZonaCulturalBase):
    id: int

    class Config:
        from_attributes = True
