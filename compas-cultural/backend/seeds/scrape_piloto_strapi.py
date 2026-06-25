"""
Scraper para eventos de Biblioteca Pública Piloto via su Strapi CMS.
No usa AI - consulta directamente la API JSON de Strapi.
Inserta eventos futuros (próximos 90 días) en Supabase.
"""
import asyncio
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

import httpx

sys.path.insert(0, __file__.replace("\\seeds\\scrape_piloto_strapi.py", "").replace("/seeds/scrape_piloto_strapi.py", ""))
from app.database import supabase

STRAPI_BASE = "https://strapibppmain.cosmoteca.gov.co/api"
PAGE_SIZE = 100

# espacio_id de "Biblioteca Pública Piloto" en nuestra DB
PILOTO_ESPACIO_ID = "687f925b-5f2d-49f4-a6a9-899f7d4f7dd2"

CO_TZ_OFFSET = "-05:00"


def _strip_html(html_text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""

    class _Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)

    p = _Parser()
    p.feed(html_text)
    return " ".join(p.parts).strip()


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:200]


def _make_datetime(fecha: str, hora: str | None) -> str:
    """Combine Strapi date+time into ISO datetime string with CO timezone."""
    if hora:
        return f"{fecha}T{hora}{CO_TZ_OFFSET}"
    return f"{fecha}T00:00:00{CO_TZ_OFFSET}"


async def fetch_all_eventos() -> list[dict]:
    """Paginate through Strapi /eventos endpoint and return all records."""
    all_events = []
    page = 1
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=30) as c:
        while True:
            url = (
                f"{STRAPI_BASE}/eventos"
                f"?populate=*"
                f"&pagination[pageSize]={PAGE_SIZE}"
                f"&pagination[page]={page}"
                f"&sort=updatedAt:desc"
            )
            r = await c.get(url)
            data = r.json()
            items = data.get("data", [])
            if not items:
                break
            all_events.extend(items)
            total = data.get("meta", {}).get("pagination", {}).get("total", 0)
            print(f"  Fetched page {page}: {len(items)} events (total: {total})")
            if len(all_events) >= total:
                break
            page += 1

    return all_events


def strapi_event_to_db_rows(ev: dict, window_start: date, window_end: date) -> list[dict]:
    """
    Convert a Strapi event (with Sesiones) into one or more DB rows.
    Only returns rows for sessions within [window_start, window_end].
    """
    attrs = ev.get("attributes", {})
    ev_id = ev.get("id")

    nombre = (attrs.get("Nombre") or "").strip()
    miniatura = attrs.get("Miniatura") or {}
    titulo = (miniatura.get("Titulo") or nombre or "Sin título").strip()
    descripcion_html = miniatura.get("Texto") or attrs.get("Texto_principal") or ""
    descripcion = _strip_html(descripcion_html)[:1000]

    modalidad = attrs.get("Modalidad") or "Presencial"

    # Image
    imagen_url = None
    imagenes = attrs.get("Imagenes", {}).get("data") or []
    if imagenes:
        img_attrs = imagenes[0].get("attributes", {})
        # prefer medium/large format
        formats = img_attrs.get("formats", {})
        imagen_url = (
            (formats.get("medium") or {}).get("url")
            or (formats.get("large") or {}).get("url")
            or img_attrs.get("url")
        )

    rows = []
    sesiones = attrs.get("Sesiones") or []
    for ses in sesiones:
        fecha_str = ses.get("Fecha_inicio")
        if not fecha_str:
            continue
        try:
            fecha_date = date.fromisoformat(fecha_str)
        except ValueError:
            continue
        if fecha_date < window_start or fecha_date > window_end:
            continue

        hora_inicio = ses.get("Hora_inicio")
        hora_fin = ses.get("Hora_fin")
        fecha_fin_str = ses.get("Fecha_fin") or fecha_str

        fecha_inicio_iso = _make_datetime(fecha_str, hora_inicio)
        fecha_fin_iso = _make_datetime(fecha_fin_str, hora_fin) if hora_fin else None

        ses_id = ses.get("id", "")
        slug = f"piloto-{ev_id}-{ses_id}-{fecha_str}"

        rows.append({
            "id": str(uuid.uuid4()),
            "slug": slug,
            "titulo": titulo[:255],
            "descripcion": descripcion,
            "espacio_id": PILOTO_ESPACIO_ID,
            "fecha_inicio": fecha_inicio_iso,
            "fecha_fin": fecha_fin_iso,
            "imagen_url": imagen_url,
            "es_gratuito": True,
            "fuente": "web",
            "fuente_url": "https://bibliotecapiloto.gov.co/agenda",
            "municipio": "medellin",
            "categoria_principal": "casa_cultura",
        })
    return rows


async def main():
    today = date.today()
    window_end = today + timedelta(days=90)
    print(f"Scraping Piloto Strapi: {today} -> {window_end}")

    print("Fetching all events from Strapi...")
    all_strapi = await fetch_all_eventos()
    print(f"Total Strapi events: {len(all_strapi)}")

    db_rows = []
    for ev in all_strapi:
        rows = strapi_event_to_db_rows(ev, today, window_end)
        db_rows.extend(rows)

    print(f"Events matching date window: {len(db_rows)}")

    if not db_rows:
        print("No upcoming events found.")
        return

    inserted = 0
    skipped = 0
    for row in db_rows:
        try:
            supabase.table("eventos").upsert(row, on_conflict="slug").execute()
            inserted += 1
        except Exception as e:
            print(f"  Error: {e} — slug: {row.get('slug', '?')}")
            skipped += 1

    print(f"Done: {inserted} upserted, {skipped} errors.")


if __name__ == "__main__":
    asyncio.run(main())
