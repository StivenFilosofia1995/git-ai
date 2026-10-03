"""
event_gate.py — Puerta de calidad DETERMINISTA para todo evento que entra al sistema.

Ningún scraper escribe directo en `eventos`: todos llaman `insertar_evento()`.
Cero LLM. Reglas explícitas, testeables y auditables (motivos en cada decisión).

Decisiones:
- publicar    → se inserta visible.
- cuarentena  → se inserta con oculto=True (el admin lo aprueba o lo borra).
- rechazar    → no se inserta (basura evidente: menú web, fecha imposible, otro país…).
- duplicado   → no se inserta; si trae datos que faltaban (imagen, hora), se completan
                en el evento existente.

La misma lógica se aplica hacia atrás con `revisar_calidad_eventos()` (job nocturno):
oculta (no borra) lo que no pasa la puerta, limpia títulos/descripciones y fusiona
duplicados. Todo lo que oculta queda marcado con `oculto_motivo = 'gate:...'`
para poder revertirlo con un UPDATE.
"""
from __future__ import annotations

import re
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

CO_TZ = ZoneInfo("America/Bogota")

# ─── Vocabularios ──────────────────────────────────────────────────────────

# Títulos que son navegación de un sitio web, no eventos
_NAV_TITLE_RE = re.compile(
    r"^(inicio|home|noticias|nosotros|quienes somos|contacto|contactenos|normatividad|transparencia|"
    r"tramites( y servicios)?|pqrs?d?|servicios|agenda|eventos|calendario|programacion|"
    r"mapa del sitio|iniciar sesion|registrate|politica de .*|terminos y condiciones|"
    r"(municipio|alcaldia|gobernacion|secretaria) de [a-z ]+|ver mas|leer mas|mas informacion|"
    r"compra(r)? (tu )?(ticket|boleta)s?|boleteria|suscribete|newsletter|galeria|blog)$"
)

# Frases de menú que aparecen pegadas en descripciones (p. ej. Bibliotecas MDE)
_MENU_TERMS = [
    "quienes somos", "directorio administrativo", "documentos institucionales", "premios y reconocimientos",
    "plan estrategico", "estudio de valor", "memorias eventos academicos", "unidades de informacion",
    "comite interinstitucional", "nuestros servicios", "afiliate", "catalogos", "renovar o reservar",
    "prestamo de espacios", "biblioteca digital", "conoce nuestras bibliotecas", "servicio de informacion local",
    "contactenos", "atencion pqrs", "preguntas frecuentes", "mapa del sitio", "politica de privacidad",
    "terminos y condiciones", "iniciar sesion", "normatividad", "transparencia y acceso", "tramites y servicios",
]

_MENU_EXTRA = ["plan estrategico 2022-2026", "nosotros", "exposiciones", "planos", "estadistica",
               "bibliolabs", "pcleo", "clubes de lectura y talleres de escritura", "memorias eventos academicos",
               "comite interinstitucional de bibliotecas", "unidades de informacion", "renovar o reservar tu libro"]
_VOCALES = {"a": "[aáà]", "e": "[eéè]", "i": "[iíì]", "o": "[oóò]", "u": "[uúüù]", "n": "[nñ]"}


def _sin_tildes_re(term: str) -> str:
    """Regex que encuentra `term` con o sin tildes ("estrategico" ↔ "estratégico")."""
    return r"(?<!\w)" + "".join(_VOCALES.get(ch, re.escape(ch)) for ch in term) + r"(?!\w)"


# Plantillas genéricas sin nombre propio ("Festival de Danza", "Charla sobre Poesía")
_GENEROS = (
    r"(danza|poesia|fotografia|cine|teatro|musica( electronica| en vivo| clasica)?|jazz|rock|arte( urbano| contemporaneo)?|"
    r"literatura|pintura|escritura|lectura|electronica|hip hop|rap|circo|escultura|ceramica|grabado|ilustracion|"
    r"dibujo|salsa|tango|folclor|narracion oral|cuento|libros?|filosofia|historia|cultura|artes?)"
)
_GENERIC_TITLE_RE = re.compile(
    r"^(gran |el |la |un |una )?(charla|festival|exposicion|taller|concierto|muestra|conferencia|feria|encuentro|"
    r"ciclo|noche|jornada|clase|curso|evento|presentacion|recital|conversatorio|lectura|proyeccion|show)"
    r"( de| sobre| del)?( la| el| los| las)? " + _GENEROS + r"$"
)

# Marcadores donde un título "pegado" del HTML debe cortarse
_TITLE_CUT_RE = re.compile(
    r"\s*(\||compra tu|comprar|boletas?:|entradas?:|hora:|pulep|primera etapa|precio:|\$\s?\d|"
    r"mas informacion|más información|ver mas|ver más|leer mas|leer más|#)",
    re.IGNORECASE,
)
_LEADING_DATE_RE = re.compile(
    r"^((lun|mar|mi[eé]|jue|vie|s[aá]b|dom)[a-záéíóú]*\.?\s+\d{1,2}\s+"
    r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\.?\s+)"
    r"((lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+)?",
    re.IGNORECASE,
)

# Vocabulario cultural inequívoco en el título: basta para no dudar del evento
_TERMINO_CULTURAL_RE = re.compile(
    r"\b(festival|concierto|recital|obra|teatro|funcion|estreno|danza|ballet|opera|exposicion|muestra|"
    r"taller|conversatorio|charla|cine|proyeccion|jazz|rock|hip hop|rap|salsa|tango|flamenco|poesia|"
    r"lectura|club de|feria del libro|lanzamiento|circo|stand ?up|impro|tablao|orquesta|filarmonica|coro)\b"
)

_CANCELADO_RE = re.compile(r"(^|[\s(\[])(cancelad[oa]|aplazad[oa]|suspendid[oa])([\s)\]:.,-]|$)")

# Ciudades fuera del Valle de Aburrá que delatan eventos ajenos
_FUERA_RE = re.compile(
    r"\b(charlotte|miami|new york|nueva york|los angeles|madrid|barcelona|buenos aires|ciudad de mexico|"
    r"quito|lima|santiago de chile|bogota|cali|cartagena|barranquilla|bucaramanga|pereira|manizales|"
    r"armenia|cucuta|santa marta|ibague|pasto|villavicencio|monteria|popayan|tunja|neiva)\b"
)
_VALLE_RE = re.compile(
    r"\b(medellin|envigado|itagui|bello|sabaneta|la estrella|caldas|copacabana|girardota|barbosa|"
    r"valle de aburra|antioquia|poblado|laureles|belen|robledo|san javier|santa elena|san antonio de prado)\b"
)
VALLE_BBOX = (5.95, 6.55, -75.75, -75.25)  # lat_min, lat_max, lng_min, lng_max

_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_FECHA_TEXTO_RE = re.compile(
    r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s*,?\s+(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b"
)

_STOP = {"de", "del", "la", "el", "los", "las", "y", "en", "a", "con", "para", "por", "un", "una", "al",
         "medellin", "evento", "presenta", "invita", "the"}

# Confianza por fuente (prefijo). Las estructuradas (APIs/JSON) casi no fallan.
_FUENTES_ALTA = ("worker_compas_urbano", "compas_urbano", "bibliotecas_mde", "comfama", "fundacion_epm",
                 "uva_epm", "parque_deseos", "planetario", "medata", "ticketmaster", "eventbrite", "bandsintown",
                 "admin", "manual")
_FUENTES_BAJA = ("auto_scraper_sitio_web", "auto_scraper_web", "precision_web", "web_", "google_",
                 "smart_listener", "discover", "fallback", "rss_", "scraper_llm", "social_listener_fb")


def _norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: Optional[str]) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(s)) if len(t) > 2 and t not in _STOP}


def confianza_fuente(fuente: Optional[str]) -> str:
    f = (fuente or "").lower()
    if f.startswith(_FUENTES_ALTA):
        return "alta"
    if f.startswith(_FUENTES_BAJA):
        return "baja"
    return "media"  # instagram, agendas de espacios, publicación de usuarios


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CO_TZ)
    return dt.astimezone(CO_TZ)


# ─── Limpieza ──────────────────────────────────────────────────────────────

def limpiar_titulo(titulo: Optional[str]) -> str:
    t = re.sub(r"\s+", " ", (titulo or "")).strip(" \t\n-–—:·|•\"'“”")
    t = _LEADING_DATE_RE.sub("", t).strip()
    m = _TITLE_CUT_RE.search(t)
    if m and m.start() >= 8:
        t = t[: m.start()].strip(" -–—:·|•")
    if len(t) > 90:
        # Primera frase / línea de un caption de Instagram
        corte = re.search(r"[.!?¡¿\n]", t[20:])
        if corte and 20 + corte.start() <= 90:
            t = t[: 20 + corte.start()].strip()
        else:
            t = t[:88].rsplit(" ", 1)[0].rstrip(",;:-–") + "…"
    return t.strip(" -–—:·|•\"'“”")


def es_texto_menu(texto: Optional[str]) -> bool:
    """True si el texto es navegación de un sitio (≥2 frases típicas de menú)."""
    tn = _norm(texto)
    return sum(1 for term in _MENU_TERMS if term in tn) >= 2


def es_prosa(texto: Optional[str]) -> bool:
    """Texto que parece una descripción escrita: ≥ 8 palabras y puntuación de oración."""
    t = (texto or "").strip()
    return len(t.split()) >= 8 and bool(re.search(r"[.!?¡¿,]", t)) and not es_texto_menu(t)


def limpiar_descripcion(desc: Optional[str]) -> Optional[str]:
    if not desc:
        return desc
    d = re.sub(r"\s+", " ", desc).strip()
    dn = _norm(d)
    hits = sum(1 for term in _MENU_TERMS if term in dn)
    if hits >= 3:
        # Quitar las frases de menú y ver si queda prosa real
        limpio = d
        for term in sorted(_MENU_TERMS + _MENU_EXTRA, key=len, reverse=True):
            limpio = re.sub(_sin_tildes_re(term), " ", limpio, flags=re.IGNORECASE)
        limpio = re.sub(r"\s+", " ", limpio).strip()
        oraciones = [o for o in re.split(r"(?<=[.!?])\s+", limpio) if len(o) > 40 and o.count(" ") > 6]
        return " ".join(oraciones)[:1500] if oraciones else None
    return d[:3000]


# ─── Reglas ───────────────────────────────────────────────────────────────

def anio_publicacion_antigua(texto: str, fecha: datetime, ahora: datetime) -> Optional[int]:
    """Si el texto dice 'sábado 30 de septiembre' y eso NO cae en sábado en el año del evento,
    devuelve el año (pasado) en que sí cae. Indica un post viejo con el año mal inferido."""
    for dia_txt, dnum, mes_txt in _FECHA_TEXTO_RE.findall(_norm(texto)):
        try:
            d, m = int(dnum), _MESES[mes_txt]
        except Exception:
            continue
        if (d, m) != (fecha.day, fecha.month):
            continue
        wd = _DIAS[dia_txt]
        try:
            if date(fecha.year, m, d).weekday() == wd:
                return None  # consistente
        except ValueError:
            continue
        for y in range(ahora.year, ahora.year - 6, -1):
            try:
                if date(y, m, d).weekday() == wd:
                    return y if y < fecha.year else None
            except ValueError:
                continue
    return None


@dataclass
class Evaluacion:
    decision: str                       # publicar | cuarentena | rechazar | duplicado
    motivos: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    duplicado_de: Optional[str] = None


def evaluar_evento(ev: dict, *, ahora: Optional[datetime] = None) -> Evaluacion:
    """Evalúa (y limpia) un evento. Función pura: no toca la base de datos."""
    ahora = ahora or datetime.now(CO_TZ)
    p = dict(ev)
    motivos: list[str] = []
    rechazos: list[str] = []
    fuente = p.get("fuente") or ""
    conf = confianza_fuente(fuente)

    titulo_orig = p.get("titulo") or ""
    p["titulo"] = limpiar_titulo(titulo_orig)
    if p["titulo"] != titulo_orig.strip():
        motivos.append("titulo_limpiado")
    if "descripcion" in p:
        desc = limpiar_descripcion(p.get("descripcion"))
        if desc != p.get("descripcion"):
            motivos.append("descripcion_limpiada")
        p["descripcion"] = desc

    tn = _norm(p["titulo"])
    if len(tn) < 4:
        rechazos.append("titulo_vacio")
    if _NAV_TITLE_RE.match(tn):
        rechazos.append("titulo_es_menu_web")
    if _CANCELADO_RE.search(tn):
        rechazos.append("cancelado")
    if conf != "alta" and _GENERIC_TITLE_RE.match(tn):
        rechazos.append("titulo_plantilla_generica")

    ini = _parse_dt(p.get("fecha_inicio"))
    fin = _parse_dt(p.get("fecha_fin"))
    hoy0 = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    if not ini:
        rechazos.append("sin_fecha")
    else:
        if fin and (fin < ini or fin > ini + timedelta(days=370)):
            p["fecha_fin"] = None
            fin = None
            motivos.append("fecha_fin_saneada")
        if fin and fin < ahora:
            rechazos.append("ya_termino")
        elif not fin and ini < hoy0:
            rechazos.append("fecha_pasada")
        if ini > ahora + timedelta(days=365):
            rechazos.append("fecha_muy_lejana")
        texto = f"{titulo_orig} {ev.get('descripcion') or ''}"
        y = anio_publicacion_antigua(texto, ini, ahora)
        if y:
            rechazos.append(f"publicacion_antigua_{y}")

    # Geografía
    lat, lng = p.get("lat"), p.get("lng")
    if lat is not None and lng is not None:
        try:
            la, ln = float(lat), float(lng)
            if not (VALLE_BBOX[0] <= la <= VALLE_BBOX[1] and VALLE_BBOX[2] <= ln <= VALLE_BBOX[3]):
                rechazos.append("coordenadas_fuera_del_valle")
        except (TypeError, ValueError):
            p["lat"] = p["lng"] = None
    cabecera = _norm(f"{p['titulo']} {(p.get('descripcion') or '')[:250]} {p.get('nombre_lugar') or ''}")
    # Otra ciudad en el TÍTULO es evidencia fuerte (aunque tenga espacio mal asociado);
    # en la descripción solo cuenta si el evento no tiene espacio del Valle.
    if _FUERA_RE.search(tn) and not _VALLE_RE.search(tn):
        rechazos.append("otra_ciudad")
    elif _FUERA_RE.search(cabecera) and not _VALLE_RE.search(cabecera) and not p.get("espacio_id"):
        rechazos.append("otra_ciudad")

    _reglas_legado(p, ev, ini, ahora, motivos, rechazos)

    # "Design House 2025" visible en 2026: el título solo nombra años pasados → probable
    # evento del año anterior con fechas mal leídas. Lo revisa una persona.
    anios = [int(a) for a in re.findall(r"(?<!\d)(20\d{2})(?!\d)", titulo_orig or "")]
    if anios and max(anios) < ahora.year:
        motivos.append("titulo_anio_pasado")

    if rechazos:
        return Evaluacion("rechazar", rechazos + motivos, p)

    # Cuarentena: dudas razonables → lo decide una persona
    sin_lugar = not (p.get("espacio_id") or p.get("nombre_lugar") or p.get("lat"))
    if conf == "baja" and sin_lugar:
        motivos.append("fuente_baja_sin_lugar")
    if titulo_orig and len(titulo_orig) > 160 and conf == "baja":
        motivos.append("titulo_era_bloque_de_texto")
    if conf == "baja" and not _TERMINO_CULTURAL_RE.search(tn):
        try:
            from app.services.data_quality import is_likely_cultural_event
            if not is_likely_cultural_event(p["titulo"], p.get("descripcion"), fuente_url=p.get("fuente_url"),
                                            categoria=p.get("categoria_principal")):
                motivos.append("no_parece_evento_cultural")
        except Exception:
            pass
    dudosos = {"fuente_baja_sin_lugar", "titulo_era_bloque_de_texto", "no_parece_evento_cultural",
               "ig_fecha_dudosa", "titulo_anio_pasado"}
    if dudosos & set(motivos):
        return Evaluacion("cuarentena", motivos, p)
    return Evaluacion("publicar", motivos, p)


# ─── Eventos heredados de extractores viejos ───────────────────────────────
_FUENTE_LLM = re.compile(r"(groq|ollama|gemini|llm|_ai\b|claude)")
_FUENTE_IG = ("auto_scraper_instagram", "instagram", "smart_listener", "social_listener", "runner_ig")


def _reglas_legado(p: dict, ev: dict, ini, ahora, motivos: list, rechazos: list) -> None:
    """Datos que produjeron extractores anteriores (LLM o el extractor IG viejo)."""
    fuente = (p.get("fuente") or "").lower()
    if _FUENTE_LLM.search(fuente):
        rechazos.append("generado_por_llm")
        return
    if not fuente.startswith(_FUENTE_IG) or p.get("evidencia"):
        return  # con evidencia = ya pasó por ig_precision
    from app.services.ig_precision import _FUERA, _NO_EVENTO, _VALLE, _norm as _n
    texto = _n(f"{ev.get('titulo') or ''} {ev.get('descripcion') or ''}")
    m = _NO_EVENTO.search(texto)
    if m:
        rechazos.append(f"ig_no_es_evento:{m.group(0)}")
    m = _FUERA.search(texto)
    if m and not _VALLE.search(texto):
        rechazos.append(f"ig_otra_ciudad:{m.group(0)}")
    # Hora inventada por el extractor viejo
    desc = (ev.get("descripcion") or "")
    if p.get("hora_confirmada") and ini is not None:
        dia_como_hora = re.search(rf"\b{ini.hour}\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
                                  rf"septiembre|octubre|noviembre|diciembre)", texto)
        if "(estimada)" in desc.lower() or dia_como_hora:
            p["hora_confirmada"] = False
            motivos.append("ig_hora_inventada")
    if desc.lower().startswith("hora del evento"):
        p["descripcion"] = re.sub(r"^hora del evento[^.]*\.\s*", "", desc, flags=re.I) or None
        motivos.append("ig_prefijo_hora_quitado")
    if ini is not None and ini > ahora + timedelta(days=120):
        motivos.append("ig_fecha_dudosa")


# ─── Duplicados ────────────────────────────────────────────────────────────

def _misma_funcion(a: dict, b: dict) -> bool:
    """Mismo evento: mismo día (Bogotá), título casi igual y mismo lugar.
    Dos funciones a horas distintas confirmadas NO son duplicado."""
    da, db = _parse_dt(a.get("fecha_inicio")), _parse_dt(b.get("fecha_inicio"))
    if not da or not db or da.date() != db.date():
        return False
    if a.get("espacio_id") and b.get("espacio_id") and a["espacio_id"] != b["espacio_id"]:
        return False
    la, lb = _tokens(a.get("nombre_lugar")), _tokens(b.get("nombre_lugar"))
    if la and lb and not (la & lb) and not (a.get("espacio_id") and a.get("espacio_id") == b.get("espacio_id")):
        return False
    if a.get("hora_confirmada") and b.get("hora_confirmada") and abs((da - db).total_seconds()) >= 3600:
        return False
    ta, tb = _tokens(a.get("titulo")), _tokens(b.get("titulo"))
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    return inter >= 2 and inter / min(len(ta), len(tb)) >= 0.6 or ta == tb


def _calidad(ev: dict) -> tuple:
    """Para elegir cuál copia conservar al fusionar duplicados."""
    rank = {"alta": 2, "media": 1, "baja": 0}[confianza_fuente(ev.get("fuente"))]
    return (rank, bool(ev.get("espacio_id")), bool(ev.get("hora_confirmada")), bool(ev.get("imagen_url")),
            len(ev.get("descripcion") or ""), -len(ev.get("titulo") or ""))


def _completar_desde(dest: dict, src: dict) -> dict:
    """Campos que el duplicado aporta al evento que se conserva."""
    upd: dict = {}
    if not dest.get("imagen_url") and src.get("imagen_url"):
        upd["imagen_url"] = src["imagen_url"]
    if not dest.get("hora_confirmada") and src.get("hora_confirmada") and src.get("fecha_inicio"):
        upd["fecha_inicio"] = src["fecha_inicio"]
        upd["hora_confirmada"] = True
    if len(dest.get("descripcion") or "") < 40 and len(src.get("descripcion") or "") > 80:
        upd["descripcion"] = src["descripcion"]
    for k in ("espacio_id", "nombre_lugar", "lat", "lng", "precio"):
        if dest.get(k) in (None, "") and src.get(k) not in (None, ""):
            upd[k] = src[k]
    return upd


# ─── Estadísticas en memoria (expuestas en /scraper/health) ──────────────
GATE_STATS: dict[str, Counter] = defaultdict(Counter)
_DIA_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _eventos_del_dia(dia: date) -> list[dict]:
    key = dia.isoformat()
    hit = _DIA_CACHE.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    from app.database import supabase
    ini = datetime(dia.year, dia.month, dia.day, tzinfo=CO_TZ)
    try:
        rows = (
            supabase.table("eventos")
            .select("id,titulo,slug,fecha_inicio,espacio_id,nombre_lugar,hora_confirmada,imagen_url,descripcion,"
                    "fuente,fuente_url,lat,lng,precio")
            .gte("fecha_inicio", ini.isoformat())
            .lt("fecha_inicio", (ini + timedelta(days=1)).isoformat())
            .limit(500)
            .execute()
        ).data or []
    except Exception:
        rows = []
    if len(_DIA_CACHE) > 400:
        _DIA_CACHE.clear()
    _DIA_CACHE[key] = (time.monotonic() + 600, rows)
    return rows


# ─── Precisión por fuente ────────────────────────────────────────────────
UMBRAL_MALAS = 0.60     # > 60 % rechazado/duplicado/cuarentena …
MIN_DECISIONES = 20     # … con al menos 20 decisiones en la ventana
VENTANA_DIAS = 14
_REVISION_CACHE: dict = {"hasta": 0.0, "fuentes": set()}


def fuentes_en_revision() -> set[str]:
    """Fuentes cuya precisión reciente es mala: sus eventos nuevos van a cuarentena."""
    if _REVISION_CACHE["hasta"] > time.monotonic():
        return _REVISION_CACHE["fuentes"]
    fuentes: set[str] = set()
    try:
        import json as _json
        from app.database import supabase
        row = supabase.table("config_kv").select("value").eq("key", "gate_fuentes_revision").execute().data
        if row:
            fuentes = set(_json.loads(row[0]["value"]).get("fuentes", []))
    except Exception:
        pass
    _REVISION_CACHE.update({"hasta": time.monotonic() + 600, "fuentes": fuentes})
    return fuentes


def calcular_precision(historial: list[dict]) -> dict:
    """Función pura: agrega snapshots diarios {fuente: {decision: n}} y marca fuentes malas."""
    total: dict[str, Counter] = defaultdict(Counter)
    for snap in historial:
        for fuente, c in snap.items():
            total[fuente].update(c)
    reporte, en_revision = {}, []
    for fuente, c in total.items():
        n = sum(c.values())
        malas = c["rechazar"] + c["duplicado"] + c["cuarentena"]
        tasa = round(malas / n, 3) if n else 0.0
        reporte[fuente] = {**dict(c), "total": n, "tasa_mala": tasa}
        if n >= MIN_DECISIONES and tasa > UMBRAL_MALAS and confianza_fuente(fuente) != "alta":
            en_revision.append(fuente)
    return {"fuentes": sorted(en_revision), "reporte": reporte}


def guardar_precision_diaria() -> dict:
    """Job nocturno: guarda el snapshot del día y recalcula las fuentes en revisión."""
    import json as _json
    from app.database import supabase
    hoy = datetime.now(CO_TZ).date()
    snap = {k: dict(v) for k, v in GATE_STATS.items()}
    try:
        supabase.table("config_kv").upsert(
            {"key": f"gate_stats:{hoy.isoformat()}", "value": _json.dumps(snap, ensure_ascii=False)},
            on_conflict="key").execute()
        claves = [f"gate_stats:{(hoy - timedelta(days=i)).isoformat()}" for i in range(VENTANA_DIAS)]
        rows = supabase.table("config_kv").select("key,value").in_("key", claves).execute().data or []
        historial = [_json.loads(r["value"]) for r in rows]
    except Exception as exc:
        print(f"[gate] precision error: {exc}")
        return {}
    res = calcular_precision(historial)
    try:
        supabase.table("config_kv").upsert(
            {"key": "gate_fuentes_revision", "value": _json.dumps(res, ensure_ascii=False)},
            on_conflict="key").execute()
    except Exception:
        pass
    GATE_STATS.clear()
    _REVISION_CACHE["hasta"] = 0.0
    print(f"📊 Precisión por fuente: en revisión = {res['fuentes']}")
    return res


class _Resp:
    """Imita la respuesta de supabase-py para no romper a los llamadores (`res.data`)."""
    def __init__(self, data: list, decision: str, motivos: list[str]):
        self.data = data
        self.decision = decision
        self.motivos = motivos


def insertar_evento(payload: dict, *, upsert: bool = False) -> _Resp:
    """Única puerta de entrada de eventos de scrapers y usuarios."""
    from app.database import supabase

    ev = evaluar_evento(payload)
    fuente = (payload.get("fuente") or "?")[:40]
    p = ev.payload

    if ev.decision != "rechazar":
        ini = _parse_dt(p.get("fecha_inicio"))
        if ini:
            for ex in _eventos_del_dia(ini.date()):
                if ex.get("slug") and ex.get("slug") == p.get("slug"):
                    continue  # mismo registro (upsert): no es duplicado
                if _misma_funcion(p, ex):
                    upd = _completar_desde(ex, p)
                    if upd:
                        try:
                            supabase.table("eventos").update(upd).eq("id", ex["id"]).execute()
                            ex.update(upd)
                        except Exception as exc:
                            print(f"[gate] merge error: {exc}")
                    GATE_STATS[fuente]["duplicado"] += 1
                    return _Resp([], "duplicado", [f"duplicado_de:{ex['id']}"] + (["completo_campos"] if upd else []))

    if ev.decision == "rechazar":
        GATE_STATS[fuente]["rechazar"] += 1
        print(f"    🚫 [gate] rechazado ({', '.join(ev.motivos[:3])}): {(payload.get('titulo') or '')[:60]}")
        return _Resp([], "rechazar", ev.motivos)

    if ev.decision == "publicar" and p.get("oculto") is True:
        ev.decision = "cuarentena"
    if ev.decision == "publicar" and fuente in fuentes_en_revision():
        ev.decision = "cuarentena"
        ev.motivos.append("fuente_en_revision")
    if ev.decision == "cuarentena":
        p["oculto"] = True
        p["verificado"] = False
        p["oculto_motivo"] = "gate:cuarentena:" + ",".join(m for m in ev.motivos if m not in ("titulo_limpiado", "descripcion_limpiada"))[:180]

    def _ejecutar(datos: dict):
        q = supabase.table("eventos")
        return (q.upsert(datos, on_conflict="slug") if upsert else q.insert(datos)).execute()

    res = None
    for _ in range(3):
        try:
            res = _ejecutar(p)
            break
        except Exception as exc:
            # Columnas opcionales que pueden no estar migradas todavía
            faltante = next((c for c in ("oculto_motivo", "evidencia", "direccion") if c in p and c in str(exc)), None)
            if not faltante:
                raise
            p.pop(faltante, None)
    GATE_STATS[fuente][ev.decision] += 1
    ini = _parse_dt(p.get("fecha_inicio"))
    if ini and res.data:
        _DIA_CACHE.get(ini.date().isoformat(), (0, []))[1].extend(res.data)
    return _Resp(res.data or [], ev.decision, ev.motivos)


# ─── Revisión retroactiva (job nocturno) ─────────────────────────────────

def planear_revision(eventos: list[dict], *, ahora: Optional[datetime] = None) -> dict:
    """Función pura: decide qué ocultar/limpiar/fusionar en un lote de eventos ya publicados."""
    ahora = ahora or datetime.now(CO_TZ)
    ocultar: dict[str, str] = {}
    actualizar: dict[str, dict] = {}
    for e in eventos:
        r = evaluar_evento(e, ahora=ahora)
        if r.decision in ("rechazar", "cuarentena"):
            ocultar[e["id"]] = f"gate:{r.decision}:" + ",".join(
                m for m in r.motivos if m not in ("titulo_limpiado", "descripcion_limpiada"))[:180]
            continue
        cambios = {k: r.payload.get(k) for k in ("titulo", "descripcion", "fecha_fin", "hora_confirmada")
                   if k in e and r.payload.get(k) != e.get(k)}
        if cambios:
            actualizar[e["id"]] = cambios
    # Duplicados entre los que siguen visibles
    por_dia: dict[date, list[dict]] = defaultdict(list)
    for e in eventos:
        if e["id"] in ocultar:
            continue
        d = _parse_dt(e.get("fecha_inicio"))
        if d:
            vista = {**e, **actualizar.get(e["id"], {})}
            por_dia[d.date()].append(vista)
    conservados_por_dia: dict[date, list[dict]] = {}
    for dia, grupo in por_dia.items():
        grupo.sort(key=_calidad, reverse=True)
        conservados: list[dict] = []
        for e in grupo:
            principal = next((c for c in conservados if _misma_funcion(c, e)), None)
            if principal is None:
                conservados.append(e)
                continue
            ocultar[e["id"]] = f"gate:duplicado:{principal['id']}"
            actualizar.pop(e["id"], None)
            extra = _completar_desde(principal, e)
            if extra:
                principal.update(extra)
                actualizar.setdefault(principal["id"], {}).update(extra)
        conservados_por_dia[dia] = conservados
    # Lo que va a cuarentena igual aporta imagen/hora al duplicado visible
    for e in eventos:
        if not ocultar.get(e["id"], "").startswith("gate:cuarentena"):
            continue
        d = _parse_dt(e.get("fecha_inicio"))
        principal = next((c for c in conservados_por_dia.get(d.date() if d else None, []) if _misma_funcion(c, e)), None)
        if principal:
            ocultar[e["id"]] = f"gate:duplicado:{principal['id']}"
            extra = _completar_desde(principal, e)
            if extra:
                principal.update(extra)
                actualizar.setdefault(principal["id"], {}).update(extra)
    return {"ocultar": ocultar, "actualizar": actualizar}


def revisar_calidad_eventos(aplicar: bool = True) -> dict:
    """Aplica la puerta a los eventos vigentes ya publicados. Oculta, no borra."""
    from app.database import supabase

    hoy = datetime.now(CO_TZ).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    eventos: list[dict] = []
    offset = 0
    while True:
        lote = (
            supabase.table("eventos").select("*")
            .or_(f"fecha_inicio.gte.{hoy},fecha_fin.gte.{hoy}")
            .order("fecha_inicio").range(offset, offset + 499).execute()
        ).data or []
        eventos.extend(e for e in lote if e.get("oculto") is not True)
        if len(lote) < 500:
            break
        offset += 500
    plan = planear_revision(eventos)
    resumen = {
        "revisados": len(eventos),
        "ocultar": len(plan["ocultar"]),
        "actualizar": len(plan["actualizar"]),
        "motivos": Counter(m.split(":")[1] for m in plan["ocultar"].values()),
    }
    if not aplicar:
        return {**resumen, "plan": plan}
    # Respaldo para revertir: SELECT value FROM config_kv WHERE key LIKE 'gate_revision:%'
    try:
        import json as _json
        supabase.table("config_kv").upsert(
            {"key": f"gate_revision:{datetime.now(CO_TZ).strftime('%Y-%m-%dT%H%M')}",
             "value": _json.dumps({"ocultar": plan["ocultar"]}, ensure_ascii=False)},
            on_conflict="key",
        ).execute()
    except Exception as exc:
        print(f"[gate] respaldo config_kv error: {exc}")
    for eid, motivo in plan["ocultar"].items():
        try:
            supabase.table("eventos").update({"oculto": True, "oculto_motivo": motivo}).eq("id", eid).execute()
        except Exception:
            try:
                supabase.table("eventos").update({"oculto": True}).eq("id", eid).execute()
            except Exception as exc:
                print(f"[gate] ocultar error {eid}: {exc}")
    for eid, cambios in plan["actualizar"].items():
        try:
            supabase.table("eventos").update(cambios).eq("id", eid).execute()
        except Exception as exc:
            print(f"[gate] update error {eid}: {exc}")
    try:
        supabase.table("scraping_log").insert({
            "fuente": "gate_revision", "registros_nuevos": 0,
            "registros_actualizados": resumen["actualizar"], "errores": 0,
            "detalle": {k: (dict(v) if isinstance(v, Counter) else v) for k, v in resumen.items()},
        }).execute()
    except Exception:
        pass
    print(f"🧹 Revisión de calidad: {resumen}")
    return resumen
