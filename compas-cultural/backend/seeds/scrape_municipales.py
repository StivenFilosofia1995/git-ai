"""Quick script: ejecutar el auto-scraper solo en las fuentes municipales nuevas."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import supabase
from app.services.auto_scraper import _scrape_lugar, _log_scraping

SLUGS_MUNICIPALES = [
    "secretaria-cultura-bello",
    "secretaria-cultura-envigado",
    "secretaria-cultura-itagui",
    "alcaldia-sabaneta-cultura",
    "alcaldia-la-estrella-cultura",
    "alcaldia-copacabana-cultura",
    "alcaldia-caldas-cultura",
    "comfama-cultura",
    "secretaria-cultura-medellin",
]

async def main():
    print("🏛️  Scraping fuentes municipales...")
    
    total_stats = {"nuevos": 0, "duplicados": 0, "errores": 0}
    
    for slug in SLUGS_MUNICIPALES:
        resp = supabase.table("lugares").select(
            "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
        ).eq("slug", slug).execute()
        
        if not resp.data:
            print(f"  ⚠️  No encontrado: {slug}")
            continue
        
        lugar = resp.data[0]
        print(f"\n📍 {lugar['nombre']} ({lugar['municipio']})")
        
        try:
            stats = await _scrape_lugar(lugar)
            total_stats["nuevos"] += stats["nuevos"]
            total_stats["duplicados"] += stats["duplicados"]
            total_stats["errores"] += stats["errores"]
            
            _log_scraping(
                fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
                registros_nuevos=stats["nuevos"],
                errores=stats["errores"],
                detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"]},
            )
            
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            total_stats["errores"] += 1
    
    print(f"\n✅ ═══════════════════════════════════════")
    print(f"   Eventos nuevos: {total_stats['nuevos']}")
    print(f"   Duplicados: {total_stats['duplicados']}")
    print(f"   Errores: {total_stats['errores']}")
    print(f"═══════════════════════════════════════════")

if __name__ == "__main__":
    asyncio.run(main())
