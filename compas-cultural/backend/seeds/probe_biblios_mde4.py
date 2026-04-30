"""
Explora cpt_eventos_mes y mec/v1/events en profundidad.
Código puro - sin AI.
"""
import sys, re, json, requests
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

# 1. cpt_eventos_mes paginado
print("=== 1. cpt_eventos_mes - todos ===")
r = requests.get(
    f"{BASE}/wp-json/wp/v2/cpt_eventos_mes",
    params={"per_page": 100, "_fields": "id,date,title,link,categories,tags,meta,content,excerpt"},
    headers=H, timeout=20
)
events_cpt = r.json() if r.status_code == 200 else []
print(f"Total: {len(events_cpt)}")
for e in events_cpt:
    cats = e.get('categories', [])
    print(f"  {e.get('date','')[:10]} | {e.get('title',{}).get('rendered','')[:60]} | cats={cats}")

# 2. MEC v1 events - formato propio
print("\n=== 2. mec/v1/events ===")
r2 = requests.get(f"{BASE}/wp-json/mec/v1/events", headers=H, timeout=15)
print(f"Status: {r2.status_code}")
print(f"Content-Type: {r2.headers.get('content-type','')[:50]}")
try:
    data2 = r2.json()
    print(f"Type: {type(data2)}")
    if isinstance(data2, list):
        print(f"Count: {len(data2)}")
        if data2:
            print(f"First keys: {list(data2[0].keys())[:15]}")
            e0 = data2[0]
            print(f"Sample: ID={e0.get('id')} | start={e0.get('start')} | title={str(e0.get('title'))[:60]}")
    elif isinstance(data2, dict):
        print(f"Dict keys: {list(data2.keys())[:10]}")
        print(json.dumps(data2, ensure_ascii=False)[:500])
except:
    print(f"Raw: {r2.text[:300]}")

# 3. mec-events con meta campos expandidos
print("\n=== 3. mec-events con meta ===")
r3 = requests.get(
    f"{BASE}/wp-json/wp/v2/mec-events",
    params={"per_page": 5},
    headers=H, timeout=15
)
if r3.status_code == 200:
    data3 = r3.json()
    print(f"Count: {len(data3)}")
    if data3:
        e = data3[0]
        print(f"All keys: {list(e.keys())}")
        for k, v in e.items():
            if k not in ['content', 'guid', '_links']:
                print(f"  {k}: {str(v)[:100]}")

# 4. Categorías de taxonomía custom
print("\n=== 4. Taxonomías custom de mec-events ===")
for tax in ["mec_cat", "mec_speaker", "mec_label", "mec_tag", "mec_location", "sede", "biblioteca", "lugar"]:
    r4 = requests.get(f"{BASE}/wp-json/wp/v2/{tax}", params={"per_page": 20}, headers=H, timeout=8)
    if r4.status_code == 200:
        data4 = r4.json()
        print(f"  ✓ {tax}: {len(data4) if isinstance(data4, list) else 'dict'}")
        if isinstance(data4, list) and data4:
            for item in data4[:5]:
                print(f"    id={item.get('id')} | name={item.get('name')} | slug={item.get('slug')}")
    else:
        print(f"  ✗ {tax}: {r4.status_code}")

# 5. Explorar evento individual para extraer fecha/sede real
print("\n=== 5. HTML evento individual - Universo Gamer ===")
r5 = requests.get(f"{BASE}/actividades/universo-gamer/", headers=H, timeout=15)
html = r5.text

# Buscar datos de MEC embebidos en JS
mec_data = re.findall(r'mec[_-]?(?:event|data)[^{]*({[^;]+})', html, re.IGNORECASE)
for d in mec_data[:3]:
    print(f"  MEC JS: {d[:300]}")

# JSON-LD
jsonld = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
for j in jsonld:
    try:
        obj = json.loads(j.strip())
        print(f"  JSON-LD: {json.dumps(obj, ensure_ascii=False)[:400]}")
    except:
        print(f"  JSON-LD raw: {j[:200]}")

# Buscar meta og
og = re.findall(r'<meta property="og:[^"]*"[^>]*content="[^"]*"[^>]*/>', html)
for m in og[:10]:
    print(f"  OG: {m[:120]}")

# Buscar patrones de fecha en contenido
date_patterns = re.findall(r'(?:fecha|date|cuando|cuándo)[:\s]*([^\n<]{5,50})', html, re.IGNORECASE)
for p in date_patterns[:5]:
    clean = re.sub(r'<[^>]+>', '', p).strip()
    if clean:
        print(f"  Fecha patrón: {clean[:80]}")

# MEC single event spans
spans = re.findall(r'<(?:span|div|p)[^>]*class="[^"]*mec[^"]*"[^>]*>(.*?)</(?:span|div|p)>', html, re.DOTALL)
for s in spans[:10]:
    clean = re.sub(r'<[^>]+>', '', s).strip()
    if clean and len(clean) > 2:
        print(f"  MEC span: {clean[:80]}")
