"""
Scraper: Red de Bibliotecas Públicas de Medellín
Fuente: bibliotecasmedellin.gov.co (WordPress, cpt_eventos_mes)
Extrae: fecha, hora, sede, descripción de cada actividad.
Código puro - sin AI. Threading para velocidad.

Uso:
    python seeds/scrape_bibliotecas_mde.py
    python seeds/scrape_bibliotecas_mde.py --pages 5  # (default: 10 páginas = ~1000 eventos)
    python seeds/scrape_bibliotecas_mde.py --dry-run   # sin insertar en BD
"""
import sys, os, re, uuid, time, argparse
import unicodedata
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

from app.database import supabase

# ── Config ──────────────────────────────────────────────────────────────────
BASE = "https://bibliotecasmedellin.gov.co"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TODAY = date.today().isoformat()
WORKERS = 5          # Concurrent HTTP workers
REQUEST_TIMEOUT = 12 # seconds per page

# Venue names on the website that don't slug-match the DB slug directly.
# Map: exact website venue string → DB slug
VENUE_SLUG_OVERRIDES: dict[str, str] = {
    "Parque al Barrio en Bibliometro":                              "bibliometro-medellin",
    "Parque al Barrio en la Institución Maestro Guillermo Vélez Vélez": "institucion-guillermo-velez-velez",
    "Parque al Barrio en la UVA de la Cordialidad":                 "uva-de-la-cordialidad",
    "Parque al Barrio / UVA Nuevo Amanecer":                        "uva-nuevo-amanecer",
}

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text.strip())
    return text[:70].strip("-")


def parse_date_es(s: str):
    """'mayo 23, 2026' → '2026-05-23'  |  None si no parsea"""
    m = re.match(r"(\w+)\s+(\d{1,2}),\s+(\d{4})", s.strip(), re.I)
    if m:
        mes_n, dia, anio = m.groups()
        mes_num = MESES_ES.get(mes_n.lower())
        if mes_num:
            try:
                return datetime(int(anio), mes_num, int(dia)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def parse_time_es(s: str) -> str:
    """'4:00 pm.' → '16:00:00'  |  '10:00:00' si no parsea"""
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)\.?", s.strip(), re.I)
    if m:
        h, mn, ampm = m.groups()
        h, mn = int(h), int(mn)
        if ampm.lower() == "pm" and h != 12:
            h += 12
        elif ampm.lower() == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mn:02d}:00"
    return "10:00:00"


# ── Scrape one event page ────────────────────────────────────────────────────
def scrape_event(title: str, url: str):
    """Returns dict with venue/date_str/time_str/description or error key."""
    try:
        resp = requests.get(url, headers=H, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "url": url}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect unique widget-container texts in DOM order
        texts = []
        seen: set = set()
        for c in soup.find_all(class_="elementor-widget-container"):
            t = c.get_text(" ", strip=True)
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                texts.append(t)

        # ── Date: "mayo 23, 2026" ──
        date_str = None
        date_idx = -1
        for i, t in enumerate(texts):
            if re.match(r"^\w+\s+\d{1,2},\s+\d{4}$", t.strip(), re.I):
                if any(mes in t.lower() for mes in MESES_ES):
                    date_str = t.strip()
                    date_idx = i
                    break

        # ── Time: "4:00 pm." ──
        time_str = None
        window = texts[date_idx : date_idx + 5] if date_idx >= 0 else texts[:10]
        for t in window:
            if re.match(r"^\d{1,2}:\d{2}\s*[ap]m\.?$", t.strip(), re.I):
                time_str = t.strip()
                break

        # ── Venue: first widget containing library keywords ──
        venue_kws = [
            "biblioteca", "parque", "uva", "unidad de vida",
            "casa de la literatura", "centro de documentación",
            "centro de documentacion",
        ]
        skip_kws = ["derechos", "©", "conócenos", "aliados", "buscar", "convertic"]
        venue_str = None
        for t in texts[:25]:
            tl = t.lower()
            if any(k in tl for k in venue_kws) and len(t) < 200:
                if not any(s in tl for s in skip_kws):
                    venue_str = t.strip()
                    break

        # ── Description: longest non-nav text ──
        footer_kws = {"©", "conócenos", "derechos reservados", "facebook", "instagram", "youtube"}
        desc_str = None
        for t in texts:
            if len(t) > 80:
                tl = t.lower()
                if not any(f in tl for f in footer_kws):
                    desc_str = t[:800]
                    break

        return {
            "title": title,
            "url": url,
            "venue": venue_str,
            "date_str": date_str,
            "time_str": time_str,
            "description": desc_str,
        }
    except Exception as e:
        return {"error": str(e), "url": url}


# ── Venue → lugar_id map ─────────────────────────────────────────────────────
def build_venue_map():
    """Returns dict: normalized_key → lugar dict, for all library/UVA spaces."""
    venue_map = {}
    offset = 0
    while True:
        r = supabase.table("lugares").select(
            "id, nombre, slug, barrio, municipio"
        ).range(offset, offset + 199).execute()
        if not r.data:
            break
        for l in r.data:
            n = l.get("nombre") or ""
            nl = n.lower()
            if any(k in nl for k in ["biblio", "uva", "parque biblioteca", "casa de la literatura", "documentaci", "velez velez"]):
                venue_map[n] = l            # exact name key
                venue_map[slugify(n)] = l   # slugified key
            # Also index by slug directly for override lookups
            venue_map["__slug__" + l["slug"]] = l
        if len(r.data) < 200:
            break
        offset += 200
    return venue_map


def find_lugar(venue_name: str, venue_map: dict, hub: dict):
    """Find best matching lugar, fallback to hub."""
    if not venue_name:
        return hub

    # 0. Hardcoded overrides — compare by slug to avoid accent encoding mismatches
    s_venue = slugify(venue_name)
    for override_name, override_slug in VENUE_SLUG_OVERRIDES.items():
        if slugify(override_name) == s_venue:
            slug_key = "__slug__" + override_slug
            if slug_key in venue_map:
                return venue_map[slug_key]

    # 1. Exact
    if venue_name in venue_map:
        return venue_map[venue_name]
    # 2. Slug match
    s = slugify(venue_name)
    if s in venue_map:
        return venue_map[s]
    # 3. Keyword match
    vl = venue_name.lower()
    PAIRS = [
        ("botero", "botero"),
        ("carrasquilla", "carrasquilla"),
        ("greiff", "greiff"),
        ("ladera", "ladera"),
        ("vallejo", "vallejo"),
        ("guayabal", "guayabal"),
        ("doce", "doce"),
        ("occidente", "occidente"),
        ("javier", "javier"),
        ("floresta", "floresta"),
        ("altavista", "altavista"),
        ("poblado", "poblado"),
        ("santa cruz", "santa cruz"),
        ("limonar", "limonar"),
        ("avila", "avila"),
        ("granizal", "granizal"),
        ("palmitas", "palmitas"),
        ("san german", "german"),
        ("jordan", "jordan"),
    ]
    for a, b in PAIRS:
        if a in vl:
            for key, lugar in venue_map.items():
                if isinstance(key, str) and b in key.lower():
                    return lugar
    # Belén / España special (accents)
    if "belen" in slugify(vl):
        for key, lugar in venue_map.items():
            if isinstance(key, str) and "belen" in slugify(key):
                return lugar
    if "espana" in slugify(vl) or "españa" in vl:
        for key, lugar in venue_map.items():
            if isinstance(key, str) and "espana" in slugify(key):
                return lugar

    return hub  # Fallback: hub del sistema


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=10, help="Pages to fetch (100 events/page)")
    parser.add_argument("--dry-run", action="store_true", help="Don't insert to DB")
    args = parser.parse_args()

    print("=" * 60)
    print("SCRAPER: Red de Bibliotecas Públicas de Medellín")
    print(f"Hoy: {TODAY} | Páginas: {args.pages} | Dry-run: {args.dry_run}")
    print("=" * 60)

    # 1. Venue map
    print("\n[1] Cargando lugares de biblioteca...")
    venue_map = build_venue_map()
    print(f"    {len(venue_map) // 2} lugares encontrados")

    hub_r = supabase.table("lugares").select("id, nombre, barrio, municipio").eq(
        "slug", "sistema-de-bibliotecas-publicas-de-medellin"
    ).execute()
    hub = hub_r.data[0] if hub_r.data else None
    print(f"    Hub fallback: {hub['nombre'] if hub else 'NOT FOUND'}")

    # 2. Paginate cpt_eventos_mes
    print(f"\n[2] Obteniendo lista de actividades (hasta {args.pages} páginas)...")
    all_events = []
    for page_num in range(1, args.pages + 1):
        resp = requests.get(
            f"{BASE}/wp-json/wp/v2/cpt_eventos_mes",
            params={"per_page": 100, "page": page_num, "_fields": "id,title,link"},
            headers=H,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"    Página {page_num}: HTTP {resp.status_code}, parando")
            break
        data = resp.json()
        if not data:
            break
        for e in data:
            all_events.append((e["title"]["rendered"], e["link"]))
        print(f"    Página {page_num}: {len(data)} eventos (acum: {len(all_events)})")
        time.sleep(0.2)

    print(f"\n    Total a scrapear: {len(all_events)}")

    # 3. Scrape pages concurrently
    print(f"\n[3] Scrapeando páginas con {WORKERS} workers...")
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(scrape_event, t, u): (t, u) for t, u in all_events}
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            results.append(result)
            if done % 50 == 0:
                print(f"    {done}/{len(all_events)} scrapeados...")

    print(f"    Scraping completo: {len(results)} resultados")

    # 4. Process and upsert
    print(f"\n[4] Procesando e insertando en BD...")
    inserted = 0
    skipped_past = 0
    skipped_no_date = 0
    errors = 0
    unknown_venues: set = set()

    for r in results:
        if "error" in r:
            errors += 1
            continue

        # Parse date
        fecha_str = parse_date_es(r.get("date_str") or "") if r.get("date_str") else None
        if not fecha_str:
            skipped_no_date += 1
            continue

        # Skip past events
        if fecha_str < TODAY:
            skipped_past += 1
            continue

        # Parse time
        hora_str = parse_time_es(r.get("time_str") or "")
        fecha_inicio = f"{fecha_str}T{hora_str}-05:00"

        # Venue
        venue = r.get("venue")
        lugar = find_lugar(venue or "", venue_map, hub)
        if not lugar:
            errors += 1
            continue
        if venue and not find_lugar(venue, venue_map, None):
            unknown_venues.add(venue)

        # Slug: reproducible, idempotent
        title = r.get("title") or r.get("url", "").split("/")[-2]
        title_slug = slugify(title)
        slug = f"biblio-mde-{title_slug}-{fecha_str.replace('-', '')}"[:120]

        row = {
            "id": str(uuid.uuid4()),
            "slug": slug,
            "titulo": title[:255],
            "espacio_id": lugar["id"],
            "fecha_inicio": fecha_inicio,
            "categoria_principal": "biblioteca",
            "fuente": "web",
            "fuente_url": r.get("url", ""),
            "municipio": lugar.get("municipio") or "medellin",
            "barrio": lugar.get("barrio") or "",
            "es_gratuito": True,
            "descripcion": (r.get("description") or "")[:1000],
        }

        if not args.dry_run:
            try:
                supabase.table("eventos").upsert(row, on_conflict="slug").execute()
                inserted += 1
            except Exception as e:
                errors += 1
        else:
            # Dry run: just print
            inserted += 1
            if inserted <= 5:
                print(f"    DRY: {fecha_str} {hora_str} | {lugar['nombre'][:40]} | {title[:50]}")

    # 5. Summary
    print(f"\n{'='*60}")
    print(f"RESUMEN")
    print(f"  Insertados/actualizados : {inserted}")
    print(f"  Saltados (pasados)      : {skipped_past}")
    print(f"  Saltados (sin fecha)    : {skipped_no_date}")
    print(f"  Errores HTTP/DB         : {errors}")
    if unknown_venues:
        print(f"  Venues sin mapeo ({len(unknown_venues)}) → usaron hub:")
        for v in sorted(unknown_venues):
            print(f"    - {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
