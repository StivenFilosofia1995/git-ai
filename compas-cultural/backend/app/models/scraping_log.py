from sqlalchemy import Column, String, TIMESTAMP, Integer, Float, func
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base


class ScrapingLog(Base):
    __tablename__ = "scraping_log"

    id = Column(Integer, primary_key=True)
    fuente = Column(String(50), nullable=False)
    ejecutado_en = Column(TIMESTAMP(timezone=True), server_default=func.now())
    registros_nuevos = Column(Integer, default=0)
    registros_actualizados = Column(Integer, default=0)
    errores = Column(Integer, default=0)
    detalle = Column(JSONB)
    duracion_segundos = Column(Float)