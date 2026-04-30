"""Probe Issuu reader3 API - get page text directly (no PDF download needed)."""
import requests
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}
USER = "bibliotecaepm1"
DOC = "programacion_formativa_mayo_-_bepm"

# 1. Get document metadata via reader3.json
r3_url = f"https://reader3.isu.pub/{USER}/{DOC}/reader3.json"
print(f"Fetching reader3: {r3_url}")
r = requests.get(r3_url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code} | Content-Type: {r.headers.get('content-type','')}")
if r.status_code == 200:
    try:
        data = r.json()
        # Show top-level keys
        for k, v in data.items():
            if k != "pages":
                print(f"  {k}: {str(v)[:100]}")
        pages = data.get("pages", [])
        print(f"  pages count: {len(pages)}")
        if pages:
            print(f"  first page keys: {list(pages[0].keys())[:10]}")
            print(f"  first page: {str(pages[0])[:200]}")
    except Exception as e:
        print(f"JSON error: {e}")
        print(r.text[:500])
else:
    print(r.text[:300])

# 2. Try text endpoint for page 1
print("\n--- Page text ---")
for fmt in [".txt", ".xml", ".json", ""]:
    txt_url = f"https://reader3.isu.pub/{USER}/{DOC}/text/page_1{fmt}"
    rt = requests.get(txt_url, headers=HEADERS, timeout=10)
    print(f"{txt_url[-50:]}: {rt.status_code} | {rt.headers.get('content-type','')[:30]} | {len(rt.content)} bytes")
    if rt.status_code == 200 and rt.text.strip():
        print(f"  Content preview: {rt.text[:300]}")

# 3. Try getting the oEmbed thumbnail to derive revision_id and then page images
oembed_url = f"https://issuu.com/oembed?url=https://issuu.com/{USER}/docs/{DOC}&format=json"
r_oe = requests.get(oembed_url, headers=HEADERS, timeout=10)
if r_oe.status_code == 200:
    d = r_oe.json()
    thumb = d.get("thumbnail_url", "")
    print(f"\nThumbnail URL: {thumb}")
    # Extract revision_id
    m = re.search(r"isu\.pub/([^/]+)/jpg/", thumb)
    if m:
        rev_id = m.group(1)
        print(f"Revision ID: {rev_id}")
        # Try downloading full page image
        page_url = f"https://image.isu.pub/{rev_id}/jpg/page_1.large.jpg"
        rp = requests.get(page_url, headers=HEADERS, timeout=15)
        print(f"Page 1 image: {rp.status_code} | {rp.headers.get('content-type','')} | {len(rp.content)} bytes")
        # Try PDF download with revision id
        pdf_url = f"https://pdf.isu.pub/{rev_id}.pdf"
        rp2 = requests.get(pdf_url, headers=HEADERS, timeout=15, allow_redirects=True)
        print(f"PDF by rev_id: {rp2.status_code} | {rp2.headers.get('content-type','')} | {len(rp2.content)} bytes")
