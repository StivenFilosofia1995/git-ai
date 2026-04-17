"""Quick: check lugar coordinates."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import supabase

r = supabase.table("lugares").select("id,nombre,lat,lng").execute()
with_coords = [l for l in r.data if l.get("lat") and l.get("lng")]
print(f"Con coordenadas: {len(with_coords)} de {len(r.data)}")
for l in with_coords[:10]:
    print(f"  {l['nombre'][:40]:40s} lat={l['lat']} lng={l['lng']}")
if len(with_coords) > 10:
    print(f"  ... y {len(with_coords)-10} mas")
