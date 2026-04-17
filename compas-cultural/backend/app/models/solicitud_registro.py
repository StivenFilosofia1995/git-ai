from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class SolicitudRegistro(Base):
    __tablename__ = "solicitudes_registro"

    id = Column(Integer, primary_key=True)
    url = Column(String(1000), nullable=False)
    tipo_url = Column(String(50), nullable=False)
    estado = Column(String(30), default='pendiente', nullable=False)

    # Datos extraídos por scraping
    datos_extraidos = Column(JSONB)

    # Si se creó un espacio a partir de esta solicitud
    espacio_id = Column(UUID(as_uuid=True), nullable=True)

    # Feedback / errores
    mensaje = Column(Text)

    # Auditoría
    ip_solicitante = Column(String(45))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
