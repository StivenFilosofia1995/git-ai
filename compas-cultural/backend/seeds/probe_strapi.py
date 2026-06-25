"""Probe Strapi CMS for Biblioteca Pública Piloto events."""
import asyncio, httpx, json

STRAPI = 'https://strapibppmain.cosmoteca.gov.co/api'

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20) as c:
        for path in [
            '/activities?populate=*&pagination[limit]=5',
            '/actividades?populate=*&pagination[limit]=5',
            '/events?populate=*&pagination[limit]=5',
            '/eventos?populate=*&pagination[limit]=5',
            '/agenda-items?populate=*&pagination[limit]=5',
            '/programas?populate=*&pagination[limit]=5',
        ]:
            r = await c.get(STRAPI + path)
            print(path, '->', r.status_code, r.text[:300])
            print()

asyncio.run(probe())
