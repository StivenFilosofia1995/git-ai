"""
Diagnóstico completo: lugares de bibliotecas/UVAs en BD y fuentes web disponibles.
Código puro - sin AI.
"""
import sys, os, requests, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")
from app.database import supabase

SLUGS_BIBLIOS = [
    "sistema-de-bibliotecas-publicas-de-medellin",
    "biblioteca-epm",
    "fundacion-epm-agenda-cultural",
    "biblioteca-publica-piloto",
    "biblioteca-publica-piloto-de-medellin",
    "museo-del-agua-epm",
    "parque-biblioteca-espana-santo-domingo",
    "parque-biblioteca-belen",
    "parque-biblioteca-san-javier",
    "parque-biblioteca-la-ladera",
    "parque-biblioteca-tomás-carrasquilla",
    "parque-biblioteca-tomas-carrasquilla",
    "parque-biblioteca-san-cristobal",
    "parque-biblioteca-doce-de-octubre",
    "biblioteca-piloto",
    "fundacion-epm",
    "uva-orquideas",
    "uva-simon-bolivar",
    "uva-pajarito",
    "uva-la-esperanza",
    "uva-el-paraiso",
    "parque-de-los-deseos",
    "parque-deseos",
]

today = "2026-04-30"
print(f"=== BUSCANDO LUGARES POR SLUG ===")
found = []
for slug in SLUGS_BIBLIOS:
    r = supabase.table("lugares").select("id, nombre, sitio_web, categoria_principal, barrio, municipio").eq("slug", slug).execute()
    if r.data:
        l = r.data[0]
        ev_r = supabase.table("eventos").select("id", count="exact").eq("espacio_id", l["id"]).gte("fecha_inicio", today).execute()
        n = ev_r.count or 0
        print(f"  ✓ {l['nombre']}")
        print(f"    id={l['id']} | web={l.get('sitio_web')} | eventos_futuros={n}")
        found.append(l)
    else:
        print(f"  ✗ NO EXISTE: {slug}")

print(f"\n=== RESUMEN: {len(found)}/{len(SLUGS_BIBLIOS)} slugs encontrados ===")

# Buscar por patron en nombre
print("\n=== BUSCANDO POR NOMBRE (offset paginado) ===")
offset = 0
libs_by_name = []
while True:
    r = supabase.table("lugares").select("id, nombre, slug, sitio_web, categoria_principal, barrio").range(offset, offset+199).execute()
    if not r.data:
        break
    for l in r.data:
        n = (l.get("nombre") or "").lower()
        if any(k in n for k in ["biblio", "uva", "epm", "parque biblioteca", "deseos", "museo agua"]):
            libs_by_name.append(l)
    if len(r.data) < 200:
        break
    offset += 200

print(f"Lugares con keywords: {len(libs_by_name)}")
for l in libs_by_name:
    print(f"  {l['nombre']} | slug={l['slug']} | web={l.get('sitio_web')}")
