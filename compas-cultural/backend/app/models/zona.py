from sqlalchemy import Column, String, Text, Integer

from app.models.base import Base


class ZonaCultural(Base):
    __tablename__ = "zonas_culturales"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    descripcion = Column(Text)
    vocacion = Column(String(255))
    municipio = Column(String(50), default='medellin')