from sqlalchemy import Column, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import Base


class Artista(Base):
    __tablename__ = "artistas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    nombre = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    categorias = Column(ARRAY(String), default=[])
    bio = Column(Text)
    municipio = Column(String(50))
    barrio = Column(String(100))
    instagram_handle = Column(String(100))
    sitio_web = Column(String(500))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())