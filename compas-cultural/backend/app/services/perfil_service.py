from typing import List, Optional
from collections import Counter
from datetime import datetime, timedelta
import math

from app.database import supabase


# ─── ML helpers ──────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia Haversine en km entre dos coordenadas."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _exponential_time_decay(days_ago: float, half_life_days: float = 14.0) -> float:
    """Decaimiento exponencial: f(t) = e^(-ln2 * t / t_half).
    A diferencia del lineal, nunca llega a 0 y respeta propiedades de señal real."""
    return math.exp(-math.log(2) * days_ago / half_life_days)


def _score_categoria_match(cat: str, top_cats: List[str], cat_scores: Counter) -> float:
    """Score por afinidad de categoría: combina ranking ordinal con peso continuo.

    score = w_rank * (1 - rank/N) + w_magnitude * log1p(raw_score)
    """
    if cat not in top_cats:
        return 0.0
    rank = top_cats.index(cat)
    n = len(top_cats)
    w_rank = 6.0 * (1 - rank / n)
    raw = cat_scores.get(cat, 0.0)
    w_magnitude = min(4.0, math.log1p(raw))  # cap en 4 para no saturar
    return w_rank + w_magnitude


def _score_proximidad(ev: dict, perfil: Optional[dict]) -> float:
    """Score de proximidad geográfica usando Haversine.

    Si hay coords del usuario y del evento: score = 5 * e^(-d/5km).
    Si solo hay coincidencia de barrio/municipio: puntaje nominal.
    """
    if not perfil:
        return 0.0
    u_lat = perfil.get("ubicacion_lat")
    u_lng = perfil.get("ubicacion_lng")
    e_lat = ev.get("lat")
    e_lng = ev.get("lng")
    if u_lat and u_lng and e_lat and e_lng:
        dist = _haversine_km(u_lat, u_lng, e_lat, e_lng)
        return 5.0 * math.exp(-dist / 5.0)  # ~5pts si mismo barrio, ~1pt si 8km
    if perfil.get("ubicacion_barrio") and ev.get("barrio") == perfil["ubicacion_barrio"]:
        return 3.5
    if perfil.get("municipio") and ev.get("municipio") == perfil["municipio"]:
        return 1.5
    return 0.0


def _score_urgencia(ev: dict, now: datetime) -> float:
    """Urgencia temporal: eventos hoy/mañana tienen score máximo.

    score = 4 * e^(-days/3) — decae suave en los próximos días.
    """
    try:
        ev_date = datetime.fromisoformat(ev["fecha_inicio"].replace("Z", "+00:00").replace("+00:00", ""))
        days_until = max(0, (ev_date.replace(tzinfo=None) - now).total_seconds() / 86400)
        return 4.0 * math.exp(-days_until / 3.0)
    except (ValueError, TypeError):
        return 0.0


def _score_popularidad(ev_id: str, popularidad_map: dict) -> float:
    """Popularidad: log del número de interacciones de otros usuarios en 24h.

    Evita el problema de escala: un evento con 100 clicks no aplasta a uno con 5.
    """
    clicks_24h = popularidad_map.get(ev_id, 0)
    return min(3.0, math.log1p(clicks_24h))  # cap en 3


def _score_calidad(ev: dict) -> float:
    """Señales de calidad del evento: imagen, gratuito, verificado."""
    s = 0.0
    if ev.get("imagen_url"):
        s += 0.8
    if ev.get("es_gratuito"):
        s += 1.2
    if ev.get("verificado"):
        s += 1.5
    if ev.get("descripcion") and len(ev["descripcion"]) > 80:
        s += 0.5
    return s


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
    Ranking ML de eventos personalizados por usuario.

    score(e, u) = f_cat(e,u) + f_geo(e,u) + f_urgencia(e) + f_popularidad(e) + f_calidad(e)

    Cada feature tiene su propia función matemática:
    - f_cat: rank ordinal + log1p(raw_score) de interacciones con decaimiento exponencial (t½=14d)
    - f_geo: Haversine score = 5 * e^(-distancia_km / 5)
    - f_urgencia: 4 * e^(-días_hasta_evento / 3)
    - f_popularidad: log1p(clicks_24h de todos los usuarios), cap en 3
    - f_calidad: señales de completitud del evento
    """
    perfil = obtener_perfil(user_id)

    # ── 1. Construir vector de preferencias del usuario ───────────────────────
    cat_scores: Counter = Counter()
    barrio_scores: Counter = Counter()

    # 1a. Preferencias declaradas (señal fuerte, peso alto)
    if perfil and perfil.get("preferencias"):
        for cat in perfil["preferencias"]:
            cat_scores[cat] += 12.0

    # 1b. Interacciones recientes con decaimiento exponencial (t½ = 14 días)
    hace_90d = (datetime.utcnow() - timedelta(days=90)).isoformat()
    resp_inter = (
        supabase.table("interacciones_usuario")
        .select("item_id, categoria, tipo, created_at, metadata")
        .eq("user_id", user_id)
        .gte("created_at", hace_90d)
        .order("created_at", desc=True)
        .limit(300)
        .execute()
    )
    now = datetime.utcnow()
    # Pesos implícitos por tipo de acción (implicit feedback)
    TIPO_PESO = {"view_evento": 3, "view_espacio": 2, "click": 4, "share": 6, "chat_mention": 2, "asistir": 8}
    for inter in resp_inter.data:
        if not inter.get("categoria"):
            continue
        try:
            created = datetime.fromisoformat(inter["created_at"].replace("Z", "").replace("+00:00", ""))
            days_ago = max(0.0, (now - created).total_seconds() / 86400)
        except Exception:
            days_ago = 30.0
        decay = _exponential_time_decay(days_ago, half_life_days=14.0)
        peso = TIPO_PESO.get(inter.get("tipo", ""), 1)
        cat_scores[inter["categoria"]] += peso * decay
        meta = inter.get("metadata") or {}
        if meta.get("barrio"):
            barrio_scores[meta["barrio"]] += decay

    # 1c. Historial de búsquedas (señal débil pero consistente)
    resp_busq = (
        supabase.table("historial_busqueda")
        .select("categorias_resultado, created_at")
        .eq("user_id", user_id)
        .gte("created_at", hace_90d)
        .order("created_at", desc=True)
        .limit(60)
        .execute()
    )
    for busq in resp_busq.data:
        try:
            created = datetime.fromisoformat(busq["created_at"].replace("Z", "").replace("+00:00", ""))
            days_ago = max(0.0, (now - created).total_seconds() / 86400)
        except Exception:
            days_ago = 30.0
        decay = _exponential_time_decay(days_ago, half_life_days=21.0)
        for cat in (busq.get("categorias_resultado") or []):
            cat_scores[cat] += 1.0 * decay

    top_cats = [cat for cat, _ in cat_scores.most_common(10)]
    top_barrios = [b for b, _ in barrio_scores.most_common(5)]

    # Cold start: usuario nuevo sin historial
    if not top_cats:
        top_cats = ["teatro", "musica_en_vivo", "hip_hop", "danza", "jazz", "electronica", "taller"]

    # ── 2. Popularidad de eventos en las últimas 24h (señal global) ───────────
    hace_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    popularidad_map: dict = {}
    try:
        resp_pop = (
            supabase.table("interacciones_usuario")
            .select("item_id")
            .gte("created_at", hace_24h)
            .in_("tipo", ["view_evento", "click"])
            .limit(2000)
            .execute()
        )
        for row in resp_pop.data:
            eid = row.get("item_id")
            if eid:
                popularidad_map[eid] = popularidad_map.get(eid, 0) + 1
    except Exception:
        pass

    # ── 3. Candidatos de eventos ──────────────────────────────────────────────
    ahora = datetime.utcnow().isoformat()
    resp_all = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", ahora)
        .order("fecha_inicio")
        .limit(120)
        .execute()
    )

    resp_zona_data = []
    if perfil and perfil.get("municipio"):
        try:
            resp_zona = (
                supabase.table("eventos")
                .select("*")
                .gte("fecha_inicio", ahora)
                .eq("municipio", perfil["municipio"])
                .order("fecha_inicio")
                .limit(40)
                .execute()
            )
            resp_zona_data = resp_zona.data
        except Exception:
            pass

    # ── 4. Scoring por features ML ────────────────────────────────────────────
    interacted_ids = {r.get("item_id") for r in resp_inter.data if r.get("item_id")}
    seen_ids: set = set()
    scored_events = []

    all_events = resp_zona_data + resp_all.data
    for ev in all_events:
        eid = ev["id"]
        if eid in seen_ids:
            continue
        seen_ids.add(eid)

        cat = ev.get("categoria_principal", "")

        # f1: afinidad de categoría (rank + magnitud)
        f1 = _score_categoria_match(cat, top_cats, cat_scores)

        # f2: bonus si categorías adicionales del evento también son de interés
        extra_cats = ev.get("categorias") or []
        f1 += sum(0.5 for c in extra_cats if c in top_cats and c != cat)

        # f3: barrio visitado frecuentemente
        f_barrio = 2.0 if (ev.get("barrio") and ev["barrio"] in top_barrios) else 0.0

        # f4: proximidad geográfica Haversine
        f_geo = _score_proximidad(ev, perfil)

        # f5: urgencia temporal
        f_urgencia = _score_urgencia(ev, now)

        # f6: popularidad log1p (señal de otros usuarios)
        f_pop = _score_popularidad(eid, popularidad_map)

        # f7: calidad de datos del evento
        f_calidad = _score_calidad(ev)

        # f8: penalización leve por ya visto (no eliminar — la gente revisa)
        f_seen = -2.0 if eid in interacted_ids else 0.0

        score = f1 + f_barrio + f_geo + f_urgencia + f_pop + f_calidad + f_seen
        scored_events.append((score, ev))

    scored_events.sort(key=lambda x: x[0], reverse=True)

    # ── 5. Diversificación (no más de 3 del mismo género en top results) ──────
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


def obtener_eventos_zona_hoy(zona_id: int) -> dict:
    """Obtiene eventos próximos en una zona específica, con espacios."""
    resp_zona = (
        supabase.table("zonas_culturales")
        .select("*")
        .eq("id", zona_id)
        .single()
        .execute()
    )
    zona = resp_zona.data
    if not zona:
        return {"eventos": [], "espacios": [], "zona": None}

    municipio = zona.get("municipio", "medellin")

    from zoneinfo import ZoneInfo
    ahora_co = datetime.now(ZoneInfo("America/Bogota"))
    hoy = ahora_co.date().isoformat()
    catorce_dias = (ahora_co.date() + timedelta(days=14)).isoformat()

    # Buscar eventos usando ilike para ignorar mayúsculas/acentos
    resp = (
        supabase.table("eventos")
        .select("*")
        .ilike("municipio", f"%{municipio}%")
        .gte("fecha_inicio", hoy)
        .lte("fecha_inicio", catorce_dias)
        .neq("estado_moderacion", "rechazado")
        .order("fecha_inicio")
        .limit(50)
        .execute()
    )

    eventos = resp.data or []

    # Si no hay eventos con municipio, buscar sin filtro de municipio (fallback)
    if not eventos:
        resp_sin_filtro = (
            supabase.table("eventos")
            .select("*")
            .gte("fecha_inicio", hoy)
            .lte("fecha_inicio", catorce_dias)
            .neq("estado_moderacion", "rechazado")
            .order("fecha_inicio")
            .limit(20)
            .execute()
        )
        eventos = resp_sin_filtro.data or []

    # Espacios activos en ese municipio
    resp_espacios = (
        supabase.table("lugares")
        .select("id,nombre,slug,categoria_principal,barrio,descripcion_corta,instagram_handle,nivel_actividad")
        .ilike("municipio", f"%{municipio}%")
        .neq("nivel_actividad", "cerrado")
        .limit(20)
        .execute()
    )

    return {
        "eventos": eventos,
        "espacios": resp_espacios.data or [],
        "zona": zona,
    }
