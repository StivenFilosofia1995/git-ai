"""
Extrae correctamente la metadata y prueba acceso a paginas del PDF.
El JSON en el HTML tiene las comillas escapadas: \"pageCount\":19
"""
import sys
import re
import json
import requests

sys.stdout.reconfigure(encoding="utf-8")

USER = "bibliotecaepm1"
DOC_NAME = "programacion_formativa_mayo_-_bepm"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

r = requests.get(
    f"https://issuu.com/{USER}/docs/{DOC_NAME}",
    headers=HEADERS, timeout=20
)
html = r.text

# The JSON in HTML uses escaped quotes: \"pageCount\":19
page_count_match = re.search(r'\\"pageCount\\":\s*(\d+)', html)
pub_id_match = re.search(r'\\"publicationId\\":\s*\\"([a-f0-9\-]+)\\"', html)
rev_id_match = re.search(r'\\"revisionId\\":\s*\\"(\d+)\\"', html)

page_count = int(page_count_match.group(1)) if page_count_match else None
pub_id = pub_id_match.group(1) if pub_id_match else None
rev_id = rev_id_match.group(1) if rev_id_match else None

print(f"pageCount={page_count}")
print(f"publicationId={pub_id}")
print(f"revisionId={rev_id}")

if not pub_id:
    # try without escaped quotes (some pages might not have backslash)
    pub_id_match = re.search(r'"publicationId"\s*:\s*"([a-f0-9\-]+)"', html)
    rev_id_match = re.search(r'"revisionId"\s*:\s*"(\d+)"', html)
    pub_id = pub_id_match.group(1) if pub_id_match else None
    rev_id = rev_id_match.group(1) if rev_id_match else None
    print(f"(no-escape) publicationId={pub_id}, revisionId={rev_id}")

# Hardcode from known values found in previous run
if not pub_id:
    pub_id = "f8f4321e0122ec91b6efa81bb49a1731"
    rev_id = "260423131949"
    page_count = 19
    print(f"Using hardcoded values: pub={pub_id} rev={rev_id}")

doc_rev = f"{rev_id}-{pub_id}"
print(f"\nDocument revision string: {doc_rev}")

# Test image access with Referer
print("\n=== Testing image.isu.pub with Referer ===")
image_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://issuu.com/",
    "Origin": "https://issuu.com",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}
for fmt in ["page_1_thumb_medium.jpg", "page_1.large.jpg", "page_1_large.jpg", "page_1.jpg"]:
    img_url = f"https://image.isu.pub/{doc_rev}/jpg/{fmt}"
    ri = requests.get(img_url, headers=image_headers, timeout=10)
    ct = ri.headers.get("content-type", "")
    print(f"  {ri.status_code} | {ct[:25]} | {len(ri.content)} bytes | {fmt}")
    if ri.status_code == 200 and "image" in ct:
        with open(f"test_page_img.jpg", "wb") as f:
            f.write(ri.content)
        print(f"    *** SAVED! ***")
        break

# Test embed API
print("\n=== Testing embed reader4 API ===")
embed_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://e.issuu.com/embed.html?u={USER}&d={DOC_NAME}",
    "Origin": "https://e.issuu.com",
}
embed_api_urls = [
    f"https://e.issuu.com/reader4/document/{USER}/{DOC_NAME}",
    f"https://e.issuu.com/reader4/config?u={USER}&d={DOC_NAME}",
    f"https://issuu.com/home/api/2_0/document/{USER}/{DOC_NAME}",
    f"https://issuu.com/home/api/2_0/document/{pub_id}",
    f"https://api.issuu.com/v1?action=issuu.documents.list&username={USER}&format=json",
    f"https://content.issuu.com/reader3/config?username={USER}&name={DOC_NAME}",
    f"https://content.issuu.com/v2/documents/{DOC_NAME}?username={USER}",
]
for eu in embed_api_urls:
    try:
        re2 = requests.get(eu, headers=embed_headers, timeout=10)
        ct2 = re2.headers.get("content-type", "")
        preview = re2.text[:100] if re2.status_code == 200 else ""
        print(f"  {re2.status_code} | {ct2[:25]} | {eu[-70:]}")
        if preview:
            print(f"    {preview}")
    except Exception as e:
        print(f"  ERROR | {eu[-70:]}")

# Reader3 with embed referer
print("\n=== Reader3 with embed Referer ===")
r3_url = f"https://reader3.isu.pub/{USER}/{DOC_NAME}/reader3.json"
rr3 = requests.get(r3_url, headers=embed_headers, timeout=10)
print(f"reader3.json: {rr3.status_code} | {rr3.headers.get('content-type','')[:30]}")
if rr3.status_code == 200:
    print(rr3.text[:300])
