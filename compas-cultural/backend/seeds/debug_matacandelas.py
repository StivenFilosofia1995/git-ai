"""Debug: Matacandelas and Piloto HTML structure"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx
from bs4 import BeautifulSoup
import re

async def run():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
        # Matacandelas
        r = await c.get("https://www.matacandelas.com/index.html", headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        print("=== MATACANDELAS ===")
        # Show all headings and dates context
        from app.services.html_event_extractor import parse_date
        from datetime import datetime
        now = datetime.now()
        elements_with_dates = []
        for el in soup.find_all(["section", "div", "article", "li", "p"]):
            text = el.get_text(" ", strip=True)
            if len(text) < 20 or len(text) > 2000:
                continue
            if parse_date(text, now.year):
                h = el.find(["h2","h3","h4","h5","b","strong"])
                if h:
                    elements_with_dates.append((h.get_text(strip=True), text[:200]))
        for title, text in elements_with_dates[:5]:
            print(f"  TITLE: {title}")
            print(f"  TEXT: {text[:150]}")
            print()

        # Piloto
        r2 = await c.get("https://bibliotecapiloto.gov.co/agenda", headers=headers)
        soup2 = BeautifulSoup(r2.text, "html.parser")
        print("=== PILOTO ===")
        print("Total headings:", len(soup2.find_all(["h2","h3","h4","h5"])))
        for h in soup2.find_all(["h2","h3","h4","h5"])[:5]:
            print(" ", h.name, ":", h.get_text(strip=True)[:100])
        # Find elements with date patterns
        for el in soup2.find_all(["div","article","li"])[:50]:
            text = el.get_text(" ", strip=True)
            if parse_date(text, now.year) and 20 < len(text) < 500:
                print("DATE CONTAINER:", text[:200])
                break

asyncio.run(run())
