"""Quick: scrape a few known-good venues to populate more events."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import supabase
from app.services.auto_scraper import _scrape_lugar, _log_scraping

# Select lugares with websites that are likely not JS-rendered
GOOD_SLUGS = [
    # Known museums/theaters with real websites
    "museo-de-arte-moderno-de-medellin-mamm",
    "teatro-matacandelas",
    "museo-de-antioquia",
    "jardin-botanico-de-medellin",
    "parque-explora",
    "museo-el-castillo",
    "teatro-pablo-tobon-uribe",
    "teatro-universidad-de-medellin",
    # Comfama already done
]

async def main():
    total = {"nuevos": 0, "duplicados": 0, "errores": 0}
    
    for slug in GOOD_SLUGS:
        resp = supabase.table("lugares").select(
            "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
        ).eq("slug", slug).execute()
        if not resp.data:
            print(f"No encontrado: {slug}")
            continue
        lugar = resp.data[0]
        if not lugar.get("sitio_web") and not lugar.get("instagram_handle"):
            print(f"Sin fuente: {lugar['nombre']}")
            continue
        
        print(f"\n=== {lugar['nombre']} ===")
        stats = await _scrape_lugar(lugar)
        total["nuevos"] += stats["nuevos"]
        total["duplicados"] += stats["duplicados"]
        total["errores"] += stats["errores"]
        print(f"  -> nuevos={stats['nuevos']}, duplicados={stats['duplicados']}, errores={stats['errores']}")
        
        _log_scraping(
            fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
            registros_nuevos=stats["nuevos"],
            errores=stats["errores"],
            detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"]},
        )
        await asyncio.sleep(2)
    
    print(f"\n=== TOTAL: nuevos={total['nuevos']}, duplicados={total['duplicados']}, errores={total['errores']} ===")

if __name__ == "__main__":
    asyncio.run(main())
