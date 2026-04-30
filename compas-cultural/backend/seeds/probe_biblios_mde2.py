"""
Explora la WordPress REST API de bibliotecasmedellin.gov.co para encontrar eventos.
Código puro - sin AI.
"""
import sys, re, json, requests
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

# 1. Descubrir tipos de post custom
print("=== 1. Tipos de post disponibles ===")
r = requests.get(f"{BASE}/wp-json/wp/v2/types", headers=H, timeout=15)
if r.status_code == 200:
    types = r.json()
    for key, val in types.items():
        print(f"  {key}: {val.get('name')} | rest_base={val.get('rest_base')}")

# 2. Explorar posts recientes (son actividades/eventos)
print("\n=== 2. Posts recientes con campos completos ===")
r2 = requests.get(
    f"{BASE}/wp-json/wp/v2/posts",
    params={"per_page": 10, "_fields": "id,date,title,excerpt,content,link,categories,tags,acf,meta"},
    headers=H, timeout=15
)
posts = r2.json()
print(f"Posts: {len(posts)}")
for p in posts[:3]:
    print(f"\n  ID={p['id']} | Date={p['date'][:10]}")
    title = p.get('title', {}).get('rendered', '')
    print(f"  Title: {title[:100]}")
    excerpt = re.sub(r'<[^>]+>', '', p.get('excerpt', {}).get('rendered', ''))[:200]
    print(f"  Excerpt: {excerpt.strip()}")
    print(f"  ACF: {p.get('acf')}")
    print(f"  Meta: {str(p.get('meta'))[:200]}")

# 3. Taxonomías / categorías
print("\n=== 3. Categorías disponibles ===")
r3 = requests.get(f"{BASE}/wp-json/wp/v2/categories", params={"per_page": 50}, headers=H, timeout=15)
cats = r3.json()
for c in cats:
    print(f"  {c['id']} | {c['name']} | count={c.get('count',0)}")

# 4. Buscar por términos de agenda/actividad
print("\n=== 4. Búsqueda por texto ===")
for q in ["taller", "club lectura", "concierto", "mayo 2026"]:
    r4 = requests.get(
        f"{BASE}/wp-json/wp/v2/posts",
        params={"search": q, "per_page": 5, "_fields": "id,date,title,link"},
        headers=H, timeout=10
    )
    data = r4.json()
    if isinstance(data, list):
        print(f"  '{q}': {len(data)} resultados")
        for p in data[:2]:
            print(f"    {p['date'][:10]} | {p['title']['rendered'][:70]}")

# 5. Intentar ACF Forms o custom post type "actividad"
print("\n=== 5. Custom post types rest ===")
for cpt in ["actividad", "actividades", "evento", "programacion", "taller", "agenda"]:
    r5 = requests.get(
        f"{BASE}/wp-json/wp/v2/{cpt}",
        params={"per_page": 3, "_fields": "id,date,title,link"},
        headers=H, timeout=8
    )
    if r5.status_code == 200:
        data = r5.json()
        print(f"  ✓ /{cpt}: {len(data) if isinstance(data, list) else 'dict'} items")
        if isinstance(data, list) and data:
            print(f"    Sample: {data[0].get('title', {}).get('rendered', '')[:60]}")
    else:
        print(f"  ✗ /{cpt}: {r5.status_code}")

# 6. Ver una actividad real desde /actividades/
print("\n=== 6. Parse actividades page HTML ===")
r6 = requests.get(f"{BASE}/actividades/", headers=H, timeout=15)
html = r6.text
# Look for event data in HTML
events_in_html = re.findall(r'<article[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
print(f"Articles found: {len(events_in_html)}")
for art in events_in_html[:3]:
    title_m = re.search(r'<h\d[^>]*>(.*?)</h\d>', art, re.DOTALL)
    date_m = re.search(r'class="[^"]*date[^"]*"[^>]*>(.*?)</', art, re.DOTALL)
    link_m = re.search(r'href="([^"]+)"', art)
    t = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
    d = re.sub(r'<[^>]+>', '', date_m.group(1)).strip() if date_m else ''
    l = link_m.group(1) if link_m else ''
    print(f"  {d} | {t[:60]} | {l[:60]}")
