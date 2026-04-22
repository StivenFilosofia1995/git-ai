"""
update_sitio_web.py — Actualiza sitio_web masivamente desde external_url de Instagram.

Usa Playwright para interceptar las llamadas XHR internas de Instagram
y extrae el external_url (sitio web) que el perfil tiene configurado.

Uso:
    cd backend
    python seeds/update_sitio_web.py
    python seeds/update_sitio_web.py --dry-run
    python seeds/update_sitio_web.py --max 50
    python seeds/update_sitio_web.py --tipo colectivo
"""

import sys, os, re, time, argparse, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.database import supabase
from app.services.instagram_pw_scraper import fetch_ig_profile


async def process_batch(lugares: list[dict], dry_run: bool) -> tuple[int, int]:
    saved = 0
    not_found = 0
    for lugar in lugares:
        nombre = lugar["nombre"]
        handle = lugar["instagram_handle"]
        lid = lugar["id"]

        print(f"  📷 @{handle:<30s} {nombre[:35]}")
        profile = await fetch_ig_profile(handle)

        if not profile:
            print(f"       ✗ sin respuesta")
            not_found += 1
        elif not profile.get("external_url"):
            bio = profile.get("biography", "")[:60]
            print(f"       ✗ sin web | bio: {bio!r}")
            not_found += 1
        else:
            web = profile["external_url"]
            print(f"       ✅ {web}")
            saved += 1
            if not dry_run:
                try:
                    supabase.table("lugares").update({"sitio_web": web}).eq("id", lid).execute()
                except Exception as e:
                    print(f"       ❌ error BD: {e}")
                    saved -= 1

        # Small pause between profiles to avoid rate-limiting
        await asyncio.sleep(2)

    return saved, not_found


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--tipo", type=str, default="")
    args = parser.parse_args()

    print("🔍 Consultando lugares con Instagram pero sin sitio_web...")
    query = (
        supabase.table("lugares")
        .select("id,nombre,tipo,instagram_handle")
        .not_.is_("instagram_handle", "null")
        .is_("sitio_web", "null")
    )
    if args.tipo:
        query = query.eq("tipo", args.tipo)
    result = query.execute()
    lugares = result.data or []
    if args.max:
        lugares = lugares[: args.max]
    print(f"   → {len(lugares)} lugares\n")

    saved, not_found = await process_batch(lugares, args.dry_run)

    print(f"\n{'='*55}")
    print(f"✅ Guardados:      {saved}")
    print(f"❌ Sin web:        {not_found}")
    if args.dry_run:
        print("⚠️  DRY-RUN: nada escrito en BD")


if __name__ == "__main__":
    asyncio.run(main())


