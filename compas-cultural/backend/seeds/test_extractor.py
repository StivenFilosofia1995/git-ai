import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from app.services.html_event_extractor import extract_events_code

TESTS = [
    ("https://teatropablotobon.com/eventos/", "Teatro Pablo Tobon", "teatro", "medellin"),
    ("https://bibliotecapiloto.gov.co/agenda",  "Biblioteca Piloto",   "casa_cultura", "medellin"),
    ("https://www.matacandelas.com/index.html", "Teatro Matacandelas", "teatro", "medellin"),
]

async def run():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
        for url, nombre, cat, mun in TESTS:
            try:
                r = await c.get(url, headers=headers)
                html = r.text
                events = extract_events_code(html, url, nombre, cat, mun)
                print(f"\n{nombre}: {len(events)} eventos")
                for ev in events[:3]:
                    titulo = ev["titulo"]
                    fecha = ev["fecha_inicio"][:10]
                    src = ev["_source"]
                    print(f"  - {titulo[:60]} | {fecha} | {src}")
            except Exception as e:
                print(f"\n{nombre}: ERROR - {e}")

asyncio.run(run())
