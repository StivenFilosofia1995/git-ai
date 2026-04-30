"""
Ve el HTML completo de un evento de biblioteca para entender la estructura real.
Código puro - sin AI.
"""
import sys, re, json, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "https://bibliotecasmedellin.gov.co"

URLS = [
    "https://bibliotecasmedellin.gov.co/actividades/universo-gamer/",
    "https://bibliotecasmedellin.gov.co/actividades/cinefilias-13/",
    "https://bibliotecasmedellin.gov.co/actividades/tu-parche-en-la-biblio-3/",
]

for url in URLS:
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    r = requests.get(url, headers=H, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Extrae todos los textos de widgets de Elementor
    print("--- Elementor widget texts ---")
    widgets = soup.find_all(class_=re.compile(r'elementor-widget'))
    for w in widgets:
        text = w.get_text(" ", strip=True)
        if text and len(text) > 5 and len(text) < 500:
            # Filter out pure nav/menu text
            if not any(nav in text for nav in ["Facebook", "Instagram", "Youtube", "Twitter", "Menú"]):
                print(f"  [{w.get('class', [''])[0]}] {text[:250]}")
    
    # Busca specific clases de info de evento
    print("--- Info específica ---")
    body_text = soup.get_text(" ", strip=True)
    
    # Fechas explícitas
    dates_full = re.findall(
        r'\b(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)(?:\s+\d{1,2}\s+de\s+\w+)?\b',
        body_text, re.IGNORECASE
    )
    print(f"  Días semana: {dates_full[:5]}")
    
    # dd de mes de yyyy o dd de mes  
    dates2 = re.findall(r'\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+de\s+\d{4})?', body_text, re.IGNORECASE)
    print(f"  Fechas texto: {dates2[:5]}")
    
    # "cada" frecuencia
    recurrence = re.findall(r'(?:cada|todos\s+los?|semanalmente|mensualmente)[^.;\n]{0,60}', body_text, re.IGNORECASE)
    print(f"  Recurrencia: {recurrence[:3]}")
    
    # Hora
    times = re.findall(r'\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?|horas?)?', body_text, re.IGNORECASE)
    print(f"  Horas: {times[:5]}")
    
    # Sede / biblioteca específica
    # Find any h1-h4 tags
    headers = [h.get_text(strip=True) for h in soup.find_all(["h1","h2","h3","h4"])]
    print(f"  Headers: {headers[:8]}")
    
    # Descripción
    desc_elems = soup.find_all(class_=re.compile(r'description|excerpt|resumen|content', re.I))
    for d in desc_elems[:2]:
        text = d.get_text(" ", strip=True)
        if 20 < len(text) < 300:
            print(f"  Desc: {text[:200]}")
    
    # Buscar "Parque Biblioteca" or library name in specific positions
    all_ps = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    for i, p in enumerate(all_ps[:20]):
        if any(k in p for k in ["Biblioteca", "biblioteca", "Parque", "UVA", "sede", "Sede"]):
            print(f"  P[{i}] venue: {p[:150]}")

    # Elementor info boxes / icon lists
    icon_lists = soup.find_all(class_=re.compile(r'icon-list|elementor-icon-list'))
    for il in icon_lists[:3]:
        text = il.get_text(" ", strip=True)
        print(f"  Icon list: {text[:200]}")

    # Check for a table or structured info section
    info_section = soup.find(class_=re.compile(r'info|detail|meta', re.I))
    if info_section:
        print(f"  Info section: {info_section.get_text(' ', strip=True)[:200]}")
