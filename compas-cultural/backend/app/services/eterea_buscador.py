"""
ETÉREA sin LLM: entiende la pregunta con reglas y responde con la misma agenda que ve la web.

"teatro este finde", "conciertos gratis hoy", "talleres en Envigado", "qué hay cerca"…
- Fecha: hoy, esta noche, mañana, finde, un día de la semana, esta semana, la próxima, este mes.
- Tipo de plan: diccionario de categorías y palabras (teatro, música, danza, cine, ciencia…).
- Gratis, municipio o barrio, y ubicación del usuario ("[Ubicación: lat, lng]").
- Lo que no entra en lo anterior se busca como texto en título, lugar y descripción.
- Las preguntas cortas de seguimiento ("¿y gratis?") heredan lo que faltó del mensaje anterior.

Solo se consulta get_eventos (hora de Bogotá, sin ocultos, sin eventos ya terminados): cero tokens.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.services.evento_service import CO_TZ, get_eventos, get_eventos_cerca

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
DIAS_NOMBRE = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}

# nombre visible → (categorías del sistema, raíces de palabras en título/lugar/descripción, disparadores)
TIPOS: dict[str, tuple[set[str], tuple[str, ...], tuple[str, ...]]] = {
    "teatro": ({"teatro"}, ("teatro", "obra", "dramat", "impro", "clown", "titere", "monolog"),
               ("teatro", "obra", "obras", "impro", "titeres", "monologo", "stand up", "standup")),
    "música": ({"musica_en_vivo", "rock", "jazz", "hip_hop", "electronica"},
               ("concierto", "musica", "banda", "recital", "orquesta", "sinfon", "cancion"),
               ("musica", "concierto", "conciertos", "recital", "toque", "toques", "banda", "bandas", "orquesta")),
    "rock": ({"rock"}, ("rock", "metal", "punk"), ("rock", "metal", "punk")),
    "jazz": ({"jazz"}, ("jazz",), ("jazz",)),
    "hip hop": ({"hip_hop"}, ("hip hop", "hiphop", "rap ", "freestyle"), ("hip hop", "hiphop", "rap", "freestyle")),
    "electrónica": ({"electronica"}, ("electronic", "techno", " dj"), ("electronica", "techno", "dj", "rave")),
    "danza": ({"danza"}, ("danza", "baile", "salsa", "tango", "ballet", "bailar"),
              ("danza", "baile", "bailar", "salsa", "tango", "ballet")),
    "cine": ({"cine"}, ("cine", "pelicula", "documental", "proyeccion", "cortometraje"),
             ("cine", "pelicula", "peliculas", "documental", "cortos", "cineclub")),
    "literatura": ({"poesia", "libreria", "editorial"},
                   ("poesia", "poema", "lectura", "libro", "literat", "escritura", "cuento", "tertulia"),
                   ("poesia", "literatura", "libros", "libro", "lectura", "leer", "escritura", "tertulia", "cuentos")),
    "talleres": ({"taller"}, ("taller", "curso", "clase", "laboratorio", "semillero", "club"),
                 ("taller", "talleres", "curso", "cursos", "clase", "clases", "aprender", "laboratorio")),
    "arte": ({"galeria", "arte_contemporaneo", "fotografia", "mural"},
             ("exposicion", "muestra", "galeria", "museo", "arte", "pintura", "escultura"),
             ("arte", "expo", "exposicion", "exposiciones", "galeria", "museo", "museos", "pintura")),
    "fotografía": ({"fotografia"}, ("fotograf",), ("fotografia", "foto", "fotos")),
    "circo": ({"circo"}, ("circo", "malabar", "acrobac"), ("circo", "malabares")),
    "festivales": ({"festival"}, ("festival", "feria", "fiesta"), ("festival", "festivales", "feria", "fiesta")),
    "charlas": ({"conferencia", "filosofia"}, ("charla", "conversatorio", "conferencia", "foro", "panel"),
                ("charla", "charlas", "conversatorio", "conferencia", "foro", "filosofia")),
    "ciencia": (set(), ("ciencia", "planetario", "astronom", "explora", "tecnolog", "robotic", "experiment"),
                ("ciencia", "planetario", "astronomia", "estrellas", "explora", "tecnologia")),
    "planes en familia": (set(), ("infantil", "nino", "familia", "familiar", "bebe", "primera infancia"),
                          ("ninos", "nino", "ninas", "infantil", "familia", "familiar", "bebes", "hijos")),
}

MUNICIPIOS = {
    "medellin": ("medellin", "mde"), "itagui": ("itagui",), "envigado": ("envigado",), "sabaneta": ("sabaneta",),
    "bello": ("bello",), "la_estrella": ("la estrella",), "caldas": ("caldas",), "copacabana": ("copacabana",),
    "girardota": ("girardota",), "barbosa": ("barbosa",),
}
MUNICIPIO_VISIBLE = {"medellin": "Medellín", "itagui": "Itagüí", "la_estrella": "La Estrella"}
BARRIOS = ("san antonio de prado", "el poblado", "poblado", "laureles", "belen", "la candelaria", "aranjuez",
           "manrique", "robledo", "castilla", "buenos aires", "san javier", "carabobo", "santa elena",
           "san cristobal", "guayabal", "la america", "villa hermosa", "moravia", "doce de octubre")

# Lugares que la gente nombra: además del tipo de plan, se buscan por nombre
NOMBRES_PROPIOS = ("planetario", "explora", "comfama", "comfenalco", "uva", "biblioteca", "otraparte",
                   "pablo tobon", "metropolitano", "mamm", "museo de antioquia", "jardin botanico", "deseos")

VACIAS = set("""a al algo alguna alguno algun ante como con cual cuales cuando de del donde el ella en entre es esa ese
eso esta este esto estos hay hoy la las le lo los me mi mis muy no o otra otro para pero por porfa porfavor puedo que
quiero quisiera recomienda recomiendame recomendas recomendame se ser si sin sobre su sus te ti tu un una uno unos y ya
yo vos ver hacer ir salir planes plan evento eventos actividad actividades cultura cultural culturales algo bueno buena
buenas buenos mejor mejores dame decime decir busco buscar buscando mostrame muestrame cuales gusta gustaria interesa
tienen tenes tengo sabes favor gracias hola valle aburra semana finde fin manana noche tarde gratis gratuito gratuitos
gratuita gratuitas cerca proxima proximo siguiente mes dia dias pasado esta este estos estas mismo cosas cosa todo
todos donde lugar lugares sitio sitios""".split())


def _n(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


@dataclass
class Consulta:
    desde: datetime
    hasta: datetime
    etiqueta: str
    fecha_explicita: bool = False
    tipos: list[str] = field(default_factory=list)
    palabras: list[str] = field(default_factory=list)
    gratis: bool = False
    municipio: Optional[str] = None
    barrio: Optional[str] = None
    ubicacion: Optional[tuple[float, float]] = None
    cerca: bool = False
    desde_hora: Optional[datetime] = None  # "esta noche": desde las 5 p. m.
    franja: Optional[tuple[int, int, str]] = None  # (hora inicial, hora final, "en la tarde")
    publico: Optional[str] = None  # clave de lexico.PUBLICOS
    precio_max: Optional[int] = None  # "barato" / "menos de 20 mil" (lo gratis siempre entra)
    virtual: bool = False
    sin_inscripcion: bool = False
    lugar: Optional[dict] = None  # lugar nombrado ("Otraparte"), lo resuelve eterea_dialogo
    zona: Optional[tuple] = None  # (nombre, barrios normalizados, centro lat/lng o None) p. ej. Comuna 13
    limite: int = 6
    realce: tuple = ()  # palabras que suben un evento sin excluir a los demás (p. ej. "halloween")

    @property
    def vacia(self) -> bool:
        return not (self.fecha_explicita or self.tipos or self.palabras or self.gratis or self.municipio
                    or self.barrio or self.cerca or self.franja or self.publico or self.precio_max
                    or self.virtual or self.lugar or self.zona)


def _dia(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _proxima(hoy: datetime, mes: int, dia: int) -> Optional[datetime]:
    """La próxima vez que cae ese día y mes (este año, o el siguiente si ya pasó)."""
    for anio in (hoy.year, hoy.year + 1):
        try:
            d = hoy.replace(year=anio, month=mes, day=dia)
        except ValueError:
            return None
        if d >= hoy - timedelta(days=1):
            return d
    return None


def _fecha_exacta(t: str, hoy: datetime):
    """Fechas con nombre: '15 de octubre', 'el 15', '15/10', 'en noviembre', 'entre el 10 y el 15',
    festividades ('Halloween', 'novenas'). Devuelve (desde, hasta, etiqueta, palabras usadas) o None."""
    from app.services.eterea_lexico import FESTIVIDADES, MESES as MESES_NUM
    for clave, (mes, dia, dias, etiqueta) in FESTIVIDADES.items():
        if f" {clave} " in t:
            d = _proxima(hoy, mes, dia)
            if d:
                ini = max(d, hoy)
                return ini, d + timedelta(days=dias), f"{etiqueta}", set(clave.split())
    meses = "|".join(sorted(MESES_NUM, key=len, reverse=True))
    m = re.search(rf" (?:entre el |del |desde el )?(\d{{1,2}}) (?:y el |al |hasta el |a )(\d{{1,2}})(?: de ({meses}))? ", t)
    if m:
        mes = MESES_NUM.get(m.group(3) or "", hoy.month)
        a, b = int(m.group(1)), int(m.group(2))
        d1, d2 = _proxima(hoy, mes, a), _proxima(hoy, mes, b)
        if d1 and d2 and d2 >= d1:
            return max(d1, hoy), d2 + timedelta(days=1), f"del {a} al {b} de {MESES_LARGOS[mes - 1]}", \
                {m.group(1), m.group(2), m.group(3) or ""}
    m = re.search(rf" (?:el |para el |este )?(\d{{1,2}}) de ({meses}) ", t) or \
        re.search(r" (?:el |para el )?(\d{1,2})/(\d{1,2}) ", t)
    if m:
        dia = int(m.group(1))
        mes = MESES_NUM.get(m.group(2)) or (int(m.group(2)) if m.group(2).isdigit() else None)
        d = _proxima(hoy, mes, dia) if mes and 1 <= mes <= 12 else None
        if d:
            return d, d + timedelta(days=1), f"el {dia} de {MESES_LARGOS[mes - 1]}", {m.group(1), m.group(2)}
    m = re.search(r" (?:el|para el|este) (\d{1,2})(?! de| a| p| y| hora| am| pm| mil| personas| anos)", t)
    if m and 1 <= int(m.group(1)) <= 31:
        dia = int(m.group(1))
        mes = hoy.month if dia >= hoy.day else (hoy.month % 12) + 1
        d = _proxima(hoy, mes, dia)
        if d:
            return d, d + timedelta(days=1), f"el {dia} de {MESES_LARGOS[mes - 1]}", {m.group(1)}
    m = re.search(rf" (?:en|para|de|todo|durante) ({meses}) ", t)
    if m and len(m.group(1)) > 3:
        mes = MESES_NUM[m.group(1)]
        d = _proxima(hoy, mes, 1) if mes != hoy.month else hoy
        if d:
            fin = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
            return max(d, hoy), fin, f"{m.group(1)}", {m.group(1)}
    return None


def _hora(n: int, sufijo: str) -> int:
    if sufijo in ("pm", "p m", "de la tarde", "de la noche") and n < 12:
        return n + 12
    if sufijo in ("am", "a m", "de la manana"):
        return n % 12
    return n + 12 if 1 <= n <= 7 else n  # "a las 7" casi siempre es de la noche


def _franja(t: str):
    from app.services.eterea_lexico import FRANJAS
    suf = r"(?: ?(pm|p m|am|a m|de la tarde|de la noche|de la manana))?"
    m = re.search(r" (?:despues de las|desde las|a partir de las|tipo|despues de la) (\d{1,2})" + suf + " ", t)
    if m:
        h = _hora(int(m.group(1)), m.group(2) or "")
        return (h, 24, f"desde las {h % 12 or 12} {'a. m.' if h < 12 else 'p. m.'}"), set()
    m = re.search(r" antes de las (\d{1,2})" + suf + " ", t)
    if m:
        h = _hora(int(m.group(1)), m.group(2) or "")
        return (0, h, f"antes de las {h % 12 or 12} {'a. m.' if h < 12 else 'p. m.'}"), set()
    m = re.search(r" (?:a las|tipo las|como a las) (\d{1,2})" + suf + " ", t)
    if m:
        h = _hora(int(m.group(1)), m.group(2) or "")
        return (max(0, h - 1), min(24, h + 2), f"hacia las {h % 12 or 12} {'a. m.' if h < 12 else 'p. m.'}"), set()
    for clave, (a, b, etiqueta) in FRANJAS.items():
        if f" {clave} " in t:
            return (a, b, etiqueta), set(clave.split())
    return None, set()


def entender(mensaje: str, ahora: Optional[datetime] = None) -> Consulta:
    ahora = ahora or datetime.now(CO_TZ)
    hoy = _dia(ahora)
    crudo = mensaje or ""
    ubic = None
    m = re.search(r"\[Ubicaci[oó]n:\s*(-?[\d.]+),\s*(-?[\d.]+)\]", crudo)
    if m:
        ubic = (float(m.group(1)), float(m.group(2)))
        crudo = crudo.replace(m.group(0), " ")
    crudo = re.sub(r"\[[^\]]*\]", " ", crudo)
    t = f" {_n(crudo)} "

    # ── Fecha ─────────────────────────────────────────────
    c = Consulta(desde=hoy, hasta=hoy + timedelta(days=7), etiqueta="los próximos 7 días")
    wd = hoy.weekday()
    usados: set[str] = set()

    def fecha(desde, hasta, etiqueta, palabras):
        c.desde, c.hasta, c.etiqueta, c.fecha_explicita = desde, hasta, etiqueta, True
        usados.update(palabras)

    exacta = _fecha_exacta(t, hoy)
    if exacta:
        fecha(*exacta)
        from app.services.eterea_lexico import REALCE_FESTIVIDAD
        c.realce = next((v for k, v in REALCE_FESTIVIDAD.items() if f" {k} " in t), ())
    elif re.search(r" (esta noche|hoy en la noche|en la noche de hoy|hoy por la noche|noche de hoy) ", t) \
            or t.strip() in ("noche", "y esta noche", "y en la noche"):
        fecha(hoy, hoy + timedelta(days=1), "esta noche", {"esta", "noche", "hoy"})
        c.desde_hora = hoy.replace(hour=17)
    elif re.search(r" pasado manana ", t):
        d = hoy + timedelta(days=2)
        fecha(d, d + timedelta(days=1), "pasado mañana", {"pasado", "manana"})
    elif re.search(r" manana ", t) and not re.search(r" (en|por) la manana ", t):
        d = hoy + timedelta(days=1)
        fecha(d, d + timedelta(days=1), "mañana", {"manana"})
    elif re.search(r" (hoy|ahora|ya mismo|esta tarde) ", t):
        fecha(hoy, hoy + timedelta(days=1), "hoy", {"hoy", "ahora", "tarde"})
    elif re.search(r" (finde|fin de semana|fines de semana|weekend) ", t):
        ini = hoy if wd >= 4 else hoy + timedelta(days=4 - wd)
        fecha(ini, hoy + timedelta(days=7 - wd), "este fin de semana", {"finde", "fin", "semana", "weekend"})
    elif re.search(r" (proxima semana|semana que viene|siguiente semana|otra semana) ", t):
        ini = hoy + timedelta(days=7 - wd)
        fecha(ini, ini + timedelta(days=7), "la próxima semana", {"proxima", "semana", "viene", "siguiente", "otra"})
    elif re.search(r" (esta semana|en la semana|semana) ", t):
        fecha(hoy, hoy + timedelta(days=7 - wd), "esta semana", {"esta", "semana"})
    elif re.search(r" (este mes|en el mes|mes) ", t):
        fin = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1)
        fecha(hoy, fin, "este mes", {"este", "mes"})
    else:
        for nombre, n in DIAS_NOMBRE.items():
            if f" {nombre} " in t:
                d = hoy + timedelta(days=(n - wd) % 7)
                fecha(d, d + timedelta(days=1), f"el {nombre.replace('sabado', 'sábado').replace('miercoles', 'miércoles')}", {nombre})
                break

    # ── Tipo de plan ──────────────────────────────────────
    for nombre, (_, _, disparadores) in TIPOS.items():
        if any(f" {d} " in t for d in disparadores):
            c.tipos.append(nombre)
            usados.update(w for d in disparadores for w in d.split())
    if "música" in c.tipos and any(x in c.tipos for x in ("rock", "jazz", "hip hop", "electrónica")):
        c.tipos.remove("música")

    # ── Precio y lugar ────────────────────────────────────
    c.gratis = bool(re.search(r" (gratis|gratuit[oa]s?|sin costo|free|entrada libre) ", t))
    for clave, alias in MUNICIPIOS.items():
        if any(f" {a} " in t for a in alias):
            c.municipio = clave
            usados.update(w for a in alias for w in a.split())
            break
    for b in BARRIOS:
        if f" {b} " in t:
            c.barrio = b
            usados.update(b.split())
            break
    c.cerca = bool(re.search(r" (cerca|cercanos?|cercanas?|alrededor|aca cerca|por aca) ", t))
    c.ubicacion = ubic

    # ── Franja, público, presupuesto, modalidad, cantidad ─
    from app.services import eterea_lexico as L
    c.franja, u = _franja(t)
    usados |= u
    for clave, (disparadores, _) in L.PUBLICOS.items():
        if L.hay(t, *disparadores):
            c.publico = clave
            usados.update(w for d in disparadores for w in d.split())
            break
    if not c.gratis:
        c.gratis = L.hay(t, *L.GRATIS)
    m = re.search(r" (?:menos de|maximo|max|hasta|no mas de|por debajo de) \$? ?(\d{1,3})(?:[.,]?(\d{3})| ?mil| ?k)? ", t)
    if m:
        c.precio_max = int(m.group(1)) * 1000 if (not m.group(2) and int(m.group(1)) < 1000) else int(m.group(1) + (m.group(2) or ""))
    elif L.hay(t, *L.BARATO):
        c.precio_max = L.TOPE_BARATO
    c.virtual = L.hay(t, *L.VIRTUAL)
    c.sin_inscripcion = L.hay(t, *L.SIN_INSCRIPCION)
    m = re.search(r" (\d{1,2}|dos|tres|cuatro|cinco|diez) (?:planes|opciones|eventos|ideas|cosas|lugares|sitios) ", t)
    numeros = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "diez": 10}
    if m:
        c.limite = max(1, min(12, numeros.get(m.group(1)) or int(m.group(1))))
    elif L.hay(t, *L.TODOS):
        c.limite = 12
    elif L.hay(t, "uno solo", "solo uno", "una sola", "solo una", "un solo plan", "un solo evento"):
        c.limite = 1

    # ── Texto libre ───────────────────────────────────────
    c.palabras = [w for w in t.split() if len(w) >= 4 and w not in VACIAS and w not in L.VACIAS_EXTRA
                  and w not in L.PALABRAS_DE_CONTROL and w not in usados and not w.isdigit()][:4]
    c.palabras += [p for p in NOMBRES_PROPIOS if f" {p} " in t and p not in c.palabras]
    # La palabra exacta que usó la persona pesa más que la categoría ("exposiciones" > "arte")
    for nombre in c.tipos:
        for d in TIPOS[nombre][2]:
            raiz = re.sub(r"(es|s)$", "", d) if len(d) > 6 else d
            if f" {d} " in t and len(raiz) >= 5 and raiz not in c.palabras:
                c.palabras.append(raiz)
    return c


def heredar(c: Consulta, previa: Consulta) -> Consulta:
    """'¿y gratis?' después de 'teatro este finde' conserva el teatro y el finde."""
    if not c.fecha_explicita and previa.fecha_explicita:
        c.desde, c.hasta, c.etiqueta, c.fecha_explicita, c.desde_hora = (
            previa.desde, previa.hasta, previa.etiqueta, True, previa.desde_hora)
    if not c.tipos and not c.palabras:
        c.tipos, c.palabras = previa.tipos, previa.palabras
    c.municipio = c.municipio or previa.municipio
    c.barrio = c.barrio or previa.barrio
    c.gratis = c.gratis or previa.gratis
    c.franja = c.franja or previa.franja
    c.publico = c.publico or previa.publico
    c.precio_max = c.precio_max if c.precio_max is not None else previa.precio_max
    c.lugar = c.lugar or previa.lugar
    c.zona = c.zona or previa.zona
    c.ubicacion = c.ubicacion or previa.ubicacion
    c.cerca = c.cerca or previa.cerca
    return c


_RAICES_RE = {nombre: re.compile(r"(?<![a-z])(" + "|".join(re.escape(r.strip()) for r in raices) + ")")
              for nombre, (_, raices, _) in TIPOS.items()}


def _tiene(texto: str, palabra: str) -> bool:
    """Coincidencia al inicio de palabra: 'arte' no casa con 'Otraparte' ni 'obra' con 'obrera'."""
    return re.search(r"(?<![a-z])" + re.escape(palabra), texto) is not None


def _puntaje(ev: dict, c: Consulta) -> int:
    titulo, lugar, desc = _n(ev.get("titulo")), _n(ev.get("nombre_lugar")), _n(ev.get("descripcion"))[:600]
    cats = {ev.get("categoria_principal")} | set(ev.get("categorias") or [])
    p = 0
    if c.tipos:
        mejor = 0
        for nombre in c.tipos:
            cats_tipo, rx = TIPOS[nombre][0], _RAICES_RE[nombre]
            if rx.search(titulo):
                mejor = max(mejor, 5)
            elif cats & cats_tipo:
                mejor = max(mejor, 4)
            elif rx.search(lugar):
                mejor = max(mejor, 2)
            elif rx.search(desc):
                mejor = max(mejor, 1)
        if not mejor:
            return 0
        p += mejor
    for w in c.palabras:
        if _tiene(titulo, w) or _tiene(lugar, w):
            p += 4
        elif _tiene(desc, w):
            p += 1
    if c.palabras and not c.tipos and p == 0:
        return 0
    if c.realce and any(_tiene(titulo, r) for r in c.realce):
        p += 6
    return p + 1


def _inicio(ev: dict) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(ev.get("fecha_inicio")).replace("Z", "+00:00"))
        return d.astimezone(CO_TZ) if d.tzinfo else d.replace(tzinfo=CO_TZ)
    except ValueError:
        return None


def precio_num(ev: dict) -> Optional[int]:
    """'$25.000', '25000', 'Desde 18 mil' → 25000 / 18000. None si no hay cifra."""
    if ev.get("es_gratuito"):
        return 0
    p = _n(str(ev.get("precio") or ""))
    m = re.search(r"(\d{1,3}) ?mil", p) or re.search(r"(\d{1,3}(?: ?\d{3})+|\d{4,6})", p)
    if not m:
        return None
    v = int(m.group(1).replace(" ", ""))
    return v * 1000 if "mil" in m.group(0) else v


_ALIAS_GENERICOS = {"centro", "estadio", "america", "colon", "prado", "boston", "bolivar", "jardin", "florida"}


def _cerca_de_zona(ev: dict, zona: tuple, radio_km: float = 1.6) -> bool:
    if len(zona) < 3 or not zona[2] or ev.get("lat") is None:
        return False
    from app.services.geo_verificacion import es_placeholder
    if es_placeholder(float(ev["lat"]), float(ev["lng"])):
        return False
    from app.services.ml_utils import haversine_km
    return haversine_km(zona[2][0], zona[2][1], float(ev["lat"]), float(ev["lng"])) <= radio_km


def _pasa_filtros(ev: dict, c: Consulta, ahora: datetime) -> bool:
    from app.services import eterea_lexico as L
    ini = _inicio(ev)
    if c.gratis and not ev.get("es_gratuito"):
        return False
    if c.precio_max is not None:
        v = precio_num(ev)
        if v is None or v > c.precio_max:
            return False
    lugar_txt = _n(f"{ev.get('barrio')} {ev.get('nombre_lugar')}")
    if c.barrio and c.barrio not in lugar_txt:
        return False
    if c.zona and len(c.zona) > 3 and c.zona[3] and ev.get("municipio")             and _n(ev.get("municipio")).replace(" ", "_") != c.zona[3]:
        return False  # "Prado" de Bello no es el Prado de La Candelaria
    if c.zona and not (_n(ev.get("barrio")) in c.zona[1]
                       or any(b and len(b) > 4 and b not in _ALIAS_GENERICOS and f" {b} " in f" {lugar_txt} "
                              for b in c.zona[1])
                       or _cerca_de_zona(ev, c.zona)):
        return False
    if c.lugar:
        nombre = _n(c.lugar.get("nombre"))
        if ev.get("espacio_id") != c.lugar.get("id") and nombre not in _n(ev.get("nombre_lugar")):
            return False
    if c.desde_hora and ini and ev.get("hora_confirmada") and ini < c.desde_hora:
        return False
    if c.franja and ini and ev.get("hora_confirmada"):
        h = ini.hour + ini.minute / 60
        if not (c.franja[0] <= h < c.franja[1]):
            return False
    texto = _n(f"{ev.get('titulo')} {ev.get('descripcion')}")[:1500]
    if c.publico:
        raices = L.PUBLICOS[c.publico][1]
        if raices and not any(r in texto for r in raices):
            return False
    if c.virtual and not L.hay(f" {texto} ", *L.VIRTUAL):
        return False
    if c.sin_inscripcion and re.search(r"inscripci|inscrib|reserva previa|cupos limitados", texto) \
            and "entrada libre" not in texto:
        return False
    # Lo que empezó hace más de una hora ya no sirve (salvo que siga en curso)
    if ini and ev.get("hora_confirmada") and ini < ahora - timedelta(hours=1) and not ev.get("fecha_fin"):
        return False
    return True


def buscar(c: Consulta, ahora: Optional[datetime] = None, limite: Optional[int] = None) -> tuple[list[dict], int]:
    ahora = ahora or datetime.now(CO_TZ)
    limite = limite or c.limite
    dias = max(1, (c.hasta - _dia(ahora)).days)
    if c.ubicacion and (c.cerca or not c.municipio):
        eventos = get_eventos_cerca(c.ubicacion[0], c.ubicacion[1], radio_km=6, dias=dias, limit=300)
        eventos = [e for e in eventos if (_inicio(e) or c.desde) < c.hasta]
    else:
        eventos = get_eventos(fecha_desde=c.desde, fecha_hasta=c.hasta - timedelta(seconds=1),
                              municipio=c.municipio, limit=1000)
    salida = []
    for ev in eventos:
        if not _pasa_filtros(ev, c, ahora):
            continue
        p = _puntaje(ev, c)
        if p:
            salida.append((p, ev))
    en_curso = lambda e: bool(_inicio(e) and _inicio(e) < c.desde)  # noqa: E731
    # Primero lo que más coincide (en franjas, para no romper el orden por fecha), luego lo más próximo
    salida.sort(key=lambda x: (-(x[0] // 2), en_curso(x[1]), bool(c.franja) and not x[1].get("hora_confirmada"),
                               _inicio(x[1]) or c.hasta,
                               not x[1].get("imagen_url")))
    return [e for _, e in salida[:limite]], len(salida)


def _fecha_corta(d: datetime) -> str:
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def _linea(ev: dict, desde: Optional[datetime] = None) -> str:
    ini = _inicio(ev)
    fin = _inicio({"fecha_inicio": ev.get("fecha_fin")}) if ev.get("fecha_fin") else None
    if ini and desde and ini < desde and fin:
        cuando = f"en curso hasta el {_fecha_corta(fin)}"
    elif ini:
        cuando = f"{DIAS[ini.weekday()]} {ini.day} {MESES[ini.month - 1]}"
        if ev.get("hora_confirmada"):
            cuando += f", {ini.hour % 12 or 12}:{ini.minute:02d} {'a. m.' if ini.hour < 12 else 'p. m.'}"
    else:
        cuando = "fecha por confirmar"
    lugar = ev.get("nombre_lugar") or ev.get("barrio") or ""
    precio = "Gratis" if ev.get("es_gratuito") else (ev.get("precio") or "")
    if "null" in str(precio).lower() or "none" in str(precio).lower():
        precio = ""
    partes = [x for x in (lugar, precio) if x and x != "Consultar"]
    return f"• {cuando} — {ev.get('titulo', '').strip()}" + (f" · {' · '.join(partes)}" if partes else "")


def _descripcion_consulta(c: Consulta) -> str:
    que = " y ".join(c.tipos) if c.tipos else (f"«{' '.join(c.palabras)}»" if c.palabras else "")
    que = (f"de {que}" if que else "") + (" gratis" if c.gratis else "")
    if c.precio_max and not c.gratis:
        que += f" de hasta ${c.precio_max:,}".replace(",", ".")
    if c.publico:
        que += {"pareja": " para ir en pareja", "amigos": " para ir con amigos"}.get(c.publico, f" para {c.publico}")
    if c.virtual:
        que += " virtuales"
    cuando = c.etiqueta + (f" {c.franja[2]}" if c.franja and c.franja[2] not in c.etiqueta else "")
    donde = ""
    if c.cerca and c.ubicacion:
        donde = " cerca de vos"
    elif c.lugar:
        donde = f" en {c.lugar.get('nombre')}"
    elif c.zona:
        donde = f" en {c.zona[0]}"
    elif c.barrio:
        donde = f" en {c.barrio.title()}"
    elif c.municipio:
        donde = f" en {MUNICIPIO_VISIBLE.get(c.municipio, c.municipio.title())}"
    else:
        donde = " en el Valle de Aburrá"
    return f"{que} para {cuando}{donde}".strip()


AYUDA = ("Decime qué te provoca y cuándo, y te muestro planes reales de la agenda. Por ejemplo: "
         "«teatro este finde», «conciertos gratis hoy», «talleres en Envigado», «cine el sábado» "
         "o «qué hay cerca» (si compartís tu ubicación).")


def responder(mensaje: str, mensajes_previos: list[str], ahora: Optional[datetime] = None) -> tuple[str, list[dict]]:
    ahora = ahora or datetime.now(CO_TZ)
    c = entender(mensaje, ahora)
    saludo = re.search(r"\b(hola|buenas|buenos dias|hey|que mas|quien eres|quien sos|ayuda|como funciona|gracias)\b",
                       _n(mensaje))
    if saludo and c.vacia:
        return "Hola, soy ETÉREA. " + AYUDA, []
    # Solo un seguimiento ("¿y gratis?", "y en Envigado?") hereda lo que faltó del mensaje anterior
    if mensajes_previos and re.match(r"^\s*[¿¡]?\s*(y|e|tambien|entonces)\b", mensaje.lower()):
        c = heredar(c, entender(mensajes_previos[-1], ahora))
    if c.vacia:
        c.etiqueta = "hoy"
        c.hasta = _dia(ahora) + timedelta(days=1)
    if c.cerca and not c.ubicacion:
        return ("Para buscar cerca necesito tu ubicación: tocá «📍 Cerca de mí» en la agenda, "
                "o decime el barrio o municipio (por ejemplo «teatro en Laureles»)."), []

    eventos, total = buscar(c, ahora)
    if eventos:
        intro = f"Encontré {total} {'plan' if total == 1 else 'planes'} {_descripcion_consulta(c)}."
        if total > len(eventos):
            intro += f" Te muestro los {len(eventos)} que más coinciden:"
        return intro + "\n" + "\n".join(_linea(e, c.desde) for e in eventos), eventos

    # Nada en esa ventana: ampliar a 30 días antes de rendirse
    amplia = Consulta(**{**c.__dict__})
    amplia.desde, amplia.hasta, amplia.desde_hora = _dia(ahora), _dia(ahora) + timedelta(days=30), None
    amplia.etiqueta = "los próximos 30 días"
    eventos, total = buscar(amplia, ahora)
    if eventos:
        return (f"No encontré planes {_descripcion_consulta(c)}. En {amplia.etiqueta} sí hay {total}:\n"
                + "\n".join(_linea(e, amplia.desde) for e in eventos)), eventos
    return (f"No encontré planes {_descripcion_consulta(c)} en la agenda. Probá con otra fecha, otro municipio "
            "o un tipo de plan más general (música, teatro, talleres, cine)."), []
