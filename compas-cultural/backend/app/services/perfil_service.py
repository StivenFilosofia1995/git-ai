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
        "telefono": data.get("telefono"),
        "bio": data.get("bio"),
        "ubicacion_barrio": data.get("ubicacion_barrio"),
        "ubicacion_lat": data.get("ubicacion_lat"),
        "ubicacion_lng": data.get("ubicacion_lng"),
    }
    # Remove None values to avoid overwriting defaults
    row = {k: v for k, v in row.items() if v is not None}
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
    Algoritmo de recomendación con aprendizaje basado en:
    1. Preferencias declaradas del usuario (peso alto)
    2. Categorías de sus interacciones recientes con time decay
    3. Zona/barrio donde vive
    4. Historial de búsquedas
    5. Barrios visitados frecuentemente
    6. Diversificación (no solo lo mismo de siempre)
    """
    perfil = obtener_perfil(user_id)

    # Construir puntaje de categorías y barrios
    cat_scores: Counter = Counter()
    barrio_scores: Counter = Counter()

    # 1. Preferencias declaradas (peso alto)
    if perfil and perfil.get("preferencias"):
        for cat in perfil["preferencias"]:
            cat_scores[cat] += 8

    # 2. Interacciones recientes con time decay
    hace_60d = (datetime.utcnow() - timedelta(days=60)).isoformat()
    resp_inter = (
        supabase.table("interacciones_usuario")
        .select("categoria, tipo, created_at, metadata")
        .eq("user_id", user_id)
        .gte("created_at", hace_60d)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    now = datetime.utcnow()
    for inter in resp_inter.data:
        if not inter.get("categoria"):
            continue
        # Time decay: recent interactions weigh more
        created = datetime.fromisoformat(inter["created_at"].replace("Z", "+00:00").replace("+00:00", ""))
        days_ago = (now - created).days
        decay = max(0.2, 1.0 - (days_ago / 60.0))  # Linear decay over 60 days

        tipo_peso = {"view_evento": 3, "view_espacio": 2, "click": 4, "share": 5, "chat_mention": 2}.get(inter["tipo"], 1)
        cat_scores[inter["categoria"]] += tipo_peso * decay

        # Track barrio visits
        meta = inter.get("metadata") or {}
        if meta.get("barrio"):
            barrio_scores[meta["barrio"]] += decay

    # 3. Historial de búsquedas con time decay
    resp_busq = (
        supabase.table("historial_busqueda")
        .select("categorias_resultado, query, created_at")
        .eq("user_id", user_id)
        .gte("created_at", hace_60d)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    for busq in resp_busq.data:
        created = datetime.fromisoformat(busq["created_at"].replace("Z", "+00:00").replace("+00:00", ""))
        days_ago = (now - created).days
        decay = max(0.3, 1.0 - (days_ago / 60.0))
        for cat in (busq.get("categorias_resultado") or []):
            cat_scores[cat] += 1.5 * decay

    # Categorías top
    top_cats = [cat for cat, _ in cat_scores.most_common(8)]
    top_barrios = [b for b, _ in barrio_scores.most_common(5)]

    # If no behavioral data, use popular categories
    if not top_cats:
        top_cats = ["teatro", "musica", "artes_visuales", "hip_hop", "danza", "jazz", "electronica"]

    # Fetch upcoming events
    ahora = datetime.utcnow().isoformat()
    resp_all = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", ahora)
        .order("fecha_inicio")
        .limit(80)
        .execute()
    )

    # Zona-specific events
    resp_zona_data = []
    if perfil and perfil.get("municipio"):
        resp_zona = (
            supabase.table("eventos")
            .select("*")
            .gte("fecha_inicio", ahora)
            .eq("municipio", perfil["municipio"])
            .order("fecha_inicio")
            .limit(30)
            .execute()
        )
        resp_zona_data = resp_zona.data

    # Score each event
    scored_events = []
    seen_ids = set()
    # Already interacted items (to reduce but not eliminate)
    interacted_ids = {inter.get("item_id") for inter in resp_inter.data if inter.get("item_id")}

    all_events = resp_zona_data + resp_all.data
    for ev in all_events:
        if ev["id"] in seen_ids:
            continue
        seen_ids.add(ev["id"])

        score = 0.0
        cat = ev.get("categoria_principal", "")

        # Category match (decaying by rank)
        if cat in top_cats:
            score += 10 - top_cats.index(cat) * 1.2

        # Zone/municipio match
        if perfil and ev.get("municipio") == perfil.get("municipio"):
            score += 4

        # Barrio match from behavior
        if ev.get("barrio") and ev["barrio"] in top_barrios:
            score += 3

        # Barrio match from profile
        if perfil and perfil.get("ubicacion_barrio") and ev.get("barrio") == perfil["ubicacion_barrio"]:
            score += 5

        # Bonus for free events
        if ev.get("es_gratuito"):
            score += 1.5

        # Bonus for events with image (better UX)
        if ev.get("imagen_url"):
            score += 0.5

        # Slight penalty for already seen (not too much — people revisit)
        if ev["id"] in interacted_ids:
            score *= 0.6

        # Proximity bonus for sooner events (next 3 days)
        try:
            ev_date = datetime.fromisoformat(ev["fecha_inicio"].replace("Z", "+00:00").replace("+00:00", ""))
            days_until = (ev_date - now).days
            if days_until <= 3:
                score += 3
            elif days_until <= 7:
                score += 1
        except (ValueError, TypeError):
            pass

        scored_events.append((score, ev))

    # Sort by score, with slight diversification
    scored_events.sort(key=lambda x: x[0], reverse=True)

    # Diversify: don't show more than 3 of same category in top results
    result = []
    cat_count: Counter = Counter()
    for score, ev in scored_events:
        cat = ev.get("categoria_principal", "")
        if cat_count[cat] >= 3 and len(result) < limit:
            continue
        cat_count[cat] += 1
        result.append(ev)
        if len(result) >= limit:
            break

    return result


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
