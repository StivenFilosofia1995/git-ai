"""Probe EPM Fundacion programacion page for hidden API endpoints."""
import asyncio, httpx, re, json

BASE = "https://www.grupo-epm.com"

async def probe():
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20) as c:
        # Check robots.txt for clues
        r = await c.get(BASE + "/robots.txt")
        print("=== robots.txt ===")
        print(r.text[:500])
        print()

        # AEM Query Builder
        for url in [
            BASE + "/bin/querybuilder.json?path=/content/epm&type=cq:Page&group.1_property=jcr:content/cq:tags&group.1_property.value=fundacion*&p.limit=20&p.hits=full",
            BASE + "/bin/epm/agenda.json",
            BASE + "/bin/agenda",
            BASE + "/site/fundacionepm/programacion.resources.json",
            BASE + "/site/fundacionepm.sitemap.xml",
        ]:
            r = await c.get(url)
            print(url, "->", r.status_code, r.text[:200])
            print()

        # Scrape the page and find all script tags with JSON data
        r = await c.get(BASE + "/site/fundacionepm/programacion/")
        html = r.text
        # Find all script tags
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        for i, s in enumerate(scripts[:5]):
            if 'event' in s.lower() or 'agenda' in s.lower() or 'fecha' in s.lower():
                print(f"Script {i} (contains event data):", s[:500])
        
        # Find data-attributes
        data_attrs = re.findall(r'data-[a-z-]+=[\'"]\{[^\'">]+\}[\'"]', html)
        print(f"\nData attributes found: {len(data_attrs)}")
        for attr in data_attrs[:5]:
            print(" ", attr[:200])
        
        # Look for any JSON inline
        json_blobs = re.findall(r'\{["\'](?:eventos|events|agenda)["\'][^\}]{20,}', html)
        print(f"\nJSON blobs: {len(json_blobs)}")
        for b in json_blobs[:3]:
            print(" ", b[:300])

asyncio.run(probe())
