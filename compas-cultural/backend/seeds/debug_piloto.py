"""Debug Piloto page structure in more detail"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx
from bs4 import BeautifulSoup

async def run():
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
        r = await c.get("https://bibliotecapiloto.gov.co/agenda", headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        
    # Show the first 3000 chars of body text
    body = soup.find("body")
    print("Status:", len(r.text), "chars")
    print("Body text (first 2000):")
    print(body.get_text(" ", strip=True)[:2000] if body else "no body")
    
    # Show all tags with class names containing "agenda|evento|card|item"
    import re
    tagged = soup.find_all(class_=re.compile(r"agenda|event|card|item|calendario", re.I))
    print(f"\nFound {len(tagged)} elements with event-related classes:")
    for t in tagged[:5]:
        print(f"  <{t.name} class={t.get('class','')}> {t.get_text(strip=True)[:100]}")

asyncio.run(run())
