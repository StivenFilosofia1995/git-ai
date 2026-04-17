from pydantic import BaseModel
from typing import List, Optional, Union
from .espacio import EspacioCultural
from .evento import Evento

class BusquedaRequest(BaseModel):
    q: str
    tipo: Optional[str] = "todo"  # "espacio", "evento", "todo"
    municipio: Optional[str] = None
    categoria: Optional[str] = None
    limit: int = 20
    offset: int = 0

class ResultadoBusqueda(BaseModel):
    tipo: str  # "espacio" o "evento"
    item: Union[EspacioCultural, Evento]
    similitud: Optional[float] = None

class BusquedaResponse(BaseModel):
    resultados: List[ResultadoBusqueda]
    total: int
    query: str