"""Debug: inspect actual HTML structure of Pablo Tobon event cards"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx
from bs4 import BeautifulSoup
import re

async def run():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
        r = await c.get("https://teatropablotobon.com/eventos/", headers=headers)
        html = r.text

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=re.compile(r"/evento/"))
    print(f"Total event links: {len(links)}")
    for link in links[:5]:
        print("\n--- LINK ---")
        print("href:", link.get("href","")[:80])
        print("direct text:", link.get_text(strip=True)[:100])
        # Show parent structure (up 3 levels)
        node = link.parent
        for i in range(3):
            if node:
                print(f"  parent[{i}] tag={node.name} class={node.get('class','')}")
                # Show headings inside parent
                hs = node.find_all(["h2","h3","h4","h5"])
                for h in hs[:3]:
                    print(f"    heading: {h.get_text(strip=True)[:80]}")
                node = node.parent

asyncio.run(run())
