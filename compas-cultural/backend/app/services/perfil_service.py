from typing import List, Optional
from collections import Counter
from datetime import datetime, timedelta

from app.database import supabase


def crear_perfil(user_id: str, data: dict) -> dict:
    """Crea un perfil de usuario."""
    row = {
        "user_id": user_id,
        "nombre": data["nombre"],
        "apellido": data["apellido"],
        "email": data["email"],
        "preferencias": data.get("preferencias", []),
        "zona_id": data.get("zona_id"),
        "municipio": data.get("municipio", "medellin"),
    }
    resp = supabase.table("perfiles_usuario").insert(row).execute()
    return resp.data[0]


def obtener_perfil(user_id: str) -> Optional[dict]:
    """Obtiene el perfil de un usuario."""
    resp = (
        supabase.table("perfiles_usuario")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def actualizar_perfil(user_id: str, data: dict) -> dict:
    """Actualiza campos del perfil."""
    update = {k: v for k, v in data.items() if v is not None}
    update["updated_at"] = datetime.utcnow().isoformat()
    resp = (
        supabase.table("perfiles_usuario")
        .update(update)
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data[0]


def registrar_interaccion(user_id: str, tipo: str, item_id: str, categoria: Optional[str] = None) -> None:
    """Registra una interacción del usuario (view, click)."""
    supabase.table("interacciones_usuario").insert({
        "user_id": user_id,
        "tipo": tipo,
        "item_id": item_id,
        "categoria": categoria,
    }).execute()


def registrar_busqueda(user_id: str, query: str, categorias: List[str]) -> None:
    """Registra una búsqueda del usuario."""
    supabase.table("historial_busqueda").insert({
        "user_id": user_id,
        "query": query,
        "categorias_resultado": categorias,
    }).execute()


def obtener_recomendaciones(user_id: str, limit: int = 10) -> List[dict]:
    """
    Algoritmo de recomendación basado en:
    1. Preferencias declaradas del usuario
    2. Categorías de sus interacciones recientes
    3. Zona donde vive
    4. Historial de búsquedas
    """
    perfil = obtener_perfil(user_id)

    # Construir puntaje de categorías
    cat_scores: Counter = Counter()

    # 1. Preferencias declaradas (peso alto)
    if perfil and perfil.get("preferencias"):
        for cat in perfil["preferencias"]:
            cat_scores[cat] += 5

    # 2. Interacciones recientes (últimos 30 días)
    hace_30d = (datetime.utcnow() - timedelta(days=30)).isoformat()
    resp_inter = (
        supabase.table("interacciones_usuario")
        .select("categoria, tipo")
        .eq("user_id", user_id)
        .gte("created_at", hace_30d)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    for inter in resp_inter.data:
        if inter.get("categoria"):
            peso = 3 if inter["tipo"] == "view_evento" else 2
            cat_scores[inter["categoria"]] += peso

    # 3. Historial de búsquedas (últimos 30 días)
    resp_busq = (
        supabase.table("historial_busqueda")
        .select("categorias_resultado")
        .eq("user_id", user_id)
        .gte("created_at", hace_30d)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    for busq in resp_busq.data:
        for cat in (busq.get("categorias_resultado") or []):
            cat_scores[cat] += 1

    # Categorías top
    top_cats = [cat for cat, _ in cat_scores.most_common(5)]

    # Si no hay datos de comportamiento, usar categorías populares
    if not top_cats:
        top_cats = ["teatro", "musica", "artes_visuales", "hip_hop", "danza"]

    # Buscar eventos relevantes
    ahora = datetime.utcnow().isoformat()
    query_eventos = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", ahora)
        .order("fecha_inicio")
        .limit(50)
    )

    # Filtrar por zona/municipio del usuario
    if perfil and perfil.get("municipio"):
        query_eventos_zona = (
            supabase.table("eventos")
            .select("*")
            .gte("fecha_inicio", ahora)
            .eq("municipio", perfil["municipio"])
            .order("fecha_inicio")
            .limit(30)
        )
        resp_zona = query_eventos_zona.execute()
    else:
        resp_zona = type("R", (), {"data": []})()

    resp_all = query_eventos.execute()

    # Puntuar cada evento
    scored_events = []
    seen_ids = set()

    all_events = resp_zona.data + resp_all.data
    for ev in all_events:
        if ev["id"] in seen_ids:
            continue
        seen_ids.add(ev["id"])

        score = 0
        cat = ev.get("categoria_principal", "")

        # Coincidencia de categoría
        if cat in top_cats:
            score += 10 - top_cats.index(cat)  # Más peso a categorías top

        # Bonus por zona del usuario
        if perfil and ev.get("municipio") == perfil.get("municipio"):
            score += 3

        # Bonus por gratuito
        if ev.get("es_gratuito"):
            score += 1

        # Bonus por imagen (mejor UX)
        if ev.get("imagen_url"):
            score += 1

        scored_events.append((score, ev))

    # Ordenar por score descendente
    scored_events.sort(key=lambda x: x[0], reverse=True)

    return [ev for _, ev in scored_events[:limit]]


def obtener_eventos_zona_hoy(zona_id: int) -> List[dict]:
    """Obtiene eventos de hoy en una zona específica, con imágenes."""
    # Obtener la zona
    resp_zona = (
        supabase.table("zonas_culturales")
        .select("*")
        .eq("id", zona_id)
        .single()
        .execute()
    )
    zona = resp_zona.data
    if not zona:
        return []

    municipio = zona.get("municipio", "medellin")
    nombre_zona = zona.get("nombre", "").lower()

    ahora_co = datetime.utcnow() - timedelta(hours=5)
    hoy = ahora_co.date().isoformat()
    manana = (ahora_co.date() + timedelta(days=1)).isoformat()

    # Buscar eventos de hoy en ese municipio
    resp = (
        supabase.table("eventos")
        .select("*")
        .eq("municipio", municipio)
        .gte("fecha_inicio", hoy)
        .lt("fecha_inicio", manana)
        .order("fecha_inicio")
        .limit(10)
        .execute()
    )

    # Si no hay eventos hoy, buscar próximos 3 días
    if not resp.data:
        tres_dias = (ahora_co.date() + timedelta(days=3)).isoformat()
        resp = (
            supabase.table("eventos")
            .select("*")
            .eq("municipio", municipio)
            .gte("fecha_inicio", hoy)
            .lt("fecha_inicio", tres_dias)
            .order("fecha_inicio")
            .limit(6)
            .execute()
        )

    # También buscar espacios activos en esa zona/barrio
    resp_espacios = (
        supabase.table("lugares")
        .select("id,nombre,slug,categoria_principal,barrio,descripcion_corta,instagram_handle")
        .eq("municipio", municipio)
        .neq("nivel_actividad", "cerrado")
        .limit(6)
        .execute()
    )

    return {
        "eventos": resp.data,
        "espacios": resp_espacios.data,
        "zona": zona,
    }
