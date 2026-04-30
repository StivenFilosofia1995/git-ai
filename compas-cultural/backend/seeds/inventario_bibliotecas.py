"""Inventario completo: espacios de bibliotecas/UVAs en BD y sus eventos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")
from app.database import supabase

today = "2026-04-30"

# Listar espacios tipo biblioteca/UVA
print("=== ESPACIOS tipo biblioteca/uva/cultura ===")
r = supabase.table("espacios").select("id, nombre, tipo, barrio, zona, slug").execute()
for e in r.data:
    nombre = e.get("nombre", "")
    tipo = e.get("tipo", "")
    if any(kw in nombre.lower() for kw in ["biblio", "uva", "epm", "piloto", "deseos", "museo", "comunit"]):
        eventos_r = supabase.table("eventos").select("id", count="exact").eq("espacio_id", e["id"]).gte("fecha_inicio", today).execute()
        n_ev = eventos_r.count or 0
        print(f"  [{tipo}] {nombre}")
        print(f"    id={e['id']} | barrio={e.get('barrio')} | zona={e.get('zona')} | eventos_futuros={n_ev}")

# Categorias disponibles en eventos
print("\n=== CATEGORIAS en uso ===")
cats_r = supabase.rpc("sql", {"query": "SELECT categoria_principal, count(*) FROM eventos GROUP BY categoria_principal ORDER BY count DESC LIMIT 20"}).execute()
print(cats_r.data)
