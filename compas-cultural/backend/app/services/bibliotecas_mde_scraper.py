"""
bibliotecas_mde_scraper.py
Scraper async para la Red de Bibliotecas Públicas de Medellín.

Fuente: bibliotecasmedellin.gov.co (WordPress, CPT cpt_eventos_mes)
Estrategia:
  1. Lista paginada via WP REST API (/wp-json/wp/v2/cpt_eventos_mes)
  2. Scraping concurrente de cada página de evento (fecha, hora, sede, descripción)
  3. Match de sede contra DB lugares (con mapa de overrides y fuzzy)
  4. Upsert idempotente por slug

Todos los eventos son gratuitos (política de la Red de Bibliotecas).
"""
import asyncio
import re
import unicodedata
import uuid
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.database import supabase

CO_TZ = ZoneInfo("America/Bogota")
BASE = "https://bibliotecasmedellin.gov.co"
HUB_SLUG = "sistema-de-bibliotecas-publicas-de-medellin"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
}

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Venue overrides: sitio web → slug del lugar en BD
_VENUE_OVERRIDES = {
    "Parque al Barrio en Bibliometro": "bibliometro-medellin",
    "Parque al Barrio en la Institución Maestro Guillermo Vélez Vélez": "institucion-guillermo-velez-velez",
    "Parque al Barrio en la UVA de la Cordialidad": "uva-de-la-cordialidad",
    "Parque al Barrio / UVA Nuevo Amanecer": "uva-nuevo-amanecer",
}

# Keyword pairs for fuzzy venue matching
_KEYWORD_PAIRS = [
    ("botero", "botero"), ("carrasquilla", "carrasquilla"), ("greiff", "greiff"),
    ("ladera", "ladera"), ("vallejo", "vallejo"), ("guayabal", "guayabal"),
    ("doce", "doce"), ("occidente", "occidente"), ("javier", "javier"),
    ("floresta", "floresta"), ("altavista", "altavista"), ("poblado", "poblado"),
    ("santa cruz", "santa cruz"), ("limonar", "limonar"), ("avila", "avila"),
    ("granizal", "granizal"), ("palmitas", "palmitas"), ("german", "german"),
    ("jordan", "jordan"), ("manrique", "manrique"), ("aranjuez", "aranjuez"),
    ("castilla", "castilla"), ("belén", "belen"), ("belen", "belen"),
    ("españa", "espana"), ("espana", "espana"),
]

_VENUE_KWS = [
    "biblioteca", "parque", "uva", "unidad de vida",
    "casa de la literatura", "centro de documentaci",
]
_SKIP_KWS = ["derechos", "©", "conócenos", "aliados", "buscar"]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text.strip()).strip("-")[:70]


def _parse_date_es(s: str) -> Optional[str]:
    m = re.match(r"(\w+)\s+(\d{1,2}),\s+(\d{4})", (s or "").strip(), re.I)
    if m:
        mes_n, dia, anio = m.groups()
        mes_num = _MESES.get(mes_n.lower())
        if mes_num:
            try:
                return datetime(int(anio), mes_num, int(dia)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _parse_time_es(s: str) -> str:
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)\.?", (s or "").strip(), re.I)
    if m:
        h, mn, ampm = m.groups()
        h, mn = int(h), int(mn)
        if ampm.lower() == "pm" and h != 12:
            h += 12
        elif ampm.lower() == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mn:02d}:00"
    return "10:00:00"


# ─── Venue map (cargado una vez por ejecución) ───────────────────────────────

def _build_venue_map() -> dict:
    venue_map: dict = {}
    offset = 0
    while True:
        r = supabase.table("lugares").select(
            "id,nombre,slug,barrio,municipio"
        ).range(offset, offset + 199).execute()
        if not r.data:
            break
        for l in r.data:
            n = l.get("nombre") or ""
            nl = n.lower()
            if any(k in nl for k in ["biblio", "uva", "parque biblioteca", "casa de la literatura", "documentaci", "velez velez"]):
                venue_map[n] = l
                venue_map[_slugify(n)] = l
            venue_map["__slug__" + l["slug"]] = l
        if len(r.data) < 200:
            break
        offset += 200
    return venue_map


def _find_lugar(venue_name: str, venue_map: dict, hub: Optional[dict]) -> Optional[dict]:
    if not venue_name:
        return hub
    s_venue = _slugify(venue_name)
    for ovr_name, ovr_slug in _VENUE_OVERRIDES.items():
        if _slugify(ovr_name) == s_venue:
            k = "__slug__" + ovr_slug
            if k in venue_map:
                return venue_map[k]
    if venue_name in venue_map:
        return venue_map[venue_name]
    if s_venue in venue_map:
        return venue_map[s_venue]
    vl = venue_name.lower()
    for a, b in _KEYWORD_PAIRS:
        if a in vl:
            for key, lugar in venue_map.items():
                if isinstance(key, str) and b in key.lower():
                    return lugar
    return hub


# ─── Scrape de página individual de evento ───────────────────────────────────

async def _scrape_event_page(title: str, url: str, client: httpx.AsyncClient) -> dict:
    try:
        resp = await client.get(url, timeout=14)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "url": url, "title": title}
        soup = BeautifulSoup(resp.text, "html.parser")

        texts = []
        seen: set = set()
        for c in soup.find_all(class_="elementor-widget-container"):
            t = c.get_text(" ", strip=True)
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                texts.append(t)

        # Date: "mayo 23, 2026"
        date_str = None
        date_idx = -1
        for i, t in enumerate(texts):
            if re.match(r"^\w+\s+\d{1,2},\s+\d{4}$", t.strip(), re.I):
                if any(mes in t.lower() for mes in _MESES):
                    date_str = t.strip()
                    date_idx = i
                    break

        # Time: "4:00 pm."
        time_str = None
        window = texts[date_idx:date_idx + 5] if date_idx >= 0 else texts[:10]
        for t in window:
            if re.match(r"^\d{1,2}:\d{2}\s*[ap]m\.?$", t.strip(), re.I):
                time_str = t.strip()
                break

        # Venue: first widget with library keywords
        venue_str = None
        for t in texts[:25]:
            tl = t.lower()
            if any(k in tl for k in _VENUE_KWS) and len(t) < 200:
                if not any(s in tl for s in _SKIP_KWS):
                    venue_str = t.strip()
                    break

        # Description: longest non-nav text
        footer_kws = {"©", "conócenos", "derechos reservados", "facebook", "instagram", "youtube"}
        desc_str = None
        for t in texts:
            if len(t) > 80 and not any(f in t.lower() for f in footer_kws):
                desc_str = t[:800]
                break

        return {
            "title": title, "url": url,
            "venue": venue_str, "date_str": date_str,
            "time_str": time_str, "description": desc_str,
        }
    except Exception as e:
        return {"error": str(e), "url": url, "title": title}


# ─── Paginación del listado ───────────────────────────────────────────────────

async def _fetch_event_list(pages: int, client: httpx.AsyncClient) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for page_num in range(1, pages + 1):
        try:
            resp = await client.get(
                f"{BASE}/wp-json/wp/v2/cpt_eventos_mes",
                params={"per_page": 100, "page": page_num, "_fields": "id,title,link"},
                timeout=20,
            )
            if resp.status_code != 200:
                print(f"  [bibliotecas] Página {page_num}: HTTP {resp.status_code}, parando")
                break
            data = resp.json()
            if not data:
                break
            for e in data:
                events.append((e["title"]["rendered"], e["link"]))
            print(f"  [bibliotecas] Página {page_num}: {len(data)} eventos (acum: {len(events)})")
            await asyncio.sleep(0.15)
        except Exception as ex:
            print(f"  [bibliotecas] Error página {page_num}: {ex}")
            break
    return events


# ─── Entry point ─────────────────────────────────────────────────────────────

async def run_bibliotecas_mde_scraper(pages: int = 6, concurrency: int = 8) -> dict:
    """
    Scraper principal para la Red de Bibliotecas Públicas de Medellín.
    pages: número de páginas WP REST (100 eventos/página, default ~600)
    concurrency: máximo de requests paralelas a páginas individuales
    """
    print("\n📚 ═══════════════════════════════════════════════")
    print("   BIBLIOTECAS PÚBLICAS DE MEDELLÍN")
    print("═══════════════════════════════════════════════════")

    today = date.today().isoformat()
    stats = {"nuevos": 0, "duplicados": 0, "descartados": 0}

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        # 1. Cargar venue map y hub
        print("  → Cargando mapa de lugares...")
        venue_map = await asyncio.to_thread(_build_venue_map)
        hub_r = supabase.table("lugares").select("id,nombre,barrio,municipio").eq("slug", HUB_SLUG).execute()
        hub = hub_r.data[0] if hub_r.data else None
        print(f"  → {len(venue_map) // 2} lugares | Hub: {hub['nombre'] if hub else 'NO ENCONTRADO'}")

        # 2. Lista paginada
        print(f"  → Obteniendo lista ({pages} páginas)...")
        event_list = await _fetch_event_list(pages, client)
        print(f"  → {len(event_list)} eventos a scrapear")
        if not event_list:
            return stats

        # 3. Scraping concurrente con semáforo
        print(f"  → Scrapeando páginas (concurrency={concurrency})...")
        sem = asyncio.Semaphore(concurrency)

        async def _limited(title: str, url: str):
            async with sem:
                return await _scrape_event_page(title, url, client)

        results = await asyncio.gather(*[_limited(t, u) for t, u in event_list])

    # 4. Cargar existentes para dedup rápido
    try:
        ex_resp = (
            supabase.table("eventos")
            .select("slug,fuente_url")
            .eq("fuente", "bibliotecas_mde")
            .gte("fecha_inicio", today)
            .execute()
        )
        existing_slugs = {e["slug"] for e in (ex_resp.data or [])}
        existing_urls  = {e["fuente_url"] for e in (ex_resp.data or []) if e.get("fuente_url")}
    except Exception:
        existing_slugs, existing_urls = set(), set()

    # 5. Procesar e insertar
    print("  → Insertando en BD...")
    for r in results:
        if "error" in r:
            stats["descartados"] += 1
            continue

        fecha_str = _parse_date_es(r.get("date_str") or "") if r.get("date_str") else None
        if not fecha_str or fecha_str < today:
            stats["descartados"] += 1
            continue

        hora_str = _parse_time_es(r.get("time_str") or "")
        fecha_inicio = f"{fecha_str}T{hora_str}-05:00"

        lugar = _find_lugar(r.get("venue") or "", venue_map, hub)
        if not lugar:
            stats["descartados"] += 1
            continue

        title = r.get("title") or r.get("url", "").split("/")[-2]
        title = re.sub(r"<[^>]+>", "", title).strip()
        slug = f"biblio-mde-{_slugify(title)}-{fecha_str.replace('-', '')}"[:120]

        # Dedup por URL exacta
        if r.get("url") in existing_urls:
            stats["duplicados"] += 1
            continue
        # Dedup por slug
        if slug in existing_slugs:
            stats["duplicados"] += 1
            continue

        row = {
            "id": str(uuid.uuid4()),
            "slug": slug,
            "titulo": title[:255],
            "espacio_id": lugar["id"],
            "fecha_inicio": fecha_inicio,
            "hora_confirmada": hora_str != "10:00:00",
            "categoria_principal": "taller",
            "fuente": "bibliotecas_mde",
            "fuente_url": r.get("url", ""),
            "municipio": lugar.get("municipio") or "medellin",
            "barrio": lugar.get("barrio") or "",
            "nombre_lugar": lugar.get("nombre") or "Red de Bibliotecas Medellín",
            "es_gratuito": True,
            "precio": "Gratis",
            "descripcion": (r.get("description") or "")[:1000],
        }
        try:
            supabase.table("eventos").upsert(row, on_conflict="slug").execute()
            existing_slugs.add(slug)
            existing_urls.add(r.get("url", ""))
            stats["nuevos"] += 1
        except Exception as e:
            print(f"  ⚠ Error upsert {slug[:40]}: {e}")
            stats["descartados"] += 1

    print(
        f"  ✅ Bibliotecas: {stats['nuevos']} nuevos | "
        f"{stats['duplicados']} duplicados | {stats['descartados']} descartados"
    )
    return stats
