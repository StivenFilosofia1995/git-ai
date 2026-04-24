import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Supabase URL or Key not found in environment.")
    sys.exit(1)

supabase: Client = create_client(url, key)
CO_TZ = ZoneInfo("America/Bogota")
now = datetime.now(CO_TZ)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

# Buscar eventos de fuentes AI con fecha igual a medianoche (00:00:00) 
# o fechas inventadas por fallbacks (hora_confirmada = False)
resp = supabase.table("eventos").select("id, titulo, fecha_inicio, fuente").in_("fuente", ["auto_scraper_web", "auto_scraper_instagram_sin_hora", "social_listener", "scraping_llm"]).execute()

eventos = resp.data or []
sospechosos = []

for ev in eventos:
    # Si la fecha no se puede parsear o es hora 00:00:00
    if not ev.get("fecha_inicio"):
        continue
    try:
        fecha = datetime.fromisoformat(ev["fecha_inicio"])
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=CO_TZ)
        else:
            fecha = fecha.astimezone(CO_TZ)
        
        # Consideramos sospechosos a los eventos con hora exacta 00:00:00, o 19:00:00
        # provenientes de las fuentes LLM que solían fallar
        if (fecha.hour == 0 and fecha.minute == 0) or (fecha.hour == 19 and fecha.minute == 0):
            sospechosos.append(ev)
    except Exception:
        pass

print(f"Total de eventos revisados: {len(eventos)}")
print(f"Eventos sospechosos (posibles fake dates generadas por LLM): {len(sospechosos)}")

# Borrado activado a petición del usuario:
for ev in sospechosos:
    supabase.table("eventos").delete().eq("id", ev["id"]).execute()
print("Eventos falsos eliminados.")
