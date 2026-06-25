import re
from typing import Optional

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = text.strip('-')
    return text

def normalizar_barrio(barrio: Optional[str]) -> Optional[str]:
    """Normalizar nombres de barrios."""
    if not barrio:
        return None

    # Mapeos comunes
    mapeos = {
        'el poblado': 'poblado',
        'san ignacio': 'san-ignacio',
        'bombona': 'bomboná',
        'laureles': 'laureles',
        'estadio': 'estadio',
        'carlos e. restrepo': 'carlos-e-restrepo',
        'prado centro': 'prado-centro',
        'ciudad del rio': 'ciudad-del-río',
        'comuna 13': 'comuna-13',
        'san javier': 'san-javier',
        'aranjuez': 'aranjuez',
        'comuna 4': 'comuna-4',
        'santa cruz': 'santa-cruz',
        'comuna 2': 'comuna-2',
        'manrique': 'manrique',
        'comuna 3': 'comuna-3'
    }

    barrio_lower = barrio.lower().strip()
    return mapeos.get(barrio_lower, barrio_lower)