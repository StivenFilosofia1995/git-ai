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

BARES_CAJAS = [
    {'nombre': 'Comfama', 'tipo': 'centro_cultural', 'categoria_principal': 'taller', 'instagram_handle': 'comfama'},
    {'nombre': 'Comfama Cultura', 'tipo': 'centro_cultural', 'categoria_principal': 'taller', 'instagram_handle': 'comfamacultura'},
    {'nombre': 'Comfenalco Antioquia', 'tipo': 'centro_cultural', 'categoria_principal': 'taller', 'instagram_handle': 'comfenalcoant', 'sitio_web': 'https://infolocal.comfenalcoantioquia.com/'},
    {'nombre': 'Blue Medellin', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'blue_medellin'},
    {'nombre': 'Pub Rock Medellin', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'pubrockmedellin'},
    {'nombre': 'Berlin Bar 1930', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'berlinbar1930'},
    {'nombre': 'Valhalla Rock Bar', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'valhallarockbar'},
    {'nombre': 'Trilogia Bar', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'trilogiabar'},
    {'nombre': 'Barnaby Jones', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'barnabyjonesbar_'},
    {'nombre': 'El Sub', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'elsub.medellin'},
    {'nombre': 'La Pascasia', 'tipo': 'teatro', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'la_pascasia'},
    {'nombre': 'Vintrash Bar', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'vintrashbar'},
    {'nombre': 'La Caverna de Baco', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'lacavernadebaco_bar'},
    {'nombre': 'Rock Symphony Bar', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'instagram_handle': 'rocksymphonymedellin'}
]

async def main():
    print('Insertando y scrapeando Bares de Rock y Cajas de Compensacion...')
    lugares_insertados = []
    
    for record in BARES_CAJAS:
        slug = slugify(record['nombre'])
        payload = {
            'slug': slug,
            'nombre': record['nombre'],
            'tipo': record.get('tipo', 'bar'),
            'categoria_principal': record.get('categoria_principal', 'musica_en_vivo'),
            'municipio': 'medellin',
            'sitio_web': record.get('sitio_web'),
            'instagram_handle': record.get('instagram_handle'),
        }
        try:
            res = supabase.table('lugares').upsert(payload, on_conflict='slug').execute()
            if res.data:
                lugares_insertados.extend(res.data)
                print(f"  ? {record['nombre']} insertado.")
        except Exception as e:
            print(f"  ? Error insertando {record['nombre']}: {e}")

    print(f"\nScrapeando {len(lugares_insertados)} lugares nuevos...")
    for lugar in lugares_insertados:
        if not lugar.get('sitio_web') and not lugar.get('instagram_handle'):
            continue
        try:
            await _scrape_lugar(lugar)
        except Exception as e:
            print(f"Error scrapeando {lugar['nombre']}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
