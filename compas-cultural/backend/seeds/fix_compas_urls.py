"""
Fix broken fuente_url on existing Compás Urbano events.

Fetches the live API and updates fuente_url for all events in the DB
that came from compas_urbano and have a compasurbano.com URL (old format)
when the API has a real external web URL (web field).

Run from: compas-cultural/backend/
  python seeds/fix_compas_urls.py
"""
import asyncio
import re
import sys
import os
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from app.database import supabase

COMPAS_API_URL = "https://www.apicompasurbano.com/Catalog/MacroEventos.json"
COMPAS_BASE_URL = "https://www.compasurbano.com"


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


def _get_fuente_url(ev: dict) -> str | None:
    web = (ev.get("web") or "").strip()
    if web and web not in ("null", "undefined", ".") and web.lower().startswith("http"):
        return web
    link = (ev.get("linkModoIngreso") or "").strip()
    if link and link not in ("null", "undefined") and link.lower().startswith("http"):
        return link
    ev_id = ev.get("id")
    slug = _slugify((ev.get("nombre") or ""))
    if ev_id and slug:
        return f"{COMPAS_BASE_URL}/evento/{slug}/{ev_id}"
    return None


async def main():
    print("Fetching Compás Urbano API...")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.compasurbano.com/",
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(COMPAS_API_URL, headers=headers)
        raw_events = resp.json()

    print(f"  {len(raw_events)} eventos del API")

    # Build index: slug → correct URL
    api_by_slug: dict[str, str] = {}
    for ev in raw_events:
        nombre = (ev.get("nombre") or "").strip()
        if not nombre:
            continue
        slug = _slugify(nombre)
        url = _get_fuente_url(ev)
        if url:
            api_by_slug[slug] = url

    print(f"  {len(api_by_slug)} slugs con URL válida en API")

    # Fetch all compasurbano events from DB
    resp_db = (
        supabase.table("eventos")
        .select("id,slug,fuente_url,titulo")
        .like("fuente", "%compas_urbano%")
        .execute()
    )
    db_events = resp_db.data or []
    print(f"  {len(db_events)} eventos compas_urbano en BD")

    fixed = 0
    skipped = 0
    for ev_db in db_events:
        slug = ev_db.get("slug", "")
        current_url = ev_db.get("fuente_url") or ""
        correct_url = api_by_slug.get(slug)

        if not correct_url:
            skipped += 1
            continue

        if correct_url == current_url:
            skipped += 1
            continue

        # Check if current URL is the old broken format
        is_old_format = "compasurbano.com/eventos/ciudad/" in current_url
        is_missing = not current_url
        if not (is_old_format or is_missing):
            # Already has an external URL — don't overwrite
            skipped += 1
            continue

        supabase.table("eventos").update({
            "fuente_url": correct_url,
        }).eq("id", ev_db["id"]).execute()
        fixed += 1
        print(f"  [FIX] {ev_db.get('titulo','')[:50]}")
        print(f"        {current_url[:60]} → {correct_url[:60]}")

    print(f"\nCompletado: {fixed} URLs corregidas, {skipped} sin cambios")


if __name__ == "__main__":
    asyncio.run(main())
