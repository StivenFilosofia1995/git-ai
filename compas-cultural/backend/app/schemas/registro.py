from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse


class RegistroURLRequest(BaseModel):
    url: str

    @field_validator('url')
    @classmethod
    def validar_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('La URL no puede estar vacía')

        # Agregar https:// si no tiene esquema
        if not v.startswith(('http://', 'https://')):
            # Si parece un handle de Instagram sin URL
            if v.startswith('@'):
                return f'https://www.instagram.com/{v.lstrip("@")}/'
            v = f'https://{v}'

        parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError('URL no válida')

        return v


class RegistroURLResponse(BaseModel):
    id: int
    url: str
    tipo_url: str
    estado: str
    mensaje: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RegistroEstadoResponse(BaseModel):
    id: int
    url: str
    tipo_url: str
    estado: str
    mensaje: Optional[str] = None
    datos_extraidos: Optional[dict] = None
    espacio_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def detectar_tipo_url(url: str) -> str:
    """Detecta el tipo de URL para dirigir al scraper adecuado."""
    parsed = urlparse(url)
    dominio = parsed.netloc.lower().replace('www.', '')

    if 'instagram.com' in dominio:
        return 'instagram'
    if 'facebook.com' in dominio or 'fb.com' in dominio:
        return 'facebook'
    if 'maps.google' in dominio or 'goo.gl/maps' in dominio or 'google.com/maps' in dominio:
        return 'google_maps'
    return 'sitio_web'
