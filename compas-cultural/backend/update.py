import re

with open('app/services/event_fallback_discovery.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add texto to _scrape_known_sites
text = re.sub(
    r"async def _scrape_known_sites\(\s*\*\,\s*municipio: Optional\[str\],\s*categoria: Optional\[str\],\s*max_sites: int = 6,\s*\) -> list\[dict\]:",
    "async def _scrape_known_sites(\n    *,\n    municipio: Optional[str],\n    categoria: Optional[str],\n    texto: Optional[str] = None,\n    max_sites: int = 6,\n) -> list[dict]:",
    text,
    count=1
)

# Update _matches inside _scrape_known_sites
old_matches = '''        if categoria and site.get("categorias"):
            cat_norm = categoria.replace("_", " ").lower()
            site_cats = [c.replace("_", " ").lower() for c in site["categorias"]]
            if not any(cat_norm in sc or sc in cat_norm for sc in site_cats):
                return False
        return True'''
new_matches = '''        if categoria and site.get("categorias"):
            cat_norm = categoria.replace("_", " ").lower()
            site_cats = [c.replace("_", " ").lower() for c in site["categorias"]]
            if not any(cat_norm in sc or sc in cat_norm for sc in site_cats):
                return False
        if texto:
            t = texto.lower()
            sn = site.get("nombre", "").lower()
            su = site.get("url", "").lower()
            sm = site.get("municipio", "").lower()
            # Si el texto de busqueda no esta en el nombre, URL o municipio (y la busqueda no es un simple check por muni)
            # Solo scrapeamos este sitio si hace match.
            if t not in sn and t not in su and t not in sm and sm not in t:
                return False
        return True'''
text = text.replace(old_matches, new_matches)

# Pass texto to _scrape_known_sites
text = re.sub(
    r"known_events = await _scrape_known_sites\(\s*municipio=municipio,\s*categoria=categoria,\s*max_sites=10,\s*\)",
    "known_events = await _scrape_known_sites(\n        municipio=municipio,\n        categoria=categoria,\n        texto=texto,\n        max_sites=10,\n    )",
    text
)

# Avoid picking the whole array if there are zero matching matches when we supply a specific texto.
old_fallback = '''    matching_sites = [s for s in KNOWN_CULTURAL_SITES if _matches(s)]
    if not matching_sites:
        matching_sites = list(KNOWN_CULTURAL_SITES)'''
new_fallback = '''    matching_sites = [s for s in KNOWN_CULTURAL_SITES if _matches(s)]
    if not matching_sites and not texto:
        matching_sites = list(KNOWN_CULTURAL_SITES)'''
text = text.replace(old_fallback, new_fallback)


with open('app/services/event_fallback_discovery.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated successfully")
