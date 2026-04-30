"""Probe Issuu to find PDF download URL for EPM cultural brochures."""
import requests
import re
import json

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}
USER = "bibliotecaepm1"
DOC = "programacion_formativa_mayo_-_bepm"

url = f"https://issuu.com/{USER}/docs/{DOC}"
print(f"Fetching: {url}")
r = requests.get(url, headers=HEADERS, timeout=20)
html = r.text

# Look for PDF/asset URLs and document IDs in the page source
patterns = [
    r'"pdfUrl"\s*:\s*"([^"]+)"',
    r'"downloadUrl"\s*:\s*"([^"]+)"',
    r'"document_name"\s*:\s*"([^"]+)"',
    r'"revisionId"\s*:\s*"([^"]+)"',
    r'"documentId"\s*:\s*"([^"]+)"',
    r'"configUrl"\s*:\s*"([^"]+)"',
    r'"articleDocumentContent"\s*:\s*"([^"]+)"',
]
for pat in patterns:
    m = re.search(pat, html)
    if m:
        print(f"FOUND {pat[:35]}: {m.group(1)[:120]}")
    else:
        print(f"NOT FOUND: {pat[:40]}")

# Try alternate: Issuu content API (no auth)
# https://issuu.com/oembed?url=...
oembed_url = f"https://issuu.com/oembed?url=https://issuu.com/{USER}/docs/{DOC}&format=json"
print(f"\n--- oEmbed ---")
r2 = requests.get(oembed_url, headers=HEADERS, timeout=15)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    d = r2.json()
    for k, v in d.items():
        print(f"  {k}: {str(v)[:120]}")

# Check for JSON blobs in script tags
print("\n--- Script data keys ---")
script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for block in script_blocks:
    if '"documentId"' in block or '"pdfUrl"' in block or '"revisionId"' in block:
        # Try to extract JSON
        m = re.search(r'(\{.*\})', block[:5000], re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                print(json.dumps(data, indent=2)[:500])
            except Exception:
                print(block[:300])
        break

# Check if there's a Next.js __NEXT_DATA__ 
if "__NEXT_DATA__" in html:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        print("\n--- __NEXT_DATA__ ---")
        try:
            data = json.loads(m.group(1))
            # Navigate to find document data
            props = data.get("props", {}).get("pageProps", {})
            print(json.dumps(props, indent=2)[:2000])
        except Exception as e:
            print(f"Parse error: {e}")
            print(m.group(1)[:500])
