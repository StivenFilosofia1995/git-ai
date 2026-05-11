"""Fix events with fecha_fin=NULL that started before today — set fecha_fin = end of their start day."""
from app.database import supabase

TODAY = "2026-05-04"

res = supabase.table("eventos").select("id,titulo,fecha_inicio,fecha_fin").is_("fecha_fin", "null").lt("fecha_inicio", TODAY).execute()
print(f"Eventos con fecha_fin NULL y inicio < {TODAY}: {len(res.data)}")
for e in res.data:
    inicio = (e.get("fecha_inicio") or "")[:10]
    titulo = e.get("titulo", "?")[:55]
    print(f"  Fixing: {titulo} | {inicio}")
    fecha_fin_str = inicio + "T23:59:59"
    supabase.table("eventos").update({"fecha_fin": fecha_fin_str}).eq("id", e["id"]).execute()

print("Done. Checking remaining NULL fin events before today...")
res2 = supabase.table("eventos").select("id,titulo,fecha_inicio").is_("fecha_fin", "null").lt("fecha_inicio", TODAY).execute()
print(f"Remaining: {len(res2.data)}")
