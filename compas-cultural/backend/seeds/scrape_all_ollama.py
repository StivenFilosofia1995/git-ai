"""
Scraper masivo utilizando todos los sitios web de la BD y Ollama (Qwen) local.
Ejecutar: python seeds/scrape_all_ollama.py
"""
import sys, os, asyncio, json, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.database import supabase
from app.services.ollama_client import ollama_chat
import httpx
from bs4 import BeautifulSoup

CO_TZ = ZoneInfo("America/Bogota")

def _now_co():
    return datetime.now(CO_TZ)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

SYS_PROMPT = """Eres un experto en cultura urbana de Medellín.
Extrae TODOS los eventos culturales futuros. Responde SOLO con JSON siguiendo esta estructura:
{
  "eventos": [
    {
      "titulo": "nombre",
      "categoria_principal": "teatro|musica_en_vivo|danza|cine|taller|festival|galeria|libreria|casa_cultura|centro_cultural|otro",
      "categorias": ["lista"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
      "descripcion": "Descripción (máx 400 chars)",
      "precio": "Entrada libre o precio",
      "es_gratuito": true
    }
  ]
}"""

def _slugify(text):
    text = text.lower().strip()
    for a, b in [("áàä","a"),("éèë","e"),("íìï","i"),("óòö","o"),("úùü","u"),("ñ","n")]:
        for ch in a: text = text.replace(ch, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]

async def fetch(url):
    if not url or not url.startswith('http'): return None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15, verify=False) as client:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000] # Limitar tokens
    except Exception as e:
        print(f"  - Fetch error en {url}: {e}")
        return None

def extract_events(text, nombre, url, municipio):
    now = _now_co()
    msg = f"Fecha actual: {now.isoformat()}\nFuente: {nombre} — {url}\nMunicipio: {municipio}\n\nContenido:\n{text}\n\nRegla: responde SOLO JSON, nada de markdown."
    
    raw = ollama_chat(
        system_prompt=SYS_PROMPT,
        messages=[{"role": "user", "content": msg}],
        max_tokens=2048,
        temperature=0.1
    )
    
    if not raw:
        return []
    
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    
    try:
        return json.loads(raw).get("eventos", [])
    except:
        return []

async def scrape_lugar(lugar):
    url = lugar.get("sitio_web")
    nombre = lugar.get("nombre")
    municipio = lugar.get("municipio", "medellin")
    
    print(f"\n Scraping: {nombre} -> {url}")
    content = await fetch(url)
    if not content:
        print("  - Sin contenido o inalcanzable")
        return 0
        
    events = extract_events(content, nombre, url, municipio)
    print(f"  - Ollama extrajo {len(events)} evento(s)")
    
    hoy = _now_co().replace(hour=0, minute=0, second=0, microsecond=0)
    insertados = 0
    
    for ev in events:
        titulo = ev.get("titulo", "").strip()
        if not titulo: continue
        fecha_str = ev.get("fecha_inicio")
        if not fecha_str: continue
        try:
            fecha = datetime.fromisoformat(fecha_str)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=CO_TZ)
            if fecha < hoy:
                continue
        except:
            continue
            
        slug = f"{_slugify(titulo)}-{fecha.strftime('%Y-%m-%d')}"
        import uuid
        
        try:
            supabase.table("eventos").upsert({
                "id": str(uuid.uuid4()), # Generar nuevo UUID si es necesario, pero upsert on conflict slug previene duplicados.
                "titulo": titulo,
                "slug": slug,
                "espacio_id": lugar["id"],
                "fecha_inicio": fecha.isoformat(),
                "categoria_principal": ev.get("categoria_principal", lugar.get("categoria_principal")),
                "municipio": municipio,
                "nombre_lugar": nombre,
                "descripcion": ev.get("descripcion", ""),
                "precio": ev.get("precio", ""),
                "es_gratuito": ev.get("es_gratuito", False),
                "fuente": "web_ollama",
                "fuente_url": url,
            }, on_conflict="slug").execute()
            print(f"  - Insertado/Actualizado: {titulo[:50]}")
            insertados += 1
        except Exception as e:
            print(f"  - Error insertando {titulo[:30]}: {e}")
            
    return insertados

async def main():
    print("Obteniendo todos los lugares con sitio_web de la BD...")
    res = supabase.table("lugares").select("id, nombre, sitio_web, categoria_principal, municipio").not_.is_("sitio_web", "null").neq("sitio_web", "").execute()
    
    lugares = res.data
    print(f"Total lugares a scrapear: {len(lugares)}")
    
    total_insertados = 0
    for lugar in lugares:
        n = await scrape_lugar(lugar)
        total_insertados += n
        await asyncio.sleep(0.5)
        
    print(f"\n=====================================")
    print(f" Proceso finalizado. Total eventos actualizados/insertados: {total_insertados}")

if __name__ == '__main__':
    asyncio.run(main())