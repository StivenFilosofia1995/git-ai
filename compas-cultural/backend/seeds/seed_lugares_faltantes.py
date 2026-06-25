import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase
from app.services.auto_scraper import _scrape_lugar

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[\xc1\xe1]', 'a', text)
    text = re.sub(r'[\xc9\xe9]', 'e', text)
    text = re.sub(r'[\xcd\xed]', 'i', text)
    text = re.sub(r'[\xd3\xf3]', 'o', text)
    text = re.sub(r'[\xda\xfa]', 'u', text)
    text = re.sub(r'\xf1', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

LUGARES_NUEVOS_1 = [
    {'nombre': 'Parque Explora', 'tipo': 'centro_cultural', 'categoria_principal': 'taller', 'municipio': 'medellin', 'sitio_web': 'https://parqueexplora.org/agenda', 'instagram_handle': 'parqueexplora'},
    {'nombre': 'Planetario de Medellin', 'tipo': 'centro_cultural', 'categoria_principal': 'taller', 'municipio': 'medellin', 'sitio_web': 'https://planetariomedellin.org/actualidad/eventos', 'instagram_handle': 'planetariomed'},
    {'nombre': 'Parque de los Pies Descalzos', 'tipo': 'parque', 'categoria_principal': 'evento_al_aire_libre', 'municipio': 'medellin', 'instagram_handle': 'fundacionepm'},
    {'nombre': 'Plaza Mayor', 'tipo': 'centro_convenciones', 'categoria_principal': 'feria', 'municipio': 'medellin', 'sitio_web': 'https://plazamayor.com.co/eventos/', 'instagram_handle': 'plazamayormed'},
    {'nombre': 'Casa de la Cultura La Barquerena', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'sabaneta', 'instagram_handle': 'culturasabaneta'},
    {'nombre': 'Casa de la Cultura Cerro del Angel', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'bello', 'instagram_handle': 'culturabello'},
    {'nombre': 'Biblioteca Diego Echavarria Misas', 'tipo': 'biblioteca', 'categoria_principal': 'literatura', 'municipio': 'itagui', 'instagram_handle': 'biblioteca_itagui', 'sitio_web':'https://bdem.org.co/'},
    {'nombre': 'Casa de la Cultura de Itagui', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'itagui', 'instagram_handle': 'institutoita'},
    {'nombre': 'Casa de la Cultura de Caldas', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'caldas', 'instagram_handle': 'cultura.caldas'},
    {'nombre': 'Casa de la Cultura Envigado', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'envigado', 'instagram_handle': 'culturaenvigado'},
    {'nombre': 'Casa de la Cultura La Estrella', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'la_estrella', 'instagram_handle': 'alcaldialaestrella'},
    {'nombre': 'Alianza Francesa Medellin', 'tipo': 'centro_cultural', 'categoria_principal': 'cine', 'municipio': 'medellin', 'sitio_web': 'https://medellin.alianzafrancesa.org.co/agenda-cultural-af-2/#/', 'instagram_handle': 'alianzafrancesamedellin'},
    {'nombre': 'Centro Colombo Americano', 'tipo': 'centro_cultural', 'categoria_principal': 'cine', 'municipio': 'medellin', 'sitio_web': 'https://www.colombomedellin.edu.co/agendacultural', 'instagram_handle': 'colombomedellin'},
    {'nombre': 'Casa de la Luna', 'tipo': 'centro_cultural', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'casadelalunamed'},
    {'nombre': 'Festival Altavoz', 'tipo': 'festival', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'altavozfest'},
    {'nombre': 'Fiesta del Libro y la Cultura', 'tipo': 'festival', 'categoria_principal': 'literatura', 'municipio': 'medellin', 'sitio_web':'https://fiestadellibroylacultura.com/', 'instagram_handle': 'fiestadellibro'},
    {'nombre': 'Cafe Vallejo', 'tipo': 'cafe', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'cafe.vallejo'},
    {'nombre': 'El Cafe del Teatro', 'tipo': 'cafe', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'cafedelteatro_'},
    {'nombre': 'Cafe Cliche', 'tipo': 'cafe', 'categoria_principal': 'literatura', 'municipio': 'medellin', 'instagram_handle': 'cafe_cliche'},
    {'nombre': 'Poblado Cafe Cultural', 'tipo': 'cafe', 'categoria_principal': 'artes_plasticas', 'municipio': 'medellin', 'instagram_handle': 'pobladocafecultural'}
]

async def main():
    print('Insertando y scrapeando Lugares Faltantes...')
    lugares_insertados = []
    
    for record in LUGARES_NUEVOS_1:
        slug = slugify(record['nombre'])
        payload = {
            'slug': slug,
            'nombre': record['nombre'],
            'tipo': record.get('tipo', 'centro_cultural'),
            'categoria_principal': record.get('categoria_principal', 'taller'),
            'municipio': record.get('municipio', 'medellin'),
            'sitio_web': record.get('sitio_web'),
            'instagram_handle': record.get('instagram_handle'),
        }
        try:
            res = supabase.table('lugares').upsert(payload, on_conflict='slug').execute()
            if res.data:
                lugares_insertados.extend(res.data)
                print(f"  ? {record['nombre']} insertado/actualizado.")
        except Exception as e:
            print(f"  ? Error insertando {record['nombre']}: {e}")

    print(f"\nScrapeando lugares nuevos...")
    for lugar in lugares_insertados:
        if not lugar.get('sitio_web') and not lugar.get('instagram_handle'):
            continue
        try:
            print(f"Scrapeando {lugar['nombre']}...")
            await _scrape_lugar(lugar)
        except Exception as e:
            print(f"Error scrapeando {lugar['nombre']}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
