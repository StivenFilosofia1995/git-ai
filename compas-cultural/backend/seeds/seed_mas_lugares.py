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

MAS_LUGARES = [
    {'nombre': 'Casa Museo Otraparte', 'tipo': 'centro_cultural', 'categoria_principal': 'literatura', 'municipio': 'envigado', 'sitio_web': 'https://www.otraparte.org/eventos/', 'instagram_handle': 'casa_otraparte'},
    {'nombre': 'Librería Palinuro', 'tipo': 'libreria', 'categoria_principal': 'literatura', 'municipio': 'medellin', 'instagram_handle': 'libreriapalinuro'},
    {'nombre': 'Exlibris Café', 'tipo': 'cafe', 'categoria_principal': 'literatura', 'municipio': 'medellin', 'instagram_handle': 'exlibris_cafeb'},
    {'nombre': 'El Caballito del Diablo', 'tipo': 'libreria', 'categoria_principal': 'literatura', 'municipio': 'medellin', 'instagram_handle': 'elcaballitodeldiablo'},
    {'nombre': 'Sistema de Bibliotecas Públicas de Medellín', 'tipo': 'biblioteca', 'categoria_principal': 'taller', 'municipio': 'medellin', 'sitio_web': 'https://bibliotecasmedellin.gov.co/agenda/', 'instagram_handle': 'bibliotecasmed'},
    {'nombre': 'Biblioteca EPM', 'tipo': 'biblioteca', 'categoria_principal': 'taller', 'municipio': 'medellin', 'sitio_web': 'https://www.bibliotecaepm.com/', 'instagram_handle': 'bibliotecaepm'},
    {'nombre': 'Casa de la Cultura Poblado', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturapoblado'},
    {'nombre': 'Casa de la Cultura Manrique', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturamanrique'},
    {'nombre': 'Casa de la Cultura Pedregal', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturapedregal'},
    {'nombre': 'Casa de la Cultura Los Colores', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturaloscolores'},
    {'nombre': 'Casa de la Cultura Ávila', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturaavila'},
    {'nombre': 'Casa de la Cultura Santander', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'medellin', 'instagram_handle': 'casaculturasantander'},
    {'nombre': 'Caos Bar (Castilla)', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'caosbar'},
    {'nombre': 'Hated Bar (Castilla)', 'tipo': 'bar', 'categoria_principal': 'musica_en_vivo', 'municipio': 'medellin', 'instagram_handle': 'hatedbar_castilla'},
    {'nombre': 'Teatro Barra del Silencio', 'tipo': 'teatro', 'categoria_principal': 'teatro', 'municipio': 'medellin', 'instagram_handle': 'barradelsilencio'},
    {'nombre': 'Ateneo Porfirio Barba Jacob', 'tipo': 'teatro', 'categoria_principal': 'teatro', 'municipio': 'medellin', 'instagram_handle': 'ateneomedellin'},
    {'nombre': 'Pequeño Teatro', 'tipo': 'teatro', 'categoria_principal': 'teatro', 'municipio': 'medellin', 'instagram_handle': 'pequenoteatro_med'},
    {'nombre': 'Teatro Victoria', 'tipo': 'teatro', 'categoria_principal': 'teatro', 'municipio': 'medellin', 'instagram_handle': 'teatrovictoria'},
    {'nombre': 'El Aquelarre', 'tipo': 'centro_cultural', 'categoria_principal': 'teatro', 'municipio': 'medellin', 'instagram_handle': 'elaquelarre.co'},
    {'nombre': 'Casa de la Cultura La Barquereña', 'tipo': 'casa_cultura', 'categoria_principal': 'taller', 'municipio': 'sabaneta', 'instagram_handle': 'culturasabaneta'},
]

async def main():
    print('Insertando y scrapeando Librerias, Casas de la Cultura y Bares Alternativos...')
    lugares_insertados = []
    
    for record in MAS_LUGARES:
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
