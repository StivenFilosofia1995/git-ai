"""
ig_precision.py — De un post de Instagram a un evento SOLO con evidencia (cero LLM).

Por qué: el extractor anterior inventaba datos.
- Hora: "este 19 de febrero" → 19:00; "$20.000" → 20:00; y si no había hora, 19:00 por defecto.
- Año: un post de febrero de 2026 que decía "19 de febrero" se mandaba a 2027.
- No eventos: castings, inscripciones, saludos, noticias y crónicas pasaban como eventos.

Reglas de este módulo (todas deterministas y con prueba unitaria):
1. FECHA: tiene que estar escrita y poder anclarse sin adivinar.
   - El año lo da la fecha de publicación del post: el evento es la primera fecha que
     cae entre el día del post y 180 días después.
   - Si se cita el día de la semana, tiene que coincidir.
   - Sin fecha de publicación solo se acepta una fecha con año explícito o con día de la
     semana que la confirme.
   - "Hoy", "mañana" y "este sábado" solo se aceptan si el post tiene 10 días o menos.
2. HORA: solo si está escrita sin ambigüedad (8 p. m., 20:00, 7:30 pm, "a las 7 de la
   noche"). Nunca por defecto, nunca de un precio ni de un número de día.
3. NO EVENTOS: castings, convocatorias, saludos, noticias, crónicas en pasado y
   eventos en otras ciudades o países se rechazan.
4. EVIDENCIA: cada evento guarda el fragmento exacto del que salió su fecha y su hora,
   y un puntaje de confianza. Por debajo del umbral va a cuarentena.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

CO_TZ = ZoneInfo("America/Bogota")

_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
         "lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
          "ene": 1, "feb": 2, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9,
          "oct": 10, "nov": 11, "dic": 12}
_DIA_RE = r"(lunes|martes|miercoles|jueves|viernes|sabado|domingo|lun|mar|mie|jue|vie|sab|dom)"
_MES_RE = r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|abr|may|jun|jul|ago|sept|sep|oct|nov|dic)"

# "sábado 3 de octubre de 2026", "3 de octubre", "sáb 3 oct"
_FECHA_LARGA = re.compile(rf"(?:\b{_DIA_RE}\.?,?\s+)?\b(\d{{1,2}})\s+(?:de\s+)?{_MES_RE}\b\.?(?:\s+(?:de\s+|del\s+)?(\d{{4}}))?")
# "del 3 al 5 de octubre", "3 y 4 de octubre"
_RANGO = re.compile(rf"\b(?:del?\s+)?(\d{{1,2}})\s*(?:al|a|y|-)\s*(\d{{1,2}})\s+(?:de\s+)?{_MES_RE}\b(?:\s+(?:de\s+)?(\d{{4}}))?")
# "25/10", "25/10/2026" (solo con barra: "7.5" o "20.000" no son fechas)
_FECHA_NUM = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/])")
# "sáb 25", "viernes 7" (sin mes)
_DIA_NUM = re.compile(rf"\b{_DIA_RE}\.?\s+(\d{{1,2}})\b(?!\s*(?:de\s+)?{_MES_RE})(?!\s*[:.h]\d)")
_RELATIVA = re.compile(rf"\b(hoy|esta noche|manana|pasado manana|este fin de semana|(?:este|esta|el proximo|proximo)\s+{_DIA_RE})\b")

# Horas. Se excluyen precios ($20.000), miles (20.000) y rangos de años.
_HORA_HM = re.compile(r"(?<![\d$.,])(\d{1,2})\s*[:h]\s*(\d{2})(?![\d.,])\s*(a\.?\s?m\.?|p\.?\s?m\.?|hrs?\b|h\b)?")
_HORA_PUNTO = re.compile(r"(?<![\d$.,])(\d{1,2})\.(\d{2})(?![\d.,])\s*(a\.?\s?m\.?|p\.?\s?m\.?)")
_HORA_AMPM = re.compile(r"(?<![\d$.,:])(\d{1,2})\s*(a\.?\s?m\.?|p\.?\s?m\.?)(?![a-z])")
_HORA_LAS = re.compile(r"\ba\s+las\s+(\d{1,2})(?::(\d{2}))?\s*(?:de\s+la\s+(manana|tarde|noche))?")

# Lo que NO es un evento al que el público puede ir
_NO_EVENTO = re.compile(
    r"\b(casting|audicion(?:es)?|convocatoria|se busca|buscamos (?:hombres|mujeres|actores|actrices|personas)|"
    r"feliz (?:dia|cumpleanos|navidad|ano)|felicitamos|en memoria de|q\.?e\.?p\.?d|condolencias|"
    r"vacante|oferta laboral|estamos contratando|"
    r"segun (?:la|el)|informo|ocupacion|urgencias|comunicado|"
    r"gracias a todos|gracias por (?:venir|acompanarnos)|asi (?:vivimos|fue)|fue un exito|"
    r"el pasado (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|fin de semana)|la semana pasada|ayer|"
    r"sorteo|giveaway|descuento en|promocion)\b"
)
_CURSO = re.compile(r"\b(inscripciones abiertas|preinscripci|matriculas|curso de|diplomado|semestre|cupos limitados para el curso)\b")
_FUERA = re.compile(
    r"\b(republica dominicana|ecuador|quito|peru|lima|mexico|argentina|chile|espana|madrid|usa|estados unidos|"
    r"bogota|cali|cartagena|barranquilla|bucaramanga|pereira|manizales|cucuta|santa marta|pasto|"
    r"gira (?:por|internacional|nacional))\b"
)
_VALLE = re.compile(r"\b(medellin|envigado|itagui|bello|sabaneta|la estrella|caldas|copacabana|girardota|barbosa|valle de aburra)\b")
_EVENTO = re.compile(
    r"\b(concierto|toque|en vivo|obra|funcion|temporada|estreno|teatro|danza|presentacion|recital|"
    r"exposicion|muestra|inauguracion|festival|feria|conversatorio|charla|conferencia|lanzamiento|"
    r"proyeccion|cine|cineforo|taller|clase abierta|laboratorio|lectura|club de|tertulia|slam|"
    r"open mic|micro abierto|batalla|jam|fiesta|noche de|velada|encuentro|circo|impro|stand ?up|"
    r"te invitamos|los invitamos|acompananos|nos vemos|entrada libre|boletas|entradas)\b"
)
_LUGAR = re.compile(r"(\ben (?:el|la|los|nuestra|nuestro)\s+[A-ZÁÉÍÓÚ]|\b(?:cra|carrera|calle|cl|cll|av|avenida|diagonal|transversal)\.?\s*\d|#\s*\d)", re.I)
_PRECIO = re.compile(r"(\$\s?\d|entrada libre|gratis|gratuit[oa]|aporte voluntario|boleta|cover)")
_CTA = re.compile(r"^(inscripciones abiertas|ya te inscribiste|no te lo pierdas|atencion|ultimos cupos|"
                  r"preinscripciones abiertas|save the date|agenda|hoy|manana|recuerda|importante)\b")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[​-‏﻿]", "", s)


def _limpiar(texto: str) -> str:
    t = re.sub(r"[​-‏﻿]", "", texto or "")
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿⬀-⯿️]", "", t)
    t = re.sub(r"(?<!\w)[#@][\w.]+", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()


@dataclass
class Resultado:
    ok: bool
    motivo: str = ""
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    hora_confirmada: bool = False
    titulo: str = ""
    descripcion: str = ""
    precio: str = "Consultar"
    es_gratuito: bool = False
    confianza: int = 0
    evidencia: dict = field(default_factory=dict)

    @property
    def decision(self) -> str:
        if not self.ok:
            return "rechazar"
        return "publicar" if self.confianza >= 4 else "cuarentena"


# ─── Fecha ──────────────────────────────────────────────────────────────────

def _anio(d: int, m: int, dia_semana: Optional[int], anio_txt: Optional[str], ancla: Optional[date],
          hoy: date) -> tuple[Optional[date], str]:
    """Resuelve el año sin adivinar. Devuelve (fecha, motivo_si_falla)."""
    if anio_txt:
        y = int(anio_txt) + (2000 if len(anio_txt) == 2 else 0)
        try:
            f = date(y, m, d)
        except ValueError:
            return None, "fecha_invalida"
        if dia_semana is not None and f.weekday() != dia_semana:
            return None, "dia_semana_no_coincide"
        return f, ""
    if ancla:
        for y in (ancla.year, ancla.year + 1):
            try:
                f = date(y, m, d)
            except ValueError:
                continue
            if ancla - timedelta(days=1) <= f <= ancla + timedelta(days=180):
                if dia_semana is not None and f.weekday() != dia_semana:
                    return None, "dia_semana_no_coincide"
                return f, ""
        return None, "fecha_lejos_del_post"
    # Sin fecha de publicación: solo el día de la semana puede confirmar el año
    if dia_semana is None:
        return None, "sin_ancla_para_el_anio"
    for y in (hoy.year, hoy.year + 1):
        try:
            f = date(y, m, d)
        except ValueError:
            continue
        if f >= hoy and f.weekday() == dia_semana:
            return f, ""
    return None, "dia_semana_no_coincide"


def extraer_fecha(texto_n: str, ancla: Optional[date], hoy: date,
                  post_dias: Optional[int]) -> tuple[Optional[date], Optional[date], str, str]:
    """(inicio, fin, fragmento_evidencia, motivo_si_falla) sobre texto normalizado."""
    m = _RANGO.search(texto_n)
    if m:
        d1, d2, mes, anio = int(m.group(1)), int(m.group(2)), _MESES[m.group(3)], m.group(4)
        f1, mot = _anio(d1, mes, None, anio, ancla, hoy)
        if f1:
            try:
                f2 = date(f1.year, mes, d2)
                if f2 >= f1:
                    return f1, f2, m.group(0).strip(), ""
            except ValueError:
                pass
    motivo = "sin_fecha"
    candidatos: list[tuple[date, str]] = []
    for m in _FECHA_LARGA.finditer(texto_n):
        dia_txt, d, mes_txt, anio = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        f, mot = _anio(d, _MESES[mes_txt], _DIAS.get(dia_txt) if dia_txt else None, anio, ancla, hoy)
        if f:
            candidatos.append((f, m.group(0).strip()))
        else:
            motivo = mot
    if not candidatos:
        for m in _FECHA_NUM.finditer(texto_n):
            d, mes, anio = int(m.group(1)), int(m.group(2)), m.group(3)
            if 1 <= mes <= 12 and 1 <= d <= 31:
                f, mot = _anio(d, mes, None, anio, ancla, hoy)
                if f:
                    candidatos.append((f, m.group(0)))
                else:
                    motivo = mot
    if not candidatos and ancla:
        for m in _DIA_NUM.finditer(texto_n):
            wd, n = _DIAS[m.group(1)], int(m.group(2))
            for k in range(0, 45):
                f = ancla + timedelta(days=k)
                if f.day == n and f.weekday() == wd:
                    candidatos.append((f, m.group(0).strip()))
                    break
    if not candidatos and ancla and post_dias is not None and post_dias <= 10:
        m = _RELATIVA.search(texto_n)
        if m:
            frase = m.group(1)
            if frase in ("hoy", "esta noche"):
                f = ancla
            elif frase == "manana":
                f = ancla + timedelta(days=1)
            elif frase == "pasado manana":
                f = ancla + timedelta(days=2)
            elif frase == "este fin de semana":
                f = ancla + timedelta(days=(5 - ancla.weekday()) % 7)
            else:
                wd = _DIAS[frase.split()[-1]]
                f = ancla + timedelta(days=(wd - ancla.weekday()) % 7 or 7)
            candidatos.append((f, frase))
    elif not candidatos and _RELATIVA.search(texto_n):
        motivo = "fecha_relativa_sin_post_reciente"
    futuros = sorted(c for c in candidatos if c[0] >= hoy)
    if futuros:
        return futuros[0][0], None, futuros[0][1], ""
    if candidatos:
        return None, None, "", "ya_paso"
    return None, None, "", motivo


# ─── Hora ───────────────────────────────────────────────────────────────────

def extraer_hora(texto_n: str) -> tuple[Optional[tuple[int, int]], str]:
    """Solo horas inequívocas. Devuelve ((h, m) | None, fragmento)."""
    def ampm(h: int, suf: str) -> Optional[int]:
        pm = suf.replace(".", "").replace(" ", "").startswith("p")
        if not 1 <= h <= 12:
            return None
        return (h % 12) + (12 if pm else 0)

    for m in _HORA_HM.finditer(texto_n):
        h, mi, suf = int(m.group(1)), int(m.group(2)), (m.group(3) or "").strip()
        if mi > 59:
            continue
        if suf.startswith(("a", "p")):
            h2 = ampm(h, suf)
            if h2 is not None:
                return (h2, mi), m.group(0).strip()
        elif suf.startswith("h") or 13 <= h <= 23:
            if 0 <= h <= 23:
                return (h, mi), m.group(0).strip()
        # "7:30" sin a.m./p.m. es ambiguo → no se confirma
    for rx in (_HORA_PUNTO, _HORA_AMPM):
        for m in rx.finditer(texto_n):
            h = int(m.group(1))
            mi = int(m.group(2)) if rx is _HORA_PUNTO else 0
            suf = m.group(3) if rx is _HORA_PUNTO else m.group(2)
            h2 = ampm(h, suf)
            if h2 is not None and mi <= 59:
                return (h2, mi), m.group(0).strip()
    for m in _HORA_LAS.finditer(texto_n):
        h, mi, franja = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if franja and 1 <= h <= 12:
            if franja in ("tarde", "noche") and h < 12:
                h += 12
            return (h, mi), m.group(0).strip()
        if 13 <= h <= 23:
            return (h, mi), m.group(0).strip()
    return None, ""


# ─── Título ─────────────────────────────────────────────────────────────────

def extraer_titulo(caption: str) -> str:
    limpio = _limpiar(caption)
    m = re.search(r"[«\"“]([^»\"”]{4,80})[»\"”]", limpio)
    if m:
        return m.group(1).strip(" .,:;-")
    for linea in limpio.splitlines():
        lin = linea.strip(" .,:;-*_|•")
        cta = _CTA.match(_norm(lin))
        if cta:  # "INSCRIPCIONES ABIERTAS Taller de Rakú" → "Taller de Rakú"
            lin = lin[cta.end():].strip(" .,:;-*_|•!¡?¿")
        if len(lin) < 4:
            continue
        frase = re.split(r"(?<=[.!?])\s", lin)[0].strip(" .,:;-")
        if len(frase) > 80:
            frase = frase[:78].rsplit(" ", 1)[0] + "…"
        return frase
    return ""


# ─── Análisis completo ─────────────────────────────────────────────────────

def analizar_post(caption: str, publicado: Optional[datetime], ahora: Optional[datetime] = None) -> Resultado:
    ahora = ahora or datetime.now(CO_TZ)
    hoy = ahora.date()
    if not caption or len(caption.strip()) < 15:
        return Resultado(False, "caption_vacio")
    n = _norm(_limpiar(caption))
    if _NO_EVENTO.search(n):
        return Resultado(False, f"no_es_evento:{_NO_EVENTO.search(n).group(0)}")
    if _FUERA.search(n) and not _VALLE.search(n):
        return Resultado(False, f"otra_ciudad:{_FUERA.search(n).group(0)}")
    if not _EVENTO.search(n):
        return Resultado(False, "sin_palabras_de_evento")

    ancla = publicado.astimezone(CO_TZ).date() if publicado else None
    post_dias = (hoy - ancla).days if ancla else None
    inicio, fin, ev_fecha, motivo = extraer_fecha(n, ancla, hoy, post_dias)
    if not inicio:
        return Resultado(False, motivo or "sin_fecha")
    hm, ev_hora = extraer_hora(n)
    titulo = extraer_titulo(caption)
    if len(titulo) < 4:
        return Resultado(False, "sin_titulo")

    h, mi = hm if hm else (0, 0)
    dt_ini = datetime(inicio.year, inicio.month, inicio.day, h, mi, tzinfo=CO_TZ)
    dt_fin = datetime(fin.year, fin.month, fin.day, 23, 59, tzinfo=CO_TZ) if fin else None

    gratis = bool(re.search(r"(entrada libre|gratis|gratuit[oa]|sin costo)", n))
    precio_m = re.search(r"\$\s?\d{1,3}(?:[.,]\d{3})+|\$\s?\d+", caption)
    precio = "Gratis" if gratis else (precio_m.group(0).replace(" ", "") if precio_m else "Consultar")

    confianza = 2  # fecha explícita y anclada
    if re.search(_DIA_RE, ev_fecha) or (fin is not None):
        confianza += 1
    if hm:
        confianza += 1
    if _LUGAR.search(caption):
        confianza += 1
    if post_dias is not None and post_dias <= 30:
        confianza += 1
    if _PRECIO.search(n):
        confianza += 1
    if _CURSO.search(n):
        confianza -= 2  # cursos y matrículas: que los revise una persona

    desc = _limpiar(caption)
    desc = re.sub(r"\s*\n\s*", " · ", desc)[:400]
    return Resultado(True, "", dt_ini, dt_fin, bool(hm), titulo, desc, precio, gratis, confianza,
                     {"fecha": ev_fecha, "hora": ev_hora or None,
                      "publicado": ancla.isoformat() if ancla else None})
