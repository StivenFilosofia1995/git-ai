from sqlalchemy import Column, String, Integer, Boolean, Text, Float, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import Base


class EspacioCultural(Base):
    __tablename__ = "lugares"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    nombre = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    tipo = Column(String(50), nullable=False)
    categorias = Column(ARRAY(String), default=[])
    categoria_principal = Column(String(50), nullable=False)

    # Ubicación
    municipio = Column(String(50), default='medellin', nullable=False)
    barrio = Column(String(100))
    comuna = Column(String(50))
    direccion = Column(String(255))
    lat = Column(Float)
    lng = Column(Float)

    # Descripción
    descripcion_corta = Column(String(300))
    descripcion = Column(Text)
    enfoque_estrategico = Column(Text)
    contexto_historico = Column(Text)

    # Contacto
    instagram_handle = Column(String(100))
    instagram_seguidores = Column(Integer)
    sitio_web = Column(String(500))
    telefono = Column(String(50))
    email = Column(String(255))
    facebook = Column(String(255))

    # Metadatos
    nivel_actividad = Column(String(30), default='activo', nullable=False)
    es_underground = Column(Boolean, default=False)
    es_institucional = Column(Boolean, default=False)
    modelo_sostenibilidad = Column(String(100))
    año_fundacion = Column(Integer)

    # Auditoría
    fuente_datos = Column(String(100), default='investigacion_base')
    ultima_verificacion = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())