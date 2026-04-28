import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase
from app.services.auto_scraper import _scrape_lugar

async def main():
    print('Scrapeando equipamientos publicos, bibliotecas, uvas y universidades...')
    
    resp = supabase.table('lugares').select('*').in_('tipo', ['biblioteca', 'uva', 'teatro', 'parque_cultural', 'universidad', 'centro_cultural', 'museo']).execute()
    lugares = resp.data or []
    
    print(f'Se encontraron {len(lugares)} lugares para scrapear.')
    
    for i, lugar in enumerate(lugares, 1):
        print(f"\n--- [{i}/{len(lugares)}] {lugar['nombre']} ---")
        if not lugar.get('sitio_web') and not lugar.get('instagram_handle'):
            print('Saltando (sin web/IG)')
            continue
        try:
            await _scrape_lugar(lugar)
        except Exception as e:
            print(f'Error en {lugar["nombre"]}: {e}')

if __name__ == '__main__':
    asyncio.run(main())
