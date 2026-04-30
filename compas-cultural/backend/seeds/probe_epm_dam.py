"""Busca PDFs de programacion en el DAM de AEM de EPM y los descarga."""
import requests
import re
import io

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}
BASE = "https://www.grupo-epm.com"

# 1. Query AEM DAM for PDF assets under programacion/fundacion paths
print("=== Searching AEM DAM for PDFs ===")
r = requests.get(
    f"{BASE}/bin/querybuilder.json",
    params={
        "path": "/content/dam/Grupo-Epm/fundacion-epm",
        "type": "dam:Asset",
        "nodename": "*.pdf",
        "p.limit": "50",
        "p.hits": "full",
        "p.properties": "jcr:path jcr:created",
        "orderby": "jcr:content/jcr:lastModified",
        "orderby.sort": "desc",
    },
    headers=HEADERS, timeout=20
)
print(f"Status: {r.status_code}")
data = r.json()
print(f"Total PDFs found: {data.get('total', 0)}")
print()
for hit in data.get("hits", [])[:20]:
    path = hit.get("jcr:path", "")
    created = hit.get("jcr:created", "")
    print(f"  {created[:10]} | {path}")

# 2. Check if PDFs are accessible via direct URL
print("\n=== Testing direct PDF access ===")
for hit in data.get("hits", [])[:5]:
    path = hit.get("jcr:path", "")
    url = f"{BASE}{path}"
    rp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
    ct = rp.headers.get("content-type", "")
    print(f"  {rp.status_code} | {ct[:30]} | {len(rp.content)} bytes | {path[-60:]}")

# 3. Specifically look for programacion PDFs
print("\n=== Searching for programacion PDFs ===")
for search_path in [
    "/content/dam/Grupo-Epm/fundacion-epm/programaci%C3%B3n",
    "/content/dam/Grupo-Epm/fundacion-epm/programacion",
    "/content/dam/Grupo-Epm/biblioteca-epm",
]:
    r2 = requests.get(
        f"{BASE}/bin/querybuilder.json",
        params={
            "path": search_path,
            "type": "dam:Asset",
            "p.limit": "20",
            "p.hits": "full",
            "p.properties": "jcr:path jcr:content/jcr:lastModified jcr:content/jcr:mimeType",
            "orderby": "jcr:content/jcr:lastModified",
            "orderby.sort": "desc",
        },
        headers=HEADERS, timeout=20
    )
    if r2.status_code == 200:
        d2 = r2.json()
        assets = d2.get("hits", [])
        print(f"\n  {search_path}: {d2.get('total', 0)} assets")
        for a in assets[:10]:
            p = a.get("jcr:path", "")
            mime = a.get("jcr:content/jcr:mimeType", "?")
            print(f"    [{mime}] {p[-80:]}")
