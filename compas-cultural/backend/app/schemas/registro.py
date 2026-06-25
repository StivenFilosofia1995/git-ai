from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse


class RegistroURLRequest(BaseModel):
    url: str
    acepta_politica_datos: bool

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

    @field_validator('acepta_politica_datos')
    @classmethod
    def validar_consentimiento(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError('Debes aceptar la política de datos para registrar una URL')
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


class RegistroManualRequest(BaseModel):
    nombre: str
    municipio: str = "medellin"
    categoria_principal: str = "otro"
    tipo: str = "colectivo"
    barrio: Optional[str] = None
    descripcion_corta: Optional[str] = None
    email: Optional[str] = None
    instagram_handle: Optional[str] = None
    sitio_web: Optional[str] = None
    acepta_politica_datos: bool

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        txt = (v or "").strip()
        if len(txt) < 3:
            raise ValueError("Nombre demasiado corto")
        return txt[:150]

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        txt = v.strip()
        if not txt:
            return None
        if "@" not in txt or "." not in txt.split("@")[-1]:
            raise ValueError("Email no válido")
        return txt[:180]

    @field_validator("acepta_politica_datos")
    @classmethod
    def validar_consentimiento_manual(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Debes aceptar la política de datos")
        return v


class RegistroManualResponse(BaseModel):
    ok: bool
    lugar_id: str
    slug: str
    mensaje: str


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
