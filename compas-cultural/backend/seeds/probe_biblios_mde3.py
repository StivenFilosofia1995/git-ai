"""
Explora mec-events y cpt-eventos-mes en bibliotecasmedellin.gov.co.
Código puro - sin AI.
"""
import sys, re, json, requests
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

# 1. Modern Events Calendar (mec-events)
print("=== 1. mec-events REST ===")
for endpoint in [
    "/wp-json/wp/v2/mec-events",
    "/wp-json/mec/v1/events",
    "/wp-json/mec/v1/events/",
]:
    r = requests.get(BASE + endpoint, params={"per_page": 3}, headers=H, timeout=15)
    ct = r.headers.get("content-type", "")
    print(f"  {r.status_code} | {ct[:30]} | {endpoint}")
    if r.status_code == 200 and "json" in ct:
        data = r.json()
        if isinstance(data, list) and data:
            print(f"    {len(data)} items | Keys: {list(data[0].keys())[:12]}")
            first = data[0]
            print(f"    ID={first.get('id')} | date={first.get('date')} | title={str(first.get('title'))[:60]}")
            print(f"    meta keys: {list((first.get('meta') or {}).keys())[:10]}")
        elif isinstance(data, dict):
            print(f"    dict keys: {list(data.keys())[:10]}")

# 2. mec-events con campos extendidos
print("\n=== 2. mec-events campos completos (1 evento) ===")
r2 = requests.get(
    f"{BASE}/wp-json/wp/v2/mec-events",
    params={"per_page": 1, "_fields": "id,date,title,content,meta,mec_data,link,categories,tags,acf"},
    headers=H, timeout=15
)
if r2.status_code == 200:
    data = r2.json()
    if data:
        e = data[0]
        print(f"  Keys disponibles: {list(e.keys())}")
        print(f"  date: {e.get('date')}")
        print(f"  title: {e.get('title')}")
        print(f"  meta: {json.dumps(e.get('meta'), ensure_ascii=False)[:500]}")
        print(f"  mec_data: {str(e.get('mec_data'))[:300]}")
        print(f"  link: {e.get('link')}")

# 3. cpt-eventos-mes
print("\n=== 3. cpt-eventos-mes ===")
for cpt in ["cpt-eventos-mes", "cpt_eventos_mes"]:
    r3 = requests.get(
        f"{BASE}/wp-json/wp/v2/{cpt}",
        params={"per_page": 3, "_fields": "id,date,title,link,meta,acf"},
        headers=H, timeout=10
    )
    if r3.status_code == 200:
        data = r3.json()
        print(f"  ✓ {cpt}: {len(data) if isinstance(data, list) else 'dict'}")
        if isinstance(data, list) and data:
            e = data[0]
            print(f"    Keys: {list(e.keys())}")
            print(f"    title: {e.get('title')}")
            print(f"    meta: {str(e.get('meta'))[:300]}")

# 4. Scrape actividades con paginación para ver estructura
print("\n=== 4. Actividades HTML - estructura de artículo completo ===")
r4 = requests.get(f"{BASE}/actividades/", headers=H, timeout=15)
html = r4.text

# Extract all articles
articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
print(f"Articles: {len(articles)}")
for art in articles[:2]:
    clean = re.sub(r'\s+', ' ', art)
    # Fecha
    date_m = re.search(r'(\d{2}/\d{2}/\d{4})', clean)
    # Hora
    hora_m = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)', clean)
    # Sede
    sede_m = re.search(r'(?:sede|lugar|biblioteca)[:\s]+([^<\n]+)', clean, re.IGNORECASE)
    # Título
    title_m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', clean, re.DOTALL)
    # Link
    link_m = re.search(r'href="(https://bibliotecasmedellin[^"]+)"', clean)
    # Categorías
    cats_m = re.findall(r'rel="category tag"[^>]*>([^<]+)<', clean)
    
    title_t = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else 'N/A'
    print(f"\n  Título: {title_t[:70]}")
    print(f"  Fecha: {date_m.group(1) if date_m else 'N/A'}")
    print(f"  Hora: {hora_m.group(1) if hora_m else 'N/A'}")
    print(f"  Cats: {cats_m}")
    print(f"  Link: {link_m.group(1)[:70] if link_m else 'N/A'}")
    print(f"  Raw (first 400): {clean[:400]}")

# 5. Ver una actividad individual
print("\n=== 5. Evento individual completo ===")
r5 = requests.get(f"{BASE}/actividades/universo-gamer/", headers=H, timeout=15)
html5 = r5.text

# Look for dates/times in meta
date_m = re.findall(r'(\d{2}/\d{2}/\d{4})', html5)
time_m = re.findall(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', html5)
sede_m = re.findall(r'(?:sede|lugar|biblioteca)[:\s]*<[^>]*>?([^<\n]+)', html5[:5000], re.IGNORECASE)
print(f"  Fechas encontradas: {date_m[:5]}")
print(f"  Horas encontradas: {time_m[:5]}")
print(f"  Sedes: {sede_m[:3]}")

# Extract meta tags with event info
og_tags = re.findall(r'<meta[^>]+(?:property|name)="[^"]*(?:event|date|time|place)[^"]*"[^>]*>', html5)
for t in og_tags[:10]:
    print(f"  Meta: {t[:120]}")

# event-details / mec-single-event divs
for cls in ["mec-single-event", "event-detail", "event-info", "event-meta", "mec-event"]:
    matches = re.findall(rf'class="[^"]*{cls}[^"]*"[^>]*>(.*?)</(?:div|section)', html5, re.DOTALL)
    if matches:
        clean_m = re.sub(r'<[^>]+>', '', matches[0]).strip()[:200]
        print(f"  .{cls}: {clean_m}")
