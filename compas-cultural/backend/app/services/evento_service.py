"""
evento_service.py
=================
Servicio de consulta de eventos. Fixes aplicados en 2026-04:
- `get_eventos_semana()` cubre hasta el domingo de la PRÓXIMA semana
  (antes solo 7 días rolling → perdía viernes-sábado-domingo).
- Nueva función `get_eventos_proximas_semanas(dias)` para ventana extendida.
- `get_eventos()` acepta filtros robustos: colectivo_slug, texto, OR de categorías.
- Fix paginación Supabase (eliminado .limit() redundante tras .range()).
- Filtro municipio con fallback a nombre_lugar / barrio.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import supabase

CO_TZ = ZoneInfo("America/Bogota")


def _now_co() -> datetime:
    """Current time in Colombia (America/Bogota)."""
    return datetime.now(CO_TZ)


def _now_iso() -> str:
    return _now_co().isoformat()


def _today_iso() -> str:
    """ISO string for today midnight in Colombia, with tz offset preserved."""
    ahora = _now_co()
    return ahora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _sunday_of_next_week_iso() -> str:
    """Fin de semana próxima (domingo 23:59:59) en zona Colombia.
    
    Esto garantiza que 'esta semana' cubra:
    - Fin de semana actual (vie-sáb-dom)
    - Toda la semana próxima (lun-vie)
    - Fin de semana próximo (sáb-dom)
    Rango total: 7 a 14 días según día actual.
    """
    ahora = _now_co()
    # weekday(): 0=lun, 6=dom
    dias_a_domingo_esta_semana = 6 - ahora.weekday()
    fin = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
    fin = fin + timedelta(days=dias_a_domingo_esta_semana + 7)
    return fin.isoformat()


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _event_matches_municipio(ev: dict, municipio: Optional[str]) -> bool:
    if not municipio:
        return True
    muni = _normalize_text(municipio)
    fields = [
        _normalize_text(ev.get("municipio")),
        _normalize_text(ev.get("nombre_lugar")),
        _normalize_text(ev.get("barrio")),
    ]
    return any(muni and muni in f for f in fields)


def _event_matches_categoria(ev: dict, categoria: Optional[str]) -> bool:
    if not categoria:
        return True
    cat = _normalize_text(categoria).replace("_", " ")
    principal = _normalize_text(ev.get("categoria_principal")).replace("_", " ")
    cats = ev.get("categorias") or []
    cats_norm = [_normalize_text(c).replace("_", " ") for c in cats if isinstance(c, str)]
    return principal == cat or cat in cats_norm


def _event_matches_precio(ev: dict, es_gratuito: Optional[bool]) -> bool:
    if es_gratuito is None:
        return True
    return bool(ev.get("es_gratuito")) is es_gratuito


def _filter_events(
    eventos: List[dict],
    *,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    return [
        ev for ev in eventos
        if _event_matches_municipio(ev, municipio)
        and _event_matches_categoria(ev, categoria)
        and _event_matches_precio(ev, es_gratuito)
    ]


# ══════════════════════════════════════════════════════════════
# Listado con filtros
# ══════════════════════════════════════════════════════════════

def get_eventos(
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    colectivo_slug: Optional[str] = None,
    texto: Optional[str] = None,
) -> List[dict]:
    """
    Listar eventos futuros con filtros robustos.
    
    Filtros:
      - municipio: match exacto O fallback a nombre_lugar/barrio (ilike)
      - categoria: match en categoria_principal O en array categorias
      - colectivo_slug: resuelve slug → espacio_id
      - texto: búsqueda en titulo/descripcion/nombre_lugar
    """
    query = supabase.table("eventos").select("*").gte("fecha_inicio", _today_iso())

    if fecha_desde:
        query = query.gte("fecha_inicio", fecha_desde.isoformat())
    if fecha_hasta:
        query = query.lte("fecha_inicio", fecha_hasta.isoformat())

    if municipio:
        # Fallback robusto: si el evento no tiene municipio pero el nombre del lugar
        # o el barrio contiene el municipio, también entra.
        # Previene el bug "filtro municipio → 0 eventos" cuando scrapers olvidan llenar municipio.
        query = query.or_(
            f"municipio.eq.{municipio},"
            f"nombre_lugar.ilike.%{municipio}%,"
            f"barrio.ilike.%{municipio}%"
        )

    if barrio:
        query = query.ilike("barrio", f"%{barrio}%")

    if categoria:
        # Match en campo string principal O en array (heterogeneidad de scrapers)
        query = query.or_(
            f"categoria_principal.eq.{categoria},"
            f"categorias.cs.{{{categoria}}}"
        )

    if es_gratuito is not None:
        query = query.eq("es_gratuito", es_gratuito)

    if colectivo_slug:
        # Resolver slug → espacio_id. Si no existe, devolver lista vacía.
        try:
            lugar_resp = (
                supabase.table("lugares")
                .select("id")
                .eq("slug", colectivo_slug)
                .execute()
            )
            if lugar_resp.data:
                query = query.eq("espacio_id", lugar_resp.data[0]["id"])
            else:
                return []
        except Exception:
            return []

    if texto:
        texto_clean = texto.replace(",", " ").strip()[:100]
        if texto_clean:
            query = query.or_(
                f"titulo.ilike.%{texto_clean}%,"
                f"descripcion.ilike.%{texto_clean}%,"
                f"nombre_lugar.ilike.%{texto_clean}%"
            )

    # FIX: Supabase PostgREST — usar range() SIN limit() adicional.
    # El .limit() tras .range() rompía paginación en supabase-py.
    response = (
        query.order("fecha_inicio")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data or []


# ══════════════════════════════════════════════════════════════
# Vistas temporales
# ══════════════════════════════════════════════════════════════

def get_eventos_hoy(
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Eventos que ocurren HOY (inician hoy o en curso multi-día)."""
    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    hoy_iso = hoy_inicio.isoformat()
    manana_iso = hoy_fin.isoformat()

    # Events that START today
    q_inicio = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy_iso)
        .lt("fecha_inicio", manana_iso)
    )
    resp_inicio = q_inicio.order("fecha_inicio").execute()
    eventos = resp_inicio.data or []

    # Multi-day events that started before today but end today or later
    q_en_curso = (
        supabase.table("eventos")
        .select("*")
        .lt("fecha_inicio", hoy_iso)
        .gte("fecha_fin", hoy_iso)
    )
    resp_en_curso = q_en_curso.order("fecha_inicio").execute()
    seen_ids = {e["id"] for e in eventos}
    for ev in (resp_en_curso.data or []):
        if ev["id"] not in seen_ids:
            ev["_en_curso"] = True
            eventos.append(ev)
            seen_ids.add(ev["id"])

    return _filter_events(
        eventos,
        municipio=municipio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )


def get_eventos_semana(
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Eventos desde hoy hasta el domingo de la PRÓXIMA semana.
    
    Cobertura total: 7–14 días (antes era 7 días rolling, lo que dejaba 
    fuera vie-sáb-dom cuando se consultaba en miércoles-jueves).
    """
    ahora = _now_co().replace(hour=0, minute=0, second=0, microsecond=0)
    fin = datetime.fromisoformat(_sunday_of_next_week_iso())
    return get_eventos(
        fecha_desde=ahora,
        fecha_hasta=fin,
        municipio=municipio,
        categoria=categoria,
        es_gratuito=es_gratuito,
        limit=500,
        offset=0,
    )


def get_eventos_proximas_semanas(
    dias: int = 21,
    municipio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Ventana extendida: eventos desde hoy hasta N días en el futuro (default 21)."""
    if dias < 1:
        dias = 1
    if dias > 90:
        dias = 90

    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = hoy_inicio + timedelta(days=dias)
    return get_eventos(
        fecha_desde=hoy_inicio,
        fecha_hasta=fin,
        municipio=municipio,
        categoria=categoria,
        es_gratuito=es_gratuito,
        limit=500,
        offset=0,
    )


# ══════════════════════════════════════════════════════════════
# Consulta individual
# ══════════════════════════════════════════════════════════════

def get_evento_by_slug(slug: str) -> dict:
    response = (
        supabase.table("eventos")
        .select("*")
        .eq("slug", slug)
        .single()
        .execute()
    )
    return response.data


def get_eventos_by_espacio(espacio_id: str, limit: int = 10) -> List[dict]:
    """Eventos futuros + en curso de un espacio específico."""
    hoy_iso = _today_iso()
    response = (
        supabase.table("eventos")
        .select("*")
        .eq("espacio_id", espacio_id)
        .gte("fecha_inicio", hoy_iso)
        .order("fecha_inicio")
        .limit(limit)
        .execute()
    )
    eventos = response.data or []

    resp_en_curso = (
        supabase.table("eventos")
        .select("*")
        .eq("espacio_id", espacio_id)
        .lt("fecha_inicio", hoy_iso)
        .gte("fecha_fin", hoy_iso)
        .order("fecha_inicio")
        .execute()
    )
    seen_ids = {e["id"] for e in eventos}
    for ev in (resp_en_curso.data or []):
        if ev["id"] not in seen_ids:
            ev["_en_curso"] = True
            eventos.insert(0, ev)
            seen_ids.add(ev["id"])

    return eventos


# ══════════════════════════════════════════════════════════════
# Feed diverso
# ══════════════════════════════════════════════════════════════

def get_eventos_feed(limit: int = 20) -> List[dict]:
    """
    Smart feed: diverse mix of upcoming events across all categories.
    Ensures variety by limiting max events per category and shuffling.
    Shows a mix of free/paid, different municipios, and different categories.
    Used for non-logged-in users and the general home feed.
    """
    from collections import Counter
    import random

    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    proxima_semana = hoy_inicio + timedelta(days=14)

    response = (
        supabase.table("eventos")
        .select("*")
        .gte("fecha_inicio", hoy_inicio.isoformat())
        .lte("fecha_inicio", proxima_semana.isoformat())
        .order("fecha_inicio")
        .limit(200)
        .execute()
    )
    pool = response.data or []
    if not pool:
        response = (
            supabase.table("eventos")
            .select("*")
            .gte("fecha_inicio", _now_iso())
            .order("fecha_inicio")
            .limit(30)
            .execute()
        )
        pool = response.data or []

    if len(pool) <= limit:
        return pool

    cat_count: Counter = Counter()
    muni_count: Counter = Counter()
    result = []

    with_img = [e for e in pool if e.get("imagen_url")]
    without_img = [e for e in pool if not e.get("imagen_url")]

    random.shuffle(with_img)
    random.shuffle(without_img)

    candidates = with_img + without_img

    for ev in candidates:
        cat = ev.get("categoria_principal", "otro")
        muni = ev.get("municipio", "medellin")

        if cat_count[cat] >= 3:
            continue
        if muni_count[muni] >= 6 and len(muni_count) > 1:
            continue

        cat_count[cat] += 1
        muni_count[muni] += 1
        result.append(ev)

        if len(result) >= limit:
            break

    result.sort(key=lambda e: e.get("fecha_inicio", ""))
    return result
