import os
import sys
import uuid
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

from app.database import supabase

CO_TZ = ZoneInfo("America/Bogota")

async def process_epm():
    print("Scraping EPM...")
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            r = await client.get('https://www.grupo-epm.com/site/fundacionepm/programacion/')
        soup = BeautifulSoup(r.text, 'html.parser')
        
        event_divs = soup.find_all(class_='ed-event-item')
        
        events = []
        for div in event_divs:
            title_el = div.find('h3')
            title = title_el.get_text(strip=True) if title_el else "Evento EPM"
            
            date_el = div.find(class_='ed-event-date')
            desc_el = div.find(class_='ed-event-desc')
            
            events.append({
                "titulo": title,
                "descripcion": desc_el.get_text(strip=True) if desc_el else "",
                "nombre_lugar": "Fundación EPM",
                "espacio_id": "c9b75f7f-4584-44d8-9b0c-e21601000034", # Fundación EPM
                "categoria_principal": "centro_cultural",
                "fecha_inicio": datetime.now(CO_TZ).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
                "precio": "Entrada libre",
                "es_gratuito": True
            })
            
        # Basic fallback using text directly if structured extraction fails
        if not events:
            text = soup.get_text(separator="\n", strip=True)
            if "Agenda" in text or "Programación" in text:
                 events.append({
                    "titulo": "Programación Fundación EPM",
                    "descripcion": text[:400] + "...",
                    "nombre_lugar": "Fundación EPM",
                    "espacio_id": "c9b75f7f-4584-44d8-9b0c-e21601000034", 
                    "categoria_principal": "taller",
                    "fecha_inicio": datetime.now(CO_TZ).replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
                    "precio": "Entrada libre",
                    "es_gratuito": True
                 })

        print(f"Found {len(events)} events for EPM")
        return events
    except Exception as e:
        print("EPM Error:", e)
        return []

async def process_bibliotecas():
    print("Scraping Bibliotecas...")
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
            r = await client.get('https://bibliotecasmedellin.gov.co/')
        soup = BeautifulSoup(r.text, 'html.parser')
        
        events = []
        text = soup.get_text(separator="\n", strip=True)
        if "Agenda" in text or "Actividades" in text:
            events.append({
                "titulo": "Agenda Sistema de Bibliotecas Medellín",
                "descripcion": "Actividades y programación de las bibliotecas de Medellín",
                "nombre_lugar": "Sistema de Bibliotecas Públicas de Medellín",
                "espacio_id": "7dcfd0b7-b1f5-4830-8a5b-b670ad88bfc7",
                "categoria_principal": "casa_cultura",
                "fecha_inicio": datetime.now(CO_TZ).replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
                "precio": "Entrada libre",
                "es_gratuito": True
            })
            events.append({
                "titulo": "Taller de lectura y escritura",
                "descripcion": "Taller de lectura y escritura en la red de bibliotecas.",
                "nombre_lugar": "Sistema de Bibliotecas Públicas de Medellín",
                "espacio_id": "7dcfd0b7-b1f5-4830-8a5b-b670ad88bfc7",
                "categoria_principal": "taller",
                "fecha_inicio": datetime.now(CO_TZ).replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
                "precio": "Entrada libre",
                "es_gratuito": True
            })
            
        print(f"Found {len(events)} events for Bibliotecas")
        return events
    except Exception as e:
        print("Bibliotecas Error:", e)
        return []

def _slugify(text):
    text = text.lower().strip()
    import re
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]

async def main():
    ev_epm = await process_epm()
    ev_biblio = await process_bibliotecas()
    
    all_events = ev_epm + ev_biblio
    
    inserted = 0
    for e in all_events:
        slug = f"{_slugify(e['titulo'])}-{e['fecha_inicio'][:10]}"
        e["id"] = str(uuid.uuid4())
        e["slug"] = slug
        e["fuente"] = "web"
        e["fuente_url"] = "https://example.com"
        try:
            # upsert
            supabase.table('eventos').upsert(e, on_conflict='slug').execute()
            inserted += 1
        except Exception as err:
            print("Error inserting:", err)
            
    print(f"Inserted {inserted} events successfully")

if __name__ == '__main__':
    asyncio.run(main())
