"""
Script de scraping urgente — corre localmente contra Supabase de producción.
Extrae eventos de los venues clave recién añadidos usando Groq.
Ejecutar: python seeds/scrape_ahora.py
"""
import sys, os, asyncio, json, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database import supabase
from app.services.groq_client import groq_chat, MODEL_FAST, MODEL_SMART
import httpx
from bs4 import BeautifulSoup

CO_TZ = ZoneInfo("America/Bogota")

def _now_co():
    return datetime.now(CO_TZ)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

# ── Venues clave con sus URLs ─────────────────────────────────────────────
TARGET_VENUES = [
    {"nombre": "Teatro Pablo Tobón Uribe",     "url": "https://teatropablotobon.com/eventos/",                         "categoria": "teatro",        "municipio": "medellin"},
    {"nombre": "Teatro Matacandelas",           "url": "https://www.matacandelas.com/index.html",                       "categoria": "teatro",        "municipio": "medellin"},
    {"nombre": "Teatro El Perpetuo Socorro",    "url": "https://www.elperpetuosocorro.org/",                            "categoria": "teatro",        "municipio": "medellin"},
    {"nombre": "Biblioteca Pública Piloto",     "url": "https://bibliotecapiloto.gov.co/agenda",                        "categoria": "casa_cultura",  "municipio": "medellin"},
    {"nombre": "Comfenalco Antioquia",          "url": "https://www.comfenalcoantioquia.com.co/personas/eventos",       "categoria": "centro_cultural","municipio": "medellin"},
    {"nombre": "Fundación EPM",                 "url": "https://www.fundacionepm.org.co/",                              "categoria": "centro_cultural","municipio": "medellin"},
    {"nombre": "Librería Café Exlibris",        "url": "https://www.exlibris.com.co/",                                  "categoria": "libreria",      "municipio": "medellin"},
    {"nombre": "Distrito San Ignacio",          "url": "http://agendacultural.distritosanignacio.com/",                 "categoria": "centro_cultural","municipio": "medellin"},
    {"nombre": "Vivir en el Poblado",           "url": "https://vivirenelpoblado.com/agenda-cultural/",                 "categoria": "festival",      "municipio": "medellin"},
    {"nombre": "Comfama – Agenda",              "url": "https://www.comfama.com/contenidos/entretenimiento/",           "categoria": "centro_cultural","municipio": "medellin"},
    {"nombre": "Plan B Medellín",               "url": "https://planbmedellin.com/",                                    "categoria": "musica_en_vivo","municipio": "medellin"},
]

PROMPT = """Eres experto en cultura urbana de Medellín, Colombia.
Analiza este contenido web y extrae TODOS los eventos culturales futuros.

Fecha actual: {fecha}
Año actual: {anio}
Fuente: {nombre} — {url}
Municipio: {municipio}

Contenido:
---
{contenido}
---

Responde SOLO JSON:
{{
  "eventos": [
    {{
      "titulo": "nombre del evento",
      "categoria_principal": "teatro|musica_en_vivo|danza|cine|taller|festival|galeria|libreria|casa_cultura|otro",
      "categorias": ["lista"],
      "fecha_inicio": "YYYY-MM-DDTHH:MM:SS",
      "fecha_fin": null,
      "descripcion": "descripción (máx 400 chars)",
      "nombre_lugar": "nombre del espacio si se menciona",
      "precio": "valor o Entrada libre",
      "es_gratuito": true/false,
      "imagen_url": null
    }}
  ]
}}

Reglas: solo eventos DESPUÉS de {fecha}. Si no hay eventos claros: {{"eventos": []}}"""


def _slugify(text):
    text = text.lower().strip()
    for a, b in [("áàä","a"),("éèë","e"),("íìï","i"),("óòö","o"),("úùü","u"),("ñ","n")]:
        for ch in a: text = text.replace(ch, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]


async def fetch(url):
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:image")
        og_img = og["content"] if og and og.get("content") else None
        for tag in soup(["script","style","nav","footer","noscript","svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if og_img:
            text = f"[OG_IMAGE: {og_img}]\n{text}"
        return text[:10000]
    except Exception as e:
        print(f"  ⚠ fetch error {url}: {e}")
        return None


def extract(prompt_text):
    # Usar MODEL_FAST (8b) — MODEL_SMART (70b) agotó cuota diaria
    raw = groq_chat(prompt_text, model=MODEL_FAST, max_tokens=4096, temperature=0)
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw).get("eventos", [])
    except:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", raw)).get("eventos", [])
        except:
            return []


async def scrape_venue(v):
    now = _now_co()
    hoy = now.replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"\n🌐 {v['nombre']} → {v['url']}")
    content = await fetch(v["url"])
    if not content:
        print("  ✗ Sin contenido")
        return 0

    prompt = PROMPT.format(
        fecha=now.isoformat(), anio=now.year,
        nombre=v["nombre"], url=v["url"],
        municipio=v["municipio"], contenido=content
    )
    events = extract(prompt)
    print(f"  📊 Groq extrajo {len(events)} evento(s)")

    nuevos = 0
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

        slug = _slugify(titulo)
        if supabase.table("eventos").select("id").eq("slug", slug).execute().data:
            continue  # ya existe

        # Buscar espacio_id en la BD
        espacio_id = None
        nombre_lugar = ev.get("nombre_lugar") or v["nombre"]
        slug_lugar = _slugify(v["nombre"])
        res = supabase.table("lugares").select("id").eq("slug", slug_lugar).execute()
        if res.data:
            espacio_id = res.data[0]["id"]

        try:
            supabase.table("eventos").insert({
                "titulo": titulo,
                "slug": slug,
                "espacio_id": espacio_id,
                "fecha_inicio": fecha.isoformat(),
                "fecha_fin": ev.get("fecha_fin"),
                "categorias": ev.get("categorias", [v["categoria"]]),
                "categoria_principal": ev.get("categoria_principal", v["categoria"]),
                "municipio": v["municipio"],
                "nombre_lugar": nombre_lugar,
                "descripcion": ev.get("descripcion"),
                "precio": ev.get("precio"),
                "es_gratuito": ev.get("es_gratuito", False),
                "imagen_url": ev.get("imagen_url"),
                "fuente": "scrape_manual",
                "fuente_url": v["url"],
                "verificado": False,
            }).execute()
            print(f"  ✅ {titulo[:70]}")
            nuevos += 1
        except Exception as e:
            print(f"  ❌ {titulo[:50]}: {e}")
    return nuevos


async def main():
    total = 0
    for v in TARGET_VENUES:
        n = await scrape_venue(v)
        total += n
        await asyncio.sleep(1)
    print(f"\n{'='*50}")
    print(f"✅ Total eventos insertados: {total}")


if __name__ == "__main__":
    asyncio.run(main())
