"""
Probe del sitio web de Red de Bibliotecas Públicas de Medellín.
Busca APIs JSON, WordPress REST, iCal, o cualquier fuente estructurada.
Código puro - sin AI.
"""
import sys, re, json, requests
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

# 1. Homepage
print("=== 1. Homepage ===")
r = requests.get(BASE, headers=H, timeout=15)
print(f"Status: {r.status_code} | Size: {len(r.text)}")

# Detect CMS
for kw in ["wp-content", "wp-json", "drupal", "joomla", "strapi", "ghost", "nextjs", "__NEXT_DATA__"]:
    if kw in r.text.lower():
        print(f"  CMS hint: {kw}")

# 2. WordPress REST API
print("\n=== 2. WordPress REST API ===")
wp_endpoints = [
    f"{BASE}/wp-json/wp/v2/posts?per_page=5",
    f"{BASE}/wp-json/tribe/events/v1/events?per_page=5",
    f"{BASE}/wp-json/wp/v2/eventos?per_page=5",
    f"{BASE}/?rest_route=/wp/v2/posts&per_page=5",
    f"{BASE}/agenda/?rest_route=/wp/v2/posts&per_page=5",
]
for url in wp_endpoints:
    try:
        r2 = requests.get(url, headers=H, timeout=10)
        ct = r2.headers.get("content-type", "")
        print(f"  {r2.status_code} | {ct[:30]} | {url[len(BASE):]}")
        if r2.status_code == 200 and "json" in ct:
            data = r2.json()
            if isinstance(data, list) and data:
                print(f"    *** JSON array: {len(data)} items ***")
                first = data[0]
                print(f"    Keys: {list(first.keys())[:8]}")
                print(f"    Title: {first.get('title', {}).get('rendered', first.get('title', ''))[:80]}")
            elif isinstance(data, dict) and data.get("events"):
                print(f"    *** Events dict: {len(data['events'])} events ***")
    except Exception as e:
        print(f"  ERR: {url[len(BASE):]} -> {e}")

# 3. Agenda page
print("\n=== 3. Agenda page ===")
for path in ["/agenda/", "/actividades/", "/programacion/", "/eventos/"]:
    try:
        r3 = requests.get(BASE + path, headers=H, timeout=10)
        ct = r3.headers.get("content-type", "")
        print(f"  {r3.status_code} | {ct[:30]} | {path}")
        if r3.status_code == 200:
            # Check for JSON data in HTML
            if "__NEXT_DATA__" in r3.text:
                print("    Found __NEXT_DATA__")
            if "wp-json" in r3.text:
                urls = re.findall(r'wp-json[^\s"\'<>]+', r3.text)
                for u in set(urls[:5]):
                    print(f"    WP-JSON ref: {u}")
    except Exception as e:
        print(f"  ERR {path}: {e}")

# 4. Sitemap
print("\n=== 4. Sitemap ===")
for path in ["/sitemap.xml", "/sitemap_index.xml", "/robots.txt"]:
    r4 = requests.get(BASE + path, headers=H, timeout=10)
    ct = r4.headers.get("content-type", "")
    print(f"  {r4.status_code} | {ct[:30]} | {path}")
    if r4.status_code == 200 and len(r4.text) < 5000:
        print(f"  Content: {r4.text[:400]}")

# 5. Try JSON feeds directly
print("\n=== 5. Feed / RSS ===")
for path in ["/feed/", "/feed/json", "/agenda/feed/", "/?feed=rss2", "/actividades/feed/"]:
    r5 = requests.get(BASE + path, headers=H, timeout=10)
    ct = r5.headers.get("content-type", "")
    print(f"  {r5.status_code} | {ct[:30]} | {path}")
