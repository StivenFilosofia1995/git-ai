"""Verifica cuantos eventos hay en la BD y si se ven desde hoy."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")
from app.database import supabase
from datetime import date

today = date.today().isoformat()
print(f"Hoy: {today}")

# Eventos de Piloto
r = (supabase.table("eventos")
     .select("id, titulo, fecha_inicio")
     .eq("espacio_id", "687f925b-5f2d-49f4-a6a9-899f7d4f7dd2")
     .gte("fecha_inicio", today)
     .order("fecha_inicio")
     .limit(10)
     .execute())
print(f"Eventos Piloto desde hoy: {len(r.data)}")
for e in r.data[:5]:
    print(f"  {e['fecha_inicio'][:10]} | {e['titulo'][:60]}")

# Total eventos en BD desde hoy
r2 = (supabase.table("eventos")
      .select("id", count="exact")
      .gte("fecha_inicio", today)
      .execute())
print(f"\nTotal eventos en BD desde hoy: {r2.count}")

# Eventos de hoy especificamente
r3 = (supabase.table("eventos")
      .select("id, titulo, fecha_inicio, espacio_id")
      .gte("fecha_inicio", today + "T00:00:00")
      .lte("fecha_inicio", today + "T23:59:59")
      .order("fecha_inicio")
      .execute())
print(f"Eventos de HOY ({today}): {len(r3.data)}")
for e in r3.data[:10]:
    print(f"  {e['fecha_inicio'][11:16]} | {e['titulo'][:50]}")
