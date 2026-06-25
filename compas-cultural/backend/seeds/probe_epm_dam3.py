"""
Descarga y parsea PDFs de programacion de Biblioteca EPM desde AEM DAM.
Encuentra los PDFs de agenda/programacion actuales.
"""
import sys
import io
import re
import requests
import pdfplumber

sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}
BASE = "https://www.grupo-epm.com"

# Buscar TODOS los PDFs en biblioteca-epm y programacion folders
print("=== Buscando PDFs de programacion y agenda ===")

# Try several DAM paths
paths_to_search = [
    "/content/dam/Grupo-Epm/biblioteca-epm",
    "/content/dam/Grupo-Epm/fundacion-epm/programaci%C3%B3n",
    "/content/dam/Grupo-Epm/fundacion-epm/programacion",
    "/content/dam/Grupo-Epm/parque-deseos",
    "/content/dam/Grupo-Epm/parque-de-los-deseos",
    "/content/dam/Grupo-Epm/uva",
    "/content/dam/Grupo-Epm/museo-agua",
    "/content/dam/Grupo-Epm/museo-del-agua",
]

pdf_paths = []
for search_path in paths_to_search:
    r = requests.get(
        f"{BASE}/bin/querybuilder.json",
        params={
            "path": search_path,
            "type": "dam:Asset",
            "nodename": "*.pdf",
            "p.limit": "50",
            "p.hits": "full",
            "p.properties": "jcr:path",
        },
        headers=HEADERS, timeout=20
    )
    if r.status_code == 200:
        d = r.json()
        total = d.get("total", 0)
        if total > 0:
            print(f"\n  {search_path}: {total} PDFs")
            for h in d.get("hits", [])[:20]:
                p = h.get("jcr:path", "")
                print(f"    {p}")
                pdf_paths.append(p)

# Download AGENDA 1.pdf
print("\n\n=== Downloading and parsing AGENDA 1.pdf ===")
agenda_url = f"{BASE}/content/dam/Grupo-Epm/biblioteca-epm/documentos/AGENDA 1.pdf"
rp = requests.get(agenda_url, headers=HEADERS, timeout=20, allow_redirects=True)
print(f"Status: {rp.status_code} | Size: {len(rp.content)} bytes")

if rp.status_code == 200 and b"%PDF" in rp.content[:10]:
    with pdfplumber.open(io.BytesIO(rp.content)) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages[:5], 1):
            text = page.extract_text()
            print(f"\n--- Page {i} ---")
            if text:
                print(text[:800])
            else:
                print("  (no text)")
else:
    print("Not a PDF or not accessible")
    print(rp.content[:200])
