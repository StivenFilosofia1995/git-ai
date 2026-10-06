from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class BusquedaRequest(BaseModel):
    q: str
    tipo: Optional[str] = "todo"  # "espacio", "evento", "todo"
    municipio: Optional[str] = None
    categoria: Optional[str] = None
    limit: int = 20
    offset: int = 0

class ResultadoBusqueda(BaseModel):
    tipo: str  # "espacio" o "evento"
    # dict: la tabla tiene valores (tipo, categorías, municipio) fuera de los Enum de
    # EspacioCultural/Evento; validar contra ellos tumbaba toda la búsqueda con 500.
    item: Dict[str, Any]
    similitud: Optional[float] = None

class BusquedaResponse(BaseModel):
    resultados: List[ResultadoBusqueda]
    total: int
    query: str