from sqlalchemy import Column, String, Integer, Boolean, Text, Float, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import Base


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    titulo = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False)

    # Relaciones
    espacio_id = Column(UUID(as_uuid=True), ForeignKey('lugares.id', ondelete='SET NULL'))

    # Temporalidad
    fecha_inicio = Column(TIMESTAMP(timezone=True), nullable=False)
    fecha_fin = Column(TIMESTAMP(timezone=True))
    es_recurrente = Column(Boolean, default=False)
    patron_recurrencia = Column(JSONB)

    # Categorización
    categorias = Column(ARRAY(String), default=[])
    categoria_principal = Column(String(50), nullable=False)

    # Ubicación
    municipio = Column(String(50), default='medellin')
    barrio = Column(String(100))
    direccion = Column(String(255))
    lat = Column(Float)
    lng = Column(Float)
    nombre_lugar = Column(String(255))

    # Contenido
    descripcion = Column(Text)
    imagen_url = Column(String(500))
    precio = Column(String(100))
    es_gratuito = Column(Boolean, default=False)

    # Fuente
    fuente = Column(String(50), nullable=False)
    fuente_url = Column(String(500))
    fuente_post_id = Column(String(255))

    # Auditoría
    verificado = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())