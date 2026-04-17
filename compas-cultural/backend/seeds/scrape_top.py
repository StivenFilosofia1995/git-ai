"""Scrape top cultural venues with known working websites."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import supabase
from app.services.auto_scraper import _scrape_lugar, _log_scraping

SLUGS = [
    "museo-de-arte-moderno-de-medellin",  # elmamm.org
    "mamm",                                # elmamm.org
    "teatro-popular-de-medellin",          # teatropopulardemedellin.com
    "teatro-oficina-central",              # teatrooficinacentral.com
    "el-aguila-descalza",                  # aguiladescalza.com.co
    "el-club-del-jazz",                    # elclubdeljazz.com
    "corporacion-otraparte",               # otraparte.org
    "pequeno-teatro-de-medellin",          # pequenoteatro.com
    "festival-poesia-medellin",            # festivaldepoesiademedellin.org
    "centro-colombo-americano",            # colomboworld.com
]

async def main():
    total = {"nuevos": 0, "duplicados": 0, "errores": 0}
    
    for slug in SLUGS:
        resp = supabase.table("lugares").select(
            "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
        ).eq("slug", slug).execute()
        if not resp.data:
            print(f"No encontrado: {slug}")
            continue
        lugar = resp.data[0]
        print(f"\n=== {lugar['nombre']} ===")
        stats = await _scrape_lugar(lugar)
        total["nuevos"] += stats["nuevos"]
        total["duplicados"] += stats["duplicados"]
        total["errores"] += stats["errores"]
        print(f"  -> nuevos={stats['nuevos']}, dup={stats['duplicados']}, err={stats['errores']}")
        _log_scraping(
            fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
            registros_nuevos=stats["nuevos"],
            errores=stats["errores"],
            detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"]},
        )
        await asyncio.sleep(2)
    
    print(f"\n=== TOTAL: nuevos={total['nuevos']}, dup={total['duplicados']}, err={total['errores']} ===")

if __name__ == "__main__":
    asyncio.run(main())
