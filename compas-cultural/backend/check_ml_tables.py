"""Script para verificar compatibilidad de tablas ML con Supabase."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.database import supabase

results = []

def check(label, fn):
    try:
        fn()
        results.append(f"  OK  {label}")
    except Exception as e:
        results.append(f"  MISS {label}: {str(e)[:100]}")

# interacciones_usuario
check("interacciones_usuario (tabla)", lambda: supabase.table("interacciones_usuario").select("id").limit(1).execute())
check("interacciones_usuario.metadata (columna)", lambda: supabase.table("interacciones_usuario").select("metadata").limit(1).execute())
check("interacciones_usuario.tipo (columna)", lambda: supabase.table("interacciones_usuario").select("tipo").limit(1).execute())
check("interacciones_usuario.item_id (columna)", lambda: supabase.table("interacciones_usuario").select("item_id").limit(1).execute())

# perfiles_usuario
check("perfiles_usuario (tabla)", lambda: supabase.table("perfiles_usuario").select("id").limit(1).execute())
check("perfiles_usuario.ubicacion_lat (columna)", lambda: supabase.table("perfiles_usuario").select("ubicacion_lat").limit(1).execute())
check("perfiles_usuario.ubicacion_lng (columna)", lambda: supabase.table("perfiles_usuario").select("ubicacion_lng").limit(1).execute())
check("perfiles_usuario.preferencias (columna)", lambda: supabase.table("perfiles_usuario").select("preferencias").limit(1).execute())
check("perfiles_usuario.ubicacion_barrio (columna)", lambda: supabase.table("perfiles_usuario").select("ubicacion_barrio").limit(1).execute())

# historial_busqueda
check("historial_busqueda (tabla)", lambda: supabase.table("historial_busqueda").select("id").limit(1).execute())
check("historial_busqueda.categorias_resultado (columna)", lambda: supabase.table("historial_busqueda").select("categorias_resultado").limit(1).execute())

# scraping_schedule (nueva)
check("scraping_schedule (tabla nueva)", lambda: supabase.table("scraping_schedule").select("id").limit(1).execute())

# eventos - columnas usadas por ML
check("eventos.lat + lng (para Haversine)", lambda: supabase.table("eventos").select("lat,lng").limit(1).execute())
check("eventos.fuente_url (para Poisson)", lambda: supabase.table("eventos").select("fuente_url").limit(1).execute())
check("eventos.espacio_id (para rank_lugares)", lambda: supabase.table("eventos").select("espacio_id").limit(1).execute())

# lugares
check("lugares.instagram_handle (para IG scraping)", lambda: supabase.table("lugares").select("instagram_handle").limit(1).execute())
check("lugares.sitio_web (para web scraping)", lambda: supabase.table("lugares").select("sitio_web").limit(1).execute())

print("\n=== Diagnóstico ML Supabase ===")
for r in results:
    print(r)

missing = [r for r in results if "MISS" in r]
ok = [r for r in results if "  OK" in r]
print(f"\n{len(ok)}/{len(results)} tablas/columnas OK")
if missing:
    print("\nFALTAN (ejecutar migration SQL en Supabase SQL Editor):")
    for m in missing:
        print(" ", m)
