from typing import List, Optional
from app.database import supabase


def crear_resena(user_id: str, user_nombre: Optional[str], data: dict) -> dict:
    """Create a review for an event or space."""
    row = {
        "user_id": user_id,
        "user_nombre": user_nombre,
        "tipo": data["tipo"],
        "item_id": data["item_id"],
        "puntuacion": data["puntuacion"],
        "titulo": data.get("titulo"),
        "comentario": data["comentario"],
    }
    resp = supabase.table("resenas").insert(row).execute()
    return resp.data[0]


def obtener_resenas(tipo: str, item_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
    """Get reviews for a specific event or space."""
    resp = (
        supabase.table("resenas")
        .select("*")
        .eq("tipo", tipo)
        .eq("item_id", item_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return resp.data


def obtener_stats(tipo: str, item_id: str) -> dict:
    """Get rating statistics for an event or space."""
    resp = (
        supabase.table("resenas")
        .select("puntuacion")
        .eq("tipo", tipo)
        .eq("item_id", item_id)
        .execute()
    )
    puntuaciones = [r["puntuacion"] for r in resp.data]
    if not puntuaciones:
        return {"promedio": 0, "total": 0, "distribucion": {str(i): 0 for i in range(1, 6)}}

    distribucion = {str(i): puntuaciones.count(i) for i in range(1, 6)}
    return {
        "promedio": round(sum(puntuaciones) / len(puntuaciones), 1),
        "total": len(puntuaciones),
        "distribucion": distribucion,
    }


def obtener_resena_usuario(user_id: str, tipo: str, item_id: str) -> Optional[dict]:
    """Check if user already reviewed this item."""
    resp = (
        supabase.table("resenas")
        .select("*")
        .eq("user_id", user_id)
        .eq("tipo", tipo)
        .eq("item_id", item_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def actualizar_resena(resena_id: str, user_id: str, data: dict) -> dict:
    """Update a review (only owner can update)."""
    update = {k: v for k, v in data.items() if v is not None}
    resp = (
        supabase.table("resenas")
        .update(update)
        .eq("id", resena_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise ValueError("Reseña no encontrada o no autorizado")
    return resp.data[0]


def eliminar_resena(resena_id: str, user_id: str) -> bool:
    """Delete a review (only owner can delete)."""
    resp = (
        supabase.table("resenas")
        .delete()
        .eq("id", resena_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(resp.data) > 0
