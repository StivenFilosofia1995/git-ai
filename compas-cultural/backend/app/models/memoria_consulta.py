from sqlalchemy import Column, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class MemoriaConsulta(Base):
    __tablename__ = "memoria_consultas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(Text)
    pregunta = Column(Text)
    respuesta = Column(Text)
    contexto = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
