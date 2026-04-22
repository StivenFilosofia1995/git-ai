"""
fix_handles.py — Limpia los instagram_handle con @@ doble o @ al inicio.
Actualiza en Supabase.
"""
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app.database import supabase

result = supabase.table('lugares').select('id,nombre,instagram_handle').not_.is_('instagram_handle', 'null').execute()
lugares = result.data or []

fixed = 0
for l in lugares:
    handle = l['instagram_handle']
    clean = handle.lstrip('@').strip()
    if clean != handle:
        print(f"  CLEAN: {handle!r:35s} -> {clean!r}")
        supabase.table('lugares').update({'instagram_handle': clean}).eq('id', l['id']).execute()
        fixed += 1

print(f'\n✅ {fixed} handles corregidos de {len(lugares)} total')
