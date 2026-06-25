"""Busca y descarga PDFs de programacion cultural de EPM desde su AEM DAM."""
import sys
import requests
import re
import io

# Fix Windows cp1252 encoding
sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}
BASE = "https://www.grupo-epm.com"

# 1. Search for programacion/biblioteca PDFs in DAM
print("=== Searching AEM DAM for programacion PDFs ===")
r = requests.get(
    f"{BASE}/bin/querybuilder.json",
    params={
        "path": "/content/dam/Grupo-Epm/fundacion-epm",
        "type": "dam:Asset",
        "nodename": "*.pdf",
        "fulltext": "programacion programación",
        "p.limit": "50",
        "p.hits": "full",
        "p.properties": "jcr:path jcr:created",
        "orderby": "@jcr:created",
        "orderby.sort": "desc",
    },
    headers=HEADERS, timeout=20
)
data = r.json()
print(f"PDFs matching 'programacion': {data.get('total', 0)}")
for hit in data.get("hits", [])[:20]:
    path = hit.get("jcr:path", "")
    print(f"  {path}")

# 2. Try direct download of one PDF
print("\n=== Testing direct PDF access ===")
for hit in data.get("hits", [])[:3]:
    path = hit.get("jcr:path", "")
    url = f"{BASE}{path}"
    try:
        rp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        ct = rp.headers.get("content-type", "")
        print(f"  {rp.status_code} | {ct[:40]} | {len(rp.content)} bytes")
        print(f"    URL: {url[-80:]}")
        if "pdf" in ct.lower() and rp.status_code == 200:
            print("  *** PDF accessible! ***")
            # Save first one to test
            with open("test_epm.pdf", "wb") as f:
                f.write(rp.content)
            print("  Saved to test_epm.pdf")
    except Exception as e:
        print(f"  ERROR: {e}")

# 3. Also check biblioteca-epm folder
print("\n=== Biblioteca EPM programacion PDFs ===")
r3 = requests.get(
    f"{BASE}/bin/querybuilder.json",
    params={
        "path": "/content/dam/Grupo-Epm/biblioteca-epm",
        "type": "dam:Asset",
        "nodename": "*.pdf",
        "p.limit": "30",
        "p.hits": "full",
        "p.properties": "jcr:path jcr:created",
        "orderby": "@jcr:created",
        "orderby.sort": "desc",
    },
    headers=HEADERS, timeout=20
)
d3 = r3.json()
print(f"Biblioteca EPM PDFs: {d3.get('total', 0)}")
for hit in d3.get("hits", [])[:15]:
    path = hit.get("jcr:path", "")
    print(f"  {path}")
