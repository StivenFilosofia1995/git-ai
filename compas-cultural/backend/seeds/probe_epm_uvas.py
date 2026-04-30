"""
Probe: Fundación EPM agenda y UVAs. Busca eventos estructurados sin AI.
Código puro - sin AI.
"""
import sys, re, json, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
EPM_BASE = "https://www.fundacionepm.org.co"

# 1. Fundación EPM agenda
print("=== 1. Fundación EPM - agenda ===")
PATHS = [
    "/micrositios/fundacion-epm/agenda/",
    "/agenda/",
    "/eventos/",
    "/programacion/",
    "/micrositios/fundacion-epm/",
]
for path in PATHS:
    r = requests.get(EPM_BASE + path, headers=H, timeout=15)
    ct = r.headers.get("content-type", "")
    print(f"  {r.status_code} | {ct[:25]} | {path}")
    if r.status_code == 200 and "html" in ct:
        # Check for WP
        for kw in ["wp-content", "wp-json", "__NEXT_DATA__", "api/", "mec-events"]:
            if kw in r.text.lower():
                print(f"    Found: {kw}")

# 2. Biblioteca EPM
print("\n=== 2. Biblioteca EPM ===")
BEPM = "https://www.bibliotecaepm.com"
for path in ["/", "/agenda/", "/eventos/", "/programacion/", "/actividades/"]:
    r = requests.get(BEPM + path, headers=H, timeout=15)
    ct = r.headers.get("content-type", "")
    print(f"  {r.status_code} | {ct[:25]} | {path}")
    if r.status_code == 200 and "html" in ct:
        for kw in ["wp-content", "wp-json", "__NEXT_DATA__", "mec-events"]:
            if kw in r.text.lower():
                print(f"    Found: {kw}")
        # Check feeds
        has_rss = "rss" in r.text.lower() or "feed" in r.text.lower()
        print(f"    RSS/Feed hint: {has_rss}")

# 3. Biblioteca EPM WP endpoints
print("\n=== 3. Biblioteca EPM - WP REST ===")
for path in [
    "/wp-json/wp/v2/types",
    "/wp-json/wp/v2/posts?per_page=5&_fields=id,date,title,link",
    "/feed/",
]:
    r = requests.get(BEPM + path, headers=H, timeout=10)
    ct = r.headers.get("content-type", "")
    print(f"  {r.status_code} | {ct[:35]} | {path}")
    if r.status_code == 200 and "json" in ct:
        try:
            d = r.json()
            if isinstance(d, list) and d:
                print(f"    {len(d)} items | {d[0].get('title',{}).get('rendered','')[:60]}")
            elif isinstance(d, dict):
                print(f"    Keys: {list(d.keys())[:8]}")
        except:
            pass

# 4. UVAs - check INDER and EPM UVA pages
print("\n=== 4. UVAs ===")
UVA_URLS = [
    "https://www.inder.gov.co/programacion/",
    "https://www.inder.gov.co/eventos/",
    "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
    "https://uva.epm.com.co/",
    "https://www.epm.com.co/site/clientes_usuarios/programas-sociales/uva.aspx",
]
for url in UVA_URLS:
    try:
        r = requests.get(url, headers=H, timeout=12)
        ct = r.headers.get("content-type", "")
        print(f"  {r.status_code} | {ct[:25]} | {url[:60]}")
        if r.status_code == 200 and "html" in ct:
            for kw in ["wp-content", "wp-json", "__NEXT_DATA__", "mec-events", "json"]:
                if kw in r.text.lower():
                    print(f"    Found: {kw}")
    except Exception as e:
        print(f"  ERR | {url[:60]} | {e}")

# 5. Parque de los Deseos
print("\n=== 5. Parque de los Deseos ===")
DESEOS = "https://www.fundacionepm.org.co/micrositios/parque-de-los-deseos/"
r = requests.get(DESEOS, headers=H, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")
for kw in ["wp-json", "__NEXT_DATA__", "mec-events", "evento"]:
    if kw in r.text.lower():
        print(f"  Found: {kw}")
# Check for event data
events = soup.find_all(class_=re.compile(r'event|actividad|programa', re.I))
print(f"  Event elements: {len(events)}")
for e in events[:3]:
    print(f"  {e.get_text(' ', strip=True)[:100]}")
