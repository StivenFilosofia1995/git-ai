from fastapi import APIRouter
from app.database import supabase

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "healthy", "service": "compas-cultural-api"}


@router.get("/stats")
def get_stats():
    """Real-time counts for espacios, eventos, zonas."""
    try:
        espacios = supabase.table("lugares").select("id", count="exact").execute()
        eventos = supabase.table("eventos").select("id", count="exact").execute()
        zonas = supabase.table("zonas_culturales").select("id", count="exact").execute()
        return {
            "espacios": espacios.count or len(espacios.data),
            "eventos": eventos.count or len(eventos.data),
            "zonas": zonas.count or len(zonas.data),
        }
    except Exception:
        return {"espacios": 0, "eventos": 0, "zonas": 0}