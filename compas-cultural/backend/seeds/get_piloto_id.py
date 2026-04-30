"""Get Piloto espacio_id."""
import sys
sys.path.insert(0, '.')
from app.database import supabase as sb

r = sb.table('lugares').select('id,nombre').ilike('nombre','%piloto%').execute()
print(r.data)
r2 = sb.table('lugares').select('id,nombre').ilike('nombre','%bibliotecas%').execute()
print(r2.data)
r3 = sb.table('lugares').select('id,nombre').ilike('nombre','%EPM%').execute()
print(r3.data)
