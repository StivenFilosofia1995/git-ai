"""Inspect Strapi /eventos structure and date fields."""
import asyncio, httpx, json

STRAPI = 'https://strapibppmain.cosmoteca.gov.co/api'

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20) as c:
        r = await c.get(STRAPI + '/eventos?populate=*&pagination[limit]=2')
        d = r.json()
        print(json.dumps(d['data'][0], ensure_ascii=False, indent=2))
        print()
        print('Total events:', d.get('meta', {}).get('pagination', {}).get('total'))
        
        # Also try with date filter - Strapi v4 uses filters[$gte]
        from datetime import date
        today = date.today().isoformat()
        r2 = await c.get(
            STRAPI + f'/eventos?populate=*&pagination[limit]=50'
            f'&filters[Fecha_Hora_Inicio][$gte]={today}'
        )
        d2 = r2.json()
        print(f'\nEvents from today ({today}):', d2.get('meta', {}).get('pagination', {}).get('total'))

asyncio.run(probe())
