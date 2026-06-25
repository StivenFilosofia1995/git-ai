"""Debug: inspect full card structure of Pablo Tobon"""
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
    cards = soup.find_all("div", class_="card")
    print(f"Total .card divs: {len(cards)}")
    for card in cards[:3]:
        print("\n=== CARD ===")
        print(card.get_text(" | ", strip=True)[:400])

asyncio.run(run())
