"""
Extrae datos completos del documento Issuu y prueba acceso a páginas.
Encontrado: pageCount=19, publicationId, revisionId en HTML de la página pública.
"""
import sys
import re
import json
import requests
import io

sys.stdout.reconfigure(encoding="utf-8")

USER = "bibliotecaepm1"
DOC_NAME = "programacion_formativa_mayo_-_bepm"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-CO,es;q=0.9",
}

# 1. Get the full JSON context from the Issuu public page
print("=== 1. Extracting document metadata from Issuu page ===")
r = requests.get(
    f"https://issuu.com/{USER}/docs/{DOC_NAME}",
    headers=HEADERS, timeout=20
)
html = r.text
# Find the JSON blob containing pageCount
idx = html.find("pageCount")
context = html[max(0, idx - 200) : idx + 500]
print("Context around pageCount:")
print(context)

# Try to extract JSON from script tags
print("\n\n=== 2. Extracting full document JSON ===")
# Look for JSON.stringify or window.__something or script type application/json
# Find all script[type=application/json] content
json_scripts = re.findall(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
for i, js in enumerate(json_scripts[:5]):
    print(f"JSON script {i}: {js[:300]}")
    print("---")

# Try to extract the specific keys
page_count_match = re.search(r'"pageCount"\s*:\s*(\d+)', html)
pub_id_match = re.search(r'"publicationId"\s*:\s*"([a-f0-9]+)"', html)
rev_id_match = re.search(r'"revisionId"\s*:\s*"(\d+)"', html)

page_count = int(page_count_match.group(1)) if page_count_match else None
pub_id = pub_id_match.group(1) if pub_id_match else None
rev_id = rev_id_match.group(1) if rev_id_match else None

print(f"\nExtracted: pageCount={page_count}, publicationId={pub_id}, revisionId={rev_id}")

if pub_id and rev_id:
    doc_rev = f"{rev_id}-{pub_id}"
    print(f"Document revision: {doc_rev}")
    
    # 3. Try page images with different headers
    print("\n=== 3. Testing image access with Referer ===")
    image_headers = {
        **HEADERS,
        "Referer": f"https://issuu.com/{USER}/docs/{DOC_NAME}",
        "Origin": "https://issuu.com",
    }
    
    for fmt in ["page_1.large.jpg", "page_1_large.jpg", "page_1.jpg", "page_1_medium.jpg", "page_1_thumb_medium.jpg"]:
        img_url = f"https://image.isu.pub/{doc_rev}/jpg/{fmt}"
        ri = requests.get(img_url, headers=image_headers, timeout=10)
        ct = ri.headers.get("content-type", "")
        print(f"  {ri.status_code} | {ct[:25]} | {len(ri.content)} bytes | {fmt}")
        if ri.status_code == 200 and "image" in ct:
            with open(f"test_issuu_{fmt}", "wb") as f:
                f.write(ri.content)
            print(f"    *** SAVED: test_issuu_{fmt} ***")
    
    # 4. Try reader4 embed API
    print("\n=== 4. Embed API call ===")
    embed_api_urls = [
        f"https://e.issuu.com/reader4/reader/document/{USER}/{DOC_NAME}",
        f"https://e.issuu.com/api/document/{USER}/{DOC_NAME}",
        f"https://issuu.com/home/api/2_0/document/{USER}/{DOC_NAME}",
    ]
    embed_headers = {**HEADERS, "Referer": f"https://e.issuu.com/embed.html?u={USER}&d={DOC_NAME}"}
    for eu in embed_api_urls:
        try:
            re2 = requests.get(eu, headers=embed_headers, timeout=10)
            ct2 = re2.headers.get("content-type", "")
            print(f"  {re2.status_code} | {ct2[:30]} | {eu[-60:]}")
            if re2.status_code == 200:
                print(f"    Content: {re2.text[:200]}")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # 5. Try reader3 with Referer
    print("\n=== 5. Reader3 with Referer ===")
    r3_headers = {**HEADERS, "Referer": f"https://e.issuu.com/embed.html?u={USER}&d={DOC_NAME}"}
    r3_url = f"https://reader3.isu.pub/{USER}/{DOC_NAME}/reader3.json"
    rr3 = requests.get(r3_url, headers=r3_headers, timeout=10)
    ct3 = rr3.headers.get("content-type", "")
    print(f"reader3.json: {rr3.status_code} | {ct3[:30]} | {len(rr3.content)} bytes")
    if rr3.status_code == 200:
        print(rr3.text[:400])
