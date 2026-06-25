"""Probe Issuu embed HTML para encontrar APIs no autenticadas."""
import sys
import re
import requests

sys.stdout.reconfigure(encoding="utf-8")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Check the Issuu public page (not embed) - look for Next.js data
DOC_NAME = "programacion_formativa_mayo_-_bepm"
USER = "bibliotecaepm1"

print("=== 1. Issuu public page ===")
r = requests.get(
    f"https://issuu.com/{USER}/docs/{DOC_NAME}",
    headers=HEADERS, timeout=15
)
print(f"Status: {r.status_code} | Size: {len(r.text)}")
# Look for __NEXT_DATA__ or document config
for kw in ["__NEXT_DATA__", "__ISSUU_CONFIG__", "docName", "pageCount", "reader3"]:
    idx = r.text.find(kw)
    if idx > 0:
        print(f"  Found '{kw}' at {idx}: ...{r.text[idx:idx+200]}...")

# 2. Check embed HTML
print("\n=== 2. Issuu embed HTML ===")
embed_url = f"https://e.issuu.com/embed.html?u={USER}&d={DOC_NAME}"
r2 = requests.get(embed_url, headers=HEADERS, timeout=15)
print(f"Status: {r2.status_code} | Size: {len(r2.text)}")
# Find script src URLs
scripts = re.findall(r'src=["\']([^"\']+)["\']', r2.text)
for s in scripts[:20]:
    print(f"  script: {s}")
# Find any config
for kw in ["apiKey", "apiUrl", "docName", "config", "isu.pub", "reader"]:
    idx = r2.text.find(kw)
    if idx > 0:
        print(f"  Found '{kw}': ...{r2.text[max(0,idx-30):idx+150]}...")

# 3. Issuu API v2 - public document info
print("\n=== 3. Issuu API endpoints ===")
api_urls = [
    f"https://issuu.com/api/2_0/document/{USER}/{DOC_NAME}",
    f"https://api.issuu.com/v2/documents/{DOC_NAME}?username={USER}",
    f"https://issuu.com/call/frontend/reader/issuu/document/{USER}/{DOC_NAME}",
    f"https://issuu.com/{USER}/docs/{DOC_NAME}?format=json",
]
for url in api_urls:
    try:
        r3 = requests.get(url, headers=HEADERS, timeout=10)
        ct = r3.headers.get("content-type", "")
        print(f"  {r3.status_code} | {ct[:30]} | {url[-60:]}")
        if r3.status_code == 200 and ("json" in ct or r3.text.startswith("{")):
            print(f"    Content: {r3.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e} | {url[-60:]}")
