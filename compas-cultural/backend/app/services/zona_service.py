import math
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from app.database import supabase
from app.services.ml_utils import log1p_score, activity_to_numeric

CO_TZ = ZoneInfo("America/Bogota")


def _enrich_zona_with_density(zona: dict) -> dict:
    """
    Enriquece una zona con métricas de densidad cultural (ML).

    Métricas añadidas:
      eventos_proximos  — eventos en los próximos 14 días en esta zona
      score_densidad    — log1p(eventos_proximos) — score saturante de actividad
      nivel_actividad   — etiqueta semántica basada en score
    """
    if not zona.get("id"):
        return zona

    try:
        ahora = datetime.now(CO_TZ)
        hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        en_14d = hoy + timedelta(days=14)

        # Buscar eventos en la zona por municipio/barrio keywords
        zona_nombre = zona.get("nombre") or ""
        municipio = zona.get("municipio") or ""

        q = (
            supabase.table("eventos")
            .select("id")
            .gte("fecha_inicio", hoy.isoformat())
            .lte("fecha_inicio", en_14d.isoformat())
        )
        if municipio:
            q = q.ilike("municipio", f"%{municipio}%")

        resp = q.limit(100).execute()
        n_eventos = len(resp.data or [])

        # score_densidad: log1p(n) — satura en valores grandes
        score = log1p_score(n_eventos, cap=5.0)

        # Etiqueta semántica
        if n_eventos >= 20:
            nivel = "muy_activo"
        elif n_eventos >= 8:
            nivel = "activo"
        elif n_eventos >= 3:
            nivel = "regular"
        else:
            nivel = "inactivo"

        zona["_eventos_proximos"] = n_eventos
        zona["_score_densidad"] = round(score, 3)
        zona["_nivel_actividad"] = nivel
    except Exception:
        pass

    return zona


def get_zonas() -> List[dict]:
    response = supabase.table("zonas_culturales").select("*").execute()
    zonas = response.data or []

    # Enriquecer con densidad de eventos y ordenar por score
    zonas = [_enrich_zona_with_density(z) for z in zonas]
    zonas.sort(key=lambda z: z.get("_score_densidad", 0.0), reverse=True)
    return zonas


def get_zona_by_slug(slug: str) -> dict:
    response = (
        supabase.table("zonas_culturales")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )
    return _enrich_zona_with_density(response.data)