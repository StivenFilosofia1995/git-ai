"""
Verifica si content.rendered de cpt_eventos_mes contiene fecha/venue sin visitar páginas individuales.
"""
import sys, re, requests, json
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://bibliotecasmedellin.gov.co"

r = requests.get(
    f"{BASE}/wp-json/wp/v2/cpt_eventos_mes",
    params={"per_page": 3, "_fields": "id,title,link,content,excerpt"},
    headers=H, timeout=20
)
data = r.json()
print(f"Total from header: {r.headers.get('X-WP-Total')}")
for e in data:
    print(f"\n{'='*50}")
    print(f"Title: {e['title']['rendered']}")
    print(f"Link: {e['link']}")
    
    content_html = e.get('content', {}).get('rendered', '')
    excerpt_html = e.get('excerpt', {}).get('rendered', '')
    
    print(f"Content length: {len(content_html)}")
    
    if content_html:
        soup = BeautifulSoup(content_html, "html.parser")
        
        # Try to find date/time/venue in content
        all_text = soup.get_text(" ", strip=True)
        print(f"Content text (first 500): {all_text[:500]}")
        
        # Look for date patterns
        dates = re.findall(r'\w+\s+\d{1,2},\s+\d{4}', all_text)
        times = re.findall(r'\d{1,2}:\d{2}\s*[ap]m\.?', all_text, re.IGNORECASE)
        print(f"Dates in content: {dates[:3]}")
        print(f"Times in content: {times[:3]}")
        
        # Widget containers
        widgets = soup.find_all(class_="elementor-widget-container")
        unique = []
        seen = set()
        for w in widgets:
            t = w.get_text(" ", strip=True)
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                unique.append(t)
        print(f"Widget texts: {unique[:8]}")
    else:
        print("NO CONTENT")
    
    print(f"Excerpt: {re.sub(r'<[^>]+>', '', excerpt_html)[:200]}")
