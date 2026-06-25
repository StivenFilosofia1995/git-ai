"""Quick: scrape Comfama + Sabaneta."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import supabase
from app.services.auto_scraper import _scrape_lugar, _log_scraping

async def main():
    slugs = ["comfama-cultura", "alcaldia-sabaneta-cultura", "secretaria-cultura-bello", "secretaria-cultura-envigado"]
    for slug in slugs:
        resp = supabase.table("lugares").select(
            "id,nombre,slug,instagram_handle,sitio_web,categoria_principal,municipio,barrio"
        ).eq("slug", slug).execute()
        if not resp.data:
            print(f"No encontrado: {slug}")
            continue
        lugar = resp.data[0]
        print(f"\n=== {lugar['nombre']} ===")
        stats = await _scrape_lugar(lugar)
        print(f"Resultado: {stats}")
        _log_scraping(
            fuente=lugar.get("sitio_web") or lugar.get("instagram_handle", "unknown"),
            registros_nuevos=stats["nuevos"],
            errores=stats["errores"],
            detalle={"lugar": lugar["nombre"], "duplicados": stats["duplicados"]},
        )
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
