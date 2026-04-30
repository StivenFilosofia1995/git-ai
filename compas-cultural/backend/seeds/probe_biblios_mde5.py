"""
Extrae fecha, hora y sede real de páginas individuales de actividades.
También pagina cpt_eventos_mes y busca categorías en posts normales.
Código puro - sin AI.
"""
import sys, re, json, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

# 1. Cuántas páginas tiene cpt_eventos_mes?
print("=== 1. Paginación cpt_eventos_mes ===")
r = requests.get(
    f"{BASE}/wp-json/wp/v2/cpt_eventos_mes",
    params={"per_page": 100, "page": 1},
    headers=H, timeout=20
)
total = r.headers.get('X-WP-Total', '?')
total_pages = r.headers.get('X-WP-TotalPages', '?')
print(f"Total: {total} | Pages: {total_pages}")

# 2. Posts normales filtrados por categoría de biblioteca
print("\n=== 2. Posts por categoría biblioteca (cat 164 = León de Greiff) ===")
for cat_id, cat_name in [(164, "León de Greiff"), (163, "Guayabal"), (199, "Tomás Carrasquilla"), (170, "San Javier")]:
    r2 = requests.get(
        f"{BASE}/wp-json/wp/v2/posts",
        params={"categories": cat_id, "per_page": 5, "_fields": "id,date,title,link"},
        headers=H, timeout=10
    )
    data2 = r2.json()
    print(f"  Cat {cat_id} ({cat_name}): {len(data2)} posts")
    for p in data2[:2]:
        print(f"    {p['date'][:10]} | {p['title']['rendered'][:60]}")

# 3. Explorar evento individual completo
print("\n=== 3. Parse HTML de 3 eventos individuales ===")
# Get 3 links from cpt_eventos_mes
sample_links = []
for e in r.json()[:10]:
    if e.get('link'):
        sample_links.append((e['title']['rendered'], e['link']))

def extract_event_details(url, title):
    try:
        resp = requests.get(url, headers=H, timeout=15)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        
        result = {"url": url, "title": title}
        
        # 1. Elementor widgets - buscar info específica
        text_blocks = soup.find_all(class_=re.compile(r'elementor-widget-text'))
        for block in text_blocks[:5]:
            text = block.get_text(" ", strip=True)
            if any(k in text.lower() for k in ["fecha", "hora", "sede", "lugar", "biblioteca"]):
                result[f"text_block"] = text[:200]
        
        # 2. Tabla de detalles
        tables = soup.find_all("table")
        for t in tables[:2]:
            rows = t.find_all("tr")
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
                if cells:
                    result[f"table_row"] = cells
        
        # 3. DL / definición
        dls = soup.find_all("dl")
        for dl in dls[:2]:
            result["dl"] = dl.get_text(" ", strip=True)[:200]
        
        # 4. Fecha en cualquier elemento con clase date/time
        date_elems = soup.find_all(class_=re.compile(r'date|time|hora|fecha', re.I))
        for el in date_elems[:5]:
            text = el.get_text(strip=True)
            if text and len(text) < 100:
                result[f"date_elem"] = text
        
        # 5. Metadata Yoast / JSON-LD
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                obj = json.loads(script.string)
                if "@graph" in obj:
                    for item in obj["@graph"]:
                        if item.get("@type") in ["Event", "SocialEvent"]:
                            result["jsonld_event"] = item
                elif obj.get("@type") in ["Event", "SocialEvent"]:
                    result["jsonld_event"] = obj
            except:
                pass
        
        # 6. Texto completo del body - buscar patrones de fecha
        body_text = soup.get_text(" ", strip=True)
        dates = re.findall(r'\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4}\b', body_text, re.IGNORECASE)
        times_found = re.findall(r'\b\d{1,2}:\d{2}\s*(?:[ap]\.?m\.?|horas?)?\b', body_text, re.IGNORECASE)
        
        result["dates_in_text"] = dates[:3]
        result["times_in_text"] = times_found[:5]
        
        # 7. Parche: buscar el "mes" mencionado
        months = re.findall(r'\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', body_text[:2000], re.IGNORECASE)
        result["months_mentioned"] = list(set(months))
        
        # 8. Sede - buscar nombre de biblioteca en texto
        lib_names = [
            "España", "Belén", "León de Greiff", "La Ladera", "Tomás Carrasquilla",
            "San Javier", "Guayabal", "Doce de Octubre", "Nuevo Occidente", "San Cristóbal",
            "El Poblado", "Santa Cruz", "Altavista", "La Floresta", "Piloto",
            "Parque Biblioteca", "Unidad de Vida"
        ]
        found_libs = [lib for lib in lib_names if lib.lower() in body_text.lower()]
        result["libraries_in_text"] = found_libs[:5]
        
        return result
    except Exception as e:
        return {"url": url, "error": str(e)}

for title, link in sample_links[:5]:
    details = extract_event_details(link, title)
    print(f"\n  --- {title[:50]} ---")
    print(f"  URL: {link}")
    for k, v in details.items():
        if k not in ['url', 'title']:
            print(f"  {k}: {str(v)[:200]}")

# 4. Posts normales con categorías - ver contenido de uno
print("\n=== 4. Post normal con categoría biblioteca ===")
r4 = requests.get(
    f"{BASE}/wp-json/wp/v2/posts",
    params={"categories": "164", "per_page": 1, "_fields": "id,date,title,link,content,excerpt,categories"},
    headers=H, timeout=10
)
data4 = r4.json()
if data4:
    p = data4[0]
    content = re.sub(r'<[^>]+>', '', p.get('content', {}).get('rendered', ''))[:500]
    print(f"  Title: {p['title']['rendered']}")
    print(f"  Date: {p['date']}")
    print(f"  Content: {content}")
    print(f"  Link: {p['link']}")
