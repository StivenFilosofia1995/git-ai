"""Debug: test exact scraper prompt with Comfama content."""
import asyncio, json, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
import anthropic
import httpx
from bs4 import BeautifulSoup
from app.config import settings
from app.services.auto_scraper import EVENT_EXTRACTION_PROMPT

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-CO,es;q=0.9",
}

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

async def main():
    # Fetch real content
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as c:
        resp = await c.get("https://www.comfama.com/agenda/", headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    content = soup.get_text(separator="\n", strip=True)[:8000]

    now_iso = datetime.utcnow().isoformat()
    
    prompt = EVENT_EXTRACTION_PROMPT.format(
        fecha_actual=now_iso,
        nombre_lugar="Comfama Cultura",
        lugar_id="test-id",
        categoria="centro_cultural",
        municipio="medellin",
        fuente_tipo="sitio_web",
        fuente_url="https://www.comfama.com/agenda/",
        contenido=content,
    )
    
    print(f"Prompt length: {len(prompt)}")
    print("--- PROMPT START ---")
    print(prompt[:500])
    print("--- PROMPT END ---")
    
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    print(f"\n--- CLAUDE RESPONSE ({len(raw)} chars) ---")
    print(raw[:1000])
    
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", raw)
        data = json.loads(fixed)
    
    events = data.get("eventos", [])
    print(f"\nEventos: {len(events)}")
    for e in events:
        print(f"  {e.get('fecha_inicio','-')[:10]} | {e.get('titulo','-')[:60]}")

asyncio.run(main())
