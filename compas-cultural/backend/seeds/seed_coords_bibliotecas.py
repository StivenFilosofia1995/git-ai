import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import supabase

coords = [
    ('sistema-de-bibliotecas-publicas-de-medellin', 6.2518, -75.5636),
    ('biblioteca-epm', 6.2443, -75.5762),
    ('fundacion-epm-agenda-cultural', 6.2443, -75.5762),
    ('biblioteca-publica-piloto', 6.2625, -75.5794),
    ('biblioteca-publica-piloto-de-medellin', 6.2625, -75.5794),
    ('museo-del-agua-epm', 6.2443, -75.5762),
    ('parque-biblioteca-espana-santo-domingo', 6.3013, -75.5458),
    ('casa-museo-otraparte', 6.1661, -75.5843),
    ('biblioteca-otraparte', 6.1661, -75.5843),
    ('fundacion-epm', 6.2443, -75.5762)
]

def main():
    for slug, lat, lng in coords:
        supabase.table('lugares').update({'lat': lat, 'lng': lng}).eq('slug', slug).execute()
        print(f"Updated coords for {slug}")

if __name__ == '__main__':
    main()
