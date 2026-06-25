"""Debug: test Claude extraction with Comfama agenda."""
import json, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import anthropic
from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

content = """Agenda Comfama | Agenda cultural de Medellin y Antioquia
Conciertos: Nino de Elche - Cante a lo gitano | Sabado 18 de abril 8:00 p.m. Patio Teatro del Claustro Comfama

Programacion para abril:
Cine:
- 21 Abr: Cineclub El arbol rojo - La Capilla del Claustro Comfama
- 22 Abr: Cineclub El arbol rojo - La Capilla del Claustro Comfama

Charlas:
- 22 Abr: Lectura en voz alta - Biblioparque Bello
- 23 Abr: Club de lectura del mundo - Claustro Comfama
- 23 Abr: Lectura en voz alta - Copacabana
- 24 Abr: BibliObservatorio contemplar el cielo - La Estrella
- 24 Abr: Club de escritura Club de los poetas muertos - Claustro Comfama
- 24 Abr: Lectura en voz alta - Girardota Auditorio La Ceiba
- 25 Abr: Club de lectura del mundo - Claustro Comfama
- 26 Abr: Sabado de colores Colores del mundo - Claustro Comfama

Talleres:
- 20 Abr: Taller de pintura con cafe - Casa Comfama Otraparte

Conciertos:
- 18 Abr: Nino de Elche Cante a lo gitano - Patio Teatro Claustro Comfama
- 26 Abr: Juan Cirerol - Patio Teatro Claustro Comfama

Teatro:
- 19 Abr: La partida - Teatro Comfama
- 20 Abr: Pinocho el musical - Teatro Comfama
- 25 Abr: Azul - Teatro Comfama
- 26 Abr: De cuentos y espantos - Teatro Comfama

Danza:
- 26 Abr: Improvisacion en movimiento danza contemporanea - Claustro Comfama

Exposiciones:
- 18 Abr: Medellin a traves de los colectivos - Claustro Comfama
"""

prompt = f"""Analiza esta agenda cultural de Comfama (Medellin, Colombia) y extrae TODOS los eventos futuros como JSON.
Fecha actual: 2026-04-16T00:00:00. Usa year 2026 para todos.

Contenido:
---
{content}
---

Responde SOLO con un JSON valido (sin texto extra):
{{"eventos": [{{"titulo": "nombre", "categoria_principal": "teatro|musica_en_vivo|cine|danza|galeria|otro", "categorias": ["lista"], "fecha_inicio": "2026-04-DDTHH:MM:SS", "fecha_fin": null, "descripcion": "breve", "precio": "No especificado", "es_gratuito": false, "es_recurrente": false, "imagen_url": null}}]}}
"""

resp = client.messages.create(
    model=settings.anthropic_model,
    max_tokens=4096,
    temperature=0.1,
    messages=[{"role": "user", "content": prompt}],
)
raw = resp.content[0].text.strip()
if raw.startswith("```"):
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # Try fixing trailing commas
    fixed = re.sub(r",\s*([}\]])", r"\1", raw)
    data = json.loads(fixed)

events = data.get("eventos", [])
print(f"Eventos extraidos: {len(events)}")
for e in events[:20]:
    print(f"  {e['fecha_inicio'][:10]} | {e['titulo'][:60]:60s} | {e['categoria_principal']}")
if len(events) > 20:
    print(f"  ... y {len(events)-20} mas")
