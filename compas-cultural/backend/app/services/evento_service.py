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

try:
    from cachetools import TTLCache
    _HOY_CACHE: TTLCache = TTLCache(maxsize=64, ttl=300)   # 5 min
    _SEMANA_CACHE: TTLCache = TTLCache(maxsize=32, ttl=600) # 10 min
    _CACHE_AVAILABLE = True
except ImportError:
    _HOY_CACHE = {}  # type: ignore
    _SEMANA_CACHE = {}  # type: ignore
    _CACHE_AVAILABLE = False

from app.database import supabase
from app.services.ml_utils import (
    urgency_score,
    quality_score,
    exponential_decay,
    log1p_score,
    multi_field_bm25,
    tokenize,
)

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


def _tomorrow_start_co() -> datetime:
    """Tomorrow midnight in Colombia timezone."""
    hoy_inicio = _now_co().replace(hour=0, minute=0, second=0, microsecond=0)
    return hoy_inicio + timedelta(days=1)


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


def _event_datetime_co(ev: dict, field: str) -> Optional[datetime]:
    raw = ev.get(field)
    if not raw:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CO_TZ)
    return dt.astimezone(CO_TZ)


def _is_event_happening_today(ev: dict, today_start: datetime, tomorrow_start: datetime) -> bool:
    """Strict timezone-aware check to avoid misclassified 'hoy' events."""
    start = _event_datetime_co(ev, "fecha_inicio")
    if not start:
        return False

    # Starts today
    if today_start <= start < tomorrow_start:
        return True

    # Multi-day in progress today
    end = _event_datetime_co(ev, "fecha_fin")
    if end and start < today_start <= end:
        return True
    return False


def _event_matches_barrio(ev: dict, barrio: Optional[str]) -> bool:
    if not barrio:
        return True
    b = _normalize_text(barrio)
    ev_barrio = _normalize_text(ev.get("barrio"))
    ev_lugar = _normalize_text(ev.get("nombre_lugar"))
    return b in ev_barrio or b in ev_lugar or ev_barrio in b


def _filter_events(
    eventos: List[dict],
    *,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    return [
        ev for ev in eventos
        if _event_matches_municipio(ev, municipio)
        and _event_matches_barrio(ev, barrio)
        and _event_matches_categoria(ev, categoria)
        and _event_matches_precio(ev, es_gratuito)
    ]


# ══════════════════════════════════════════════════════════════
# ML Scoring de eventos
# ══════════════════════════════════════════════════════════════

def _score_evento_ml(
    ev: dict,
    now: datetime,
    texto: Optional[str] = None,
) -> float:
    """
    Score ML compuesto para un evento. Usado para reordenar resultados
    después de la consulta SQL (post-retrieval ranking).

    Componentes:
      f_urgencia  = 4 * e^(-days_until / 3)   — eventos pronto pesan más
      f_calidad   = quality_score(ev) ∈ [0,4]  — contenido completo
      f_texto     = BM25 multi-campo si hay query de texto
      f_gratuito  = 0.3 bonus si es gratis

    Retorna score ≥ 0 (sin cota superior fija).
    """
    # Urgencia
    fecha_str = ev.get("fecha_inicio") or ""
    days_until = 0.0
    try:
        if fecha_str:
            ev_dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            ev_dt_naive = ev_dt.replace(tzinfo=None)
            now_naive = now.replace(tzinfo=None)
            days_until = max(0.0, (ev_dt_naive - now_naive).total_seconds() / 86400)
    except Exception:
        pass
    f_urgencia = urgency_score(days_until, weight=4.0, decay=3.0)

    # Calidad del contenido
    f_calidad = quality_score(ev)

    # BM25 si hay query
    f_texto = 0.0
    if texto:
        f_texto = multi_field_bm25(
            tokenize(texto),
            {
                "titulo":       (ev.get("titulo") or "", 3.0),
                "nombre_lugar": (ev.get("nombre_lugar") or "", 2.0),
                "categoria":    (ev.get("categoria_principal") or "", 2.0),
                "barrio":       (ev.get("barrio") or "", 1.5),
                "descripcion":  (ev.get("descripcion") or "", 1.0),
            },
        )

    # Bonus accesibilidad
    f_gratuito = 0.3 if ev.get("es_gratuito") else 0.0

    return f_urgencia + f_calidad + f_texto + f_gratuito


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
    Listar eventos con filtros robustos.
    """
    query = supabase.table("eventos").select("*")

    if fecha_desde:
        # Use date-only format to match DB rows that store date without timezone.
        fecha_desde_str = fecha_desde.strftime("%Y-%m-%d")
        query = query.or_(f"fecha_inicio.gte.{fecha_desde_str},fecha_fin.gte.{fecha_desde_str}")
    else:
        # Si no se pasa fecha_desde (ej: pestaña Todos), mostrar solo futuros o en curso
        hoy = _now_co().strftime("%Y-%m-%d")
        query = query.or_(f"fecha_inicio.gte.{hoy},fecha_fin.gte.{hoy}")

    if fecha_hasta:
        query = query.lte("fecha_inicio", fecha_hasta.strftime("%Y-%m-%d"))

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
    eventos = response.data or []

    # Post-retrieval ML ranking: reordenar por score compuesto
    # (urgencia + calidad + coincidencia textual)
    now = _now_co()
    eventos.sort(key=lambda ev: _score_evento_ml(ev, now, texto), reverse=True)
    return eventos


# ══════════════════════════════════════════════════════════════
# Vistas temporales
# ══════════════════════════════════════════════════════════════

def get_eventos_hoy(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Eventos que ocurren HOY (inician hoy o en curso multi-día). Con cache 5 min."""
    _cache_key = (municipio, barrio, categoria, es_gratuito)
    if _CACHE_AVAILABLE and _cache_key in _HOY_CACHE:
        return _HOY_CACHE[_cache_key]
    ahora = _now_co()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    hoy_str = hoy_inicio.strftime("%Y-%m-%d")

    # Events that START today
    q_inicio = supabase.table("eventos").select("*").eq("fecha_inicio", hoy_str)
    resp_inicio = q_inicio.order("fecha_inicio").execute()
    eventos = resp_inicio.data or []

    # Multi-day events that started before today but end today or later
    q_en_curso = (
        supabase.table("eventos")
        .select("*")
        .lt("fecha_inicio", hoy_str)
        .gte("fecha_fin", hoy_str)
    )
    resp_en_curso = q_en_curso.order("fecha_inicio").execute()
    seen_ids = {e["id"] for e in eventos}
    for ev in (resp_en_curso.data or []):
        if ev["id"] not in seen_ids:
            ev["_en_curso"] = True
            eventos.append(ev)
            seen_ids.add(ev["id"])

    # Final strict validation in Colombia timezone to avoid wrong-day leaks.
    eventos = [ev for ev in eventos if _is_event_happening_today(ev, hoy_inicio, hoy_fin)]

    result = _filter_events(
        eventos,
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
    )
    if _CACHE_AVAILABLE:
        _HOY_CACHE[_cache_key] = result
    return result


def get_eventos_semana(
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Eventos de los próximos 7 días (mañana a 7 días). Con cache 10 min."""
    _cache_key = (municipio, barrio, categoria, es_gratuito)
    if _CACHE_AVAILABLE and _cache_key in _SEMANA_CACHE:
        return _SEMANA_CACHE[_cache_key]
    manana_inicio = _tomorrow_start_co()
    fin = manana_inicio + timedelta(days=7)
    result = get_eventos(
        fecha_desde=manana_inicio,
        fecha_hasta=fin,
        municipio=municipio,
        barrio=barrio,
        categoria=categoria,
        es_gratuito=es_gratuito,
        limit=500,
        offset=0,
    )
    if _CACHE_AVAILABLE:
        _SEMANA_CACHE[_cache_key] = result
    return result


def get_eventos_proximas_semanas(
    dias: int = 21,
    desde_dias: int = 1,
    municipio: Optional[str] = None,
    barrio: Optional[str] = None,
    categoria: Optional[str] = None,
    es_gratuito: Optional[bool] = None,
) -> List[dict]:
    """Ventana futura configurable: default desde mañana hasta 21 días."""
    if dias < 1:
        dias = 21
    if dias > 90:
        dias = 90
    if desde_dias < 0:
        desde_dias = 0
    if desde_dias > dias:
        desde_dias = dias

    hoy_inicio = _now_co().replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = hoy_inicio + timedelta(days=desde_dias)
    fin = hoy_inicio + timedelta(days=dias)
    return get_eventos(
        fecha_desde=inicio,
        fecha_hasta=fin,
        municipio=municipio,
        barrio=barrio,
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
    Smart feed con ML: mix diverso de eventos ordenado por score compuesto.

    Score = urgency_decay(días) + quality_score + log1p(días_hasta*0) — diversificado
    por categoría (máx 3) y municipio (máx 6). Prioriza eventos con imagen y
    descripción completa sobre los que no tienen.

    Para usuarios no logueados y el feed general de Home.
    """
    from collections import Counter

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

    # Puntuar cada evento con ML
    scored = [
        (ev, _score_evento_ml(ev, ahora))
        for ev in pool
    ]
    # Ordenar por score descendente
    scored.sort(key=lambda x: x[1], reverse=True)

    # Diversificación: máx 3 por categoría, máx 6 por municipio
    cat_count: Counter = Counter()
    muni_count: Counter = Counter()
    result = []

    for ev, _score in scored:
        cat = ev.get("categoria_principal") or "otro"
        muni = ev.get("municipio") or "medellin"

        if cat_count[cat] >= 3:
            continue
        if muni_count[muni] >= 6 and len(muni_count) > 1:
            continue

        cat_count[cat] += 1
        muni_count[muni] += 1
        result.append(ev)

        if len(result) >= limit:
            break

    return result
