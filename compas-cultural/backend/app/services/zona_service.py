from typing import List

from app.database import supabase


def get_zonas() -> List[dict]:
    response = supabase.table("zonas_culturales").select("*").execute()
    return response.data


def get_zona_by_slug(slug: str) -> dict:
    response = (
        supabase.table("zonas_culturales")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )
    return response.data