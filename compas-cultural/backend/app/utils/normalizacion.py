from typing import Dict, Any, Optional
from .slugify import slugify, normalizar_barrio

def normalizar_espacio_datos(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizar datos de un espacio cultural."""
    normalizados = datos.copy()

    # Generar slug si no existe
    if 'nombre' in normalizados and 'slug' not in normalizados:
        normalizados['slug'] = slugify(normalizados['nombre'])

    # Normalizar barrio
    if 'barrio' in normalizados:
        normalizados['barrio'] = normalizar_barrio(normalizados['barrio'])

    # Normalizar municipio
    if 'municipio' in normalizados:
        municipio = normalizados['municipio'].lower().strip()
        if municipio == 'medellín':
            normalizados['municipio'] = 'medellin'
        elif municipio == 'itagüí':
            normalizados['municipio'] = 'itagui'
        elif municipio == 'envigado':
            normalizados['municipio'] = 'envigado'
        # Agregar otros municipios según necesidad

    # Normalizar categorías
    if 'categorias' in normalizados and isinstance(normalizados['categorias'], list):
        normalizados['categorias'] = [cat.lower().strip() for cat in normalizados['categorias']]

    if 'categoria_principal' in normalizados:
        normalizados['categoria_principal'] = normalizados['categoria_principal'].lower().strip()

    return normalizados

def normalizar_evento_datos(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizar datos de un evento."""
    normalizados = datos.copy()

    # Generar slug si no existe
    if 'titulo' in normalizados and 'slug' not in normalizados:
        normalizados['slug'] = slugify(normalizados['titulo'])

    # Normalizar barrio y municipio como en espacios
    if 'barrio' in normalizados:
        normalizados['barrio'] = normalizar_barrio(normalizados['barrio'])

    if 'municipio' in normalizados:
        municipio = normalizados['municipio'].lower().strip()
        if municipio == 'medellín':
            normalizados['municipio'] = 'medellin'
        elif municipio == 'itagüí':
            normalizados['municipio'] = 'itagui'

    # Normalizar categorías
    if 'categorias' in normalizados and isinstance(normalizados['categorias'], list):
        normalizados['categorias'] = [cat.lower().strip() for cat in normalizados['categorias']]

    if 'categoria_principal' in normalizados:
        normalizados['categoria_principal'] = normalizados['categoria_principal'].lower().strip()

    return normalizados