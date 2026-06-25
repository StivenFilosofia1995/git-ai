"""Probe EPM sitemap to find event URLs and examine one event page."""
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import sys

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CulturEterea/1.0)"}

# 1. Parse sitemap
r = requests.get("https://www.grupo-epm.com/site/fundacionepm.sitemap.xml",
                  headers=HEADERS, timeout=20)
print(f"Sitemap status: {r.status_code}")

root = ET.fromstring(r.text)
ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
urls = [el.text for el in root.findall(".//sm:loc", ns)]
prog_urls = [u for u in urls if "programacion" in u]

print(f"Total sitemap URLs: {len(urls)}")
print(f"Programacion URLs: {len(prog_urls)}")
print()
for u in prog_urls[:20]:
    print(u)

# 2. Fetch one event page to see structure
if prog_urls:
    detail_urls = [u for u in prog_urls if u.rstrip("/").count("/") > 6]
    target = detail_urls[0] if detail_urls else prog_urls[0]
    print(f"\n=== Fetching detail page: {target} ===")
    r2 = requests.get(target, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r2.text, "html.parser")

    # Look for title
    title = soup.find("h1") or soup.find("h2")
    print(f"H1/H2: {title.get_text(strip=True) if title else 'NOT FOUND'}")

    # Look for dates
    for tag in soup.find_all(["time", "span", "p", "div"]):
        txt = tag.get_text(strip=True)
        # dates often contain digits like 2025 or 2026
        if any(y in txt for y in ["2025", "2026", "2027"]) and len(txt) < 100:
            print(f"Date candidate [{tag.name}.{tag.get('class','')}]: {txt[:120]}")

    # Print meta tags
    print("\n--- Meta tags ---")
    for m in soup.find_all("meta"):
        name = m.get("name") or m.get("property") or ""
        content = m.get("content") or ""
        if any(k in name.lower() for k in ["date", "time", "event", "description", "title"]):
            print(f"  {name}: {content[:120]}")

    # Print data-cmp-data-layer attributes
    print("\n--- data-cmp-data-layer ---")
    cnt = 0
    for tag in soup.find_all(attrs={"data-cmp-data-layer": True}):
        print(f"  {tag['data-cmp-data-layer'][:200]}")
        cnt += 1
        if cnt >= 10:
            break

    # Look for JSON+LD
    print("\n--- JSON-LD ---")
    for s in soup.find_all("script", type="application/ld+json"):
        print(s.string[:500] if s.string else "")
