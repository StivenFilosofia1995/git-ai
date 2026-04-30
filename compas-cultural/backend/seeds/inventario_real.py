"""Inventario real de espacios (tabla: lugares) - bibliotecas, UVAs, EPM."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")
from app.database import supabase

today = "2026-04-30"

# 1. Todos los lugares tipo biblioteca/uva/EPM
print("=== LUGARES con 'biblio', 'uva', 'epm', 'piloto', 'deseos', 'museo' ===")
r = supabase.table("lugares").select("id, nombre, tipo, categoria_principal, barrio, zona, slug, municipio").execute()
libs = []
for e in r.data:
    nombre = (e.get("nombre") or "").lower()
    if any(kw in nombre for kw in ["biblio", "uva ", "uva_", " uva", "epm", "piloto", "deseos", "museo agua", "parque"]):
        libs.append(e)

for e in libs:
    ev_r = supabase.table("eventos").select("id", count="exact").eq("espacio_id", e["id"]).gte("fecha_inicio", today).execute()
    n = ev_r.count or 0
    print(f"\n  {e['nombre']}")
    print(f"    id={e['id']}")
    print(f"    tipo={e.get('tipo')} | cat={e.get('categoria_principal')} | barrio={e.get('barrio')} | zona={e.get('zona')}")
    print(f"    eventos_futuros={n}")

# 2. Total lugares
print(f"\n=== TOTAL lugares en BD: {len(r.data)} ===")

# 3. Categorias disponibles
print("\n=== CATEGORIAS de eventos (muestra) ===")
ev_r = supabase.table("eventos").select("categoria_principal, espacio_id").limit(20).execute()
cats = set(e.get("categoria_principal") for e in ev_r.data)
print(f"  Categorias en uso: {sorted(cats)}")

# 4. Columnas de la tabla lugares (detectar si tiene zona/barrio)
print("\n=== COLUMNAS lugares (primer registro) ===")
sample = supabase.table("lugares").select("*").limit(1).execute()
if sample.data:
    print(f"  Keys: {sorted(sample.data[0].keys())}")
