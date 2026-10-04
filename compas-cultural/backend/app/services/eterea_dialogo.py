"""
ETÉREA: árbol de decisión determinista ("ars combinatoria") sobre la agenda real.

Cada mensaje se descompone en ejes (ver eterea_lexico) y un árbol ordenado decide la acción:

  1. SOCIAL        saludo, gracias, despedida, ¿quién sos?, ¿qué podés hacer?, insulto, chiste
  2. SITIO         publicar evento, registrar espacio, boletín, cuenta, app, aportes, mapa, datos…
  3. REFERENCIA    "¿a qué hora es el segundo?", "¿dónde queda ese?" → sobre la lista anterior
  4. LUGAR         "¿dónde queda Otraparte?", "instagram de Casa Teatro", "qué hay en el MAMM"
  5. DETALLE       "¿cuánto vale el festival de flamenco?" (evento nombrado + campo)
  6. LUGARES       "¿dónde hay teatros en Envigado?", "colectivos de hip hop en Bello"
  7. CONTAR        "¿cuántos conciertos hay este finde?"
  8. RECOMENDAR    "sorprendeme", "estoy aburrido", "plan para una cita el sábado"
  9. FUERA DE TEMA clima, fútbol, política… (si no hay nada cultural en la pregunta)
 10. EVENTOS       todo lo demás: QUÉ × CUÁNDO × DÓNDE × CUÁNTO × PARA QUIÉN

La combinación de ejes da decenas de miles de preguntas distintas con la misma maquinaria.
Cero tokens: solo reglas, la base de datos y plantillas.
"""
from __future__ import annotations

import hashlib
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.services import eterea_datos as D
from app.services import eterea_lexico as L
from app.services.eterea_buscador import (
    AYUDA, CO_TZ, DIAS, MESES, MUNICIPIO_VISIBLE, TIPOS, Consulta, _descripcion_consulta, _dia, _fecha_corta,
    _inicio, _linea, buscar, entender, heredar,
)

SITIO_WEB = "https://www.culturaetereamed.com"
ROLES_ASISTENTE = ("compas", "asistente", "assistant", "eterea", "bot")


@dataclass
class Turno:
    texto: str
    eventos: list[dict] = field(default_factory=list)
    espacios: list[dict] = field(default_factory=list)
    accion: str = ""


def _elige(opciones: tuple[str, ...] | list[str], semilla: str) -> str:
    """Variedad sin azar real: la misma pregunta da la misma frase, preguntas distintas varían."""
    h = int(hashlib.md5(semilla.encode()).hexdigest(), 16)
    return opciones[h % len(opciones)]


def _hora_txt(d: datetime) -> str:
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"


def _fecha_larga(d: datetime) -> str:
    nombres = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
    return f"{nombres[d.weekday()]} {d.day} de {meses[d.month - 1]}"


def _maps(lat, lng, nombre: str = "") -> Optional[str]:
    if lat is None or lng is None:
        return None
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"


def _municipio_txt(m: Optional[str]) -> str:
    m = (m or "").strip()
    return MUNICIPIO_VISIBLE.get(L.norm(m).replace(" ", "_"), m.title() if m.islower() else m)


# ─── Historial: qué se mostró antes ──────────────────────────────────────

def _ultima_lista(historial: list[tuple[str, str]]) -> tuple[str, list[dict]]:
    """Recupera la última lista que mostró ETÉREA ('eventos' o 'lugares') a partir de sus viñetas."""
    for rol, texto in reversed(historial):
        if rol not in ROLES_ASISTENTE or "•" not in (texto or ""):
            continue
        titulos_ev = {L.norm(e.get("titulo")): e for e in D.eventos_proximos()}
        nombres_lu = {L.norm(l.get("nombre")): l for l in D.lugares()}
        eventos, lugares = [], []
        for linea in texto.splitlines():
            if not linea.strip().startswith("•"):
                continue
            cuerpo = linea.strip().lstrip("•").strip()
            if " — " in cuerpo:
                titulo = cuerpo.split(" — ", 1)[1].split(" · ")[0]
                ev = titulos_ev.get(L.norm(titulo))
                if ev:
                    eventos.append(ev)
                    continue
            nombre = re.split(r" — | · | \(", cuerpo)[0]
            lu = nombres_lu.get(L.norm(nombre))
            if lu:
                lugares.append(lu)
        if eventos:
            return "eventos", eventos
        if lugares:
            return "lugares", lugares
    return "", []


def _foco(historial: list[tuple[str, str]]) -> tuple[str, Optional[dict]]:
    """El evento o lugar del que se acaba de hablar (última respuesta de ETÉREA con una sola ficha)."""
    for rol, texto in reversed(historial):
        if rol not in ROLES_ASISTENTE:
            continue
        texto = texto or ""
        m = re.search(r"/evento/([\w-]+)", texto)
        if m and texto.count("/evento/") == 1:
            ev = next((e for e in D.eventos_proximos() if e.get("slug") == m.group(1)), None)
            if ev:
                return "evento", ev
        m = re.search(r"«([^»]+)»", texto)
        if m and "•" not in texto.split("\n", 1)[0]:
            titulo = L.norm(m.group(1))
            ev = next((e for e in D.eventos_proximos() if L.norm(e.get("titulo")) == titulo), None)
            if ev:
                return "evento", ev
        m = re.search(r"/espacio/([\w-]+)", texto)
        if m and texto.count("/espacio/") == 1:
            lu = next((l for l in D.lugares() if l.get("slug") == m.group(1)), None)
            if lu:
                return "lugar", lu
        primera = L.norm(texto.split("\n", 1)[0])
        lu = next((l for l in D.lugares() if L.norm(l.get("nombre")) and primera.startswith(L.norm(l.get("nombre")))),
                  None)
        if lu:
            return "lugar", lu
        return "", None  # solo mira la última respuesta
    return "", None


def _referencia(t: str, n: int) -> Optional[int]:
    """'el segundo' → 1, 'ese' (si solo hay uno) → 0, 'el último' → n-1."""
    palabras = [k for k in L.ORDINALES if not k.isdigit() and k not in ("uno", "dos", "tres")]
    m = re.search(r" (" + "|".join(palabras) + r") ", t) or \
        re.search(r" (?:el|la|del|de la|numero|opcion|#) (1|2|3|4|5|6|uno|dos|tres) ", t)
    if m:
        i = L.ORDINALES[m.group(1)]
        return i if i < n else None
    if L.hay(t, "el ultimo", "la ultima", "ultimo", "ultima"):
        return n - 1
    if L.hay(t, *L.DEICTICOS) and n >= 1:
        return 0
    return None


# ─── Campos ──────────────────────────────────────────────────────────────

def _campo(t: str, tabla: dict) -> Optional[str]:
    mejor, largo = None, 0
    for campo, frases in tabla.items():
        for f in frases:
            if f" {f} " in t and len(f) > largo:
                mejor, largo = campo, len(f)
    return mejor


def _enlace_entradas(ev: dict) -> Optional[str]:
    m = re.search(r"(https?://\S+)", ev.get("descripcion") or "")
    return m.group(1).rstrip(".,)") if m else None


def detalle_evento(ev: dict, campo: Optional[str]) -> str:
    titulo = (ev.get("titulo") or "").strip()
    ini = _inicio(ev)
    fin = _inicio({"fecha_inicio": ev.get("fecha_fin")}) if ev.get("fecha_fin") else None
    ficha = f"{SITIO_WEB}/evento/{ev.get('slug') or ev.get('id')}"
    lugar = ev.get("nombre_lugar") or "un lugar por confirmar"
    donde = ", ".join(x for x in (lugar, ev.get("barrio"), _municipio_txt(ev.get("municipio"))) if x)
    precio = "Es gratis." if ev.get("es_gratuito") else (
        f"Precio: {ev['precio']}." if ev.get("precio") and ev.get("precio") not in ("Consultar",) else
        "No tengo el precio confirmado.")
    hoy = _dia(datetime.now(CO_TZ))
    if ini and ini < hoy and fin:
        cuando = f"está en curso hasta el {_fecha_larga(fin)}"
    elif ini:
        cuando = f"es el {_fecha_larga(ini)}" + (f" a las {_hora_txt(ini)}" if ev.get("hora_confirmada") else "")
    else:
        cuando = "no tiene fecha confirmada"
    mapa = _maps(ev.get("lat"), ev.get("lng"))
    entradas = _enlace_entradas(ev) or ev.get("fuente_url")

    if campo == "hora":
        if ini and ev.get("hora_confirmada"):
            return f"«{titulo}» empieza a las {_hora_txt(ini)} el {_fecha_larga(ini)}, en {lugar}.\nFicha: {ficha}"
        return (f"«{titulo}» {cuando}, pero la hora no está confirmada en la fuente. "
                f"Revisala acá: {entradas or ficha}")
    if campo == "fecha":
        return f"«{titulo}» {cuando}, en {lugar}.\nFicha: {ficha}"
    if campo == "lugar":
        return f"«{titulo}» es en {donde}." + (f"\nCómo llegar: {mapa}" if mapa else "") + f"\nFicha: {ficha}"
    if campo == "precio":
        return f"«{titulo}»: {precio}" + (f" Entradas o más info: {entradas}" if entradas else "")
    if campo == "entradas":
        if entradas:
            return f"Para «{titulo}», las entradas o la inscripción están acá: {entradas}\n{precio}"
        return f"No tengo enlace de entradas para «{titulo}». {precio} Mirá la ficha: {ficha}"
    if campo == "llegar":
        if mapa:
            return f"«{titulo}» es en {donde}.\nRuta en Google Maps: {mapa}"
        return f"«{titulo}» es en {donde}. No tengo la ubicación exacta en el mapa todavía."
    if campo == "duracion":
        if fin:
            return f"«{titulo}» va hasta el {_fecha_larga(fin)}" + (
                f" a las {_hora_txt(fin)}." if fin.hour or fin.minute else ".")
        return f"No tengo la hora de cierre de «{titulo}». {cuando[0].upper() + cuando[1:]}."
    if campo == "publico":
        desc = ev.get("descripcion") or ""
        m = re.search(r"P[uú]blico:\s*([^·\n]+)", desc)
        if m:
            return f"«{titulo}» está pensado para: {m.group(1).strip()}."
        return f"La fuente no dice para qué público es «{titulo}». Mirá la ficha: {ficha}"
    # Ficha completa (o "de qué se trata")
    desc = re.sub(r"\s+", " ", (ev.get("descripcion") or "")).strip()
    desc = re.sub(r"(Inscripción o entradas|P[uú]blico|Modalidad):[^·]*·?", "", desc).strip(" ·")
    partes = [f"«{titulo}»", f"• Cuándo: {cuando}", f"• Dónde: {donde}", f"• {precio}"]
    if desc:
        partes.append(f"• De qué se trata: {desc[:380]}{'…' if len(desc) > 380 else ''}")
    if entradas:
        partes.append(f"• Entradas o inscripción: {entradas}")
    if mapa:
        partes.append(f"• Cómo llegar: {mapa}")
    partes.append(f"Ficha: {ficha}")
    return "\n".join(partes)


def detalle_lugar(l: dict, campo: Optional[str]) -> str:
    nombre = l.get("nombre")
    donde = ", ".join(x for x in (l.get("direccion"), l.get("barrio"), _municipio_txt(l.get("municipio"))) if x)
    mapa = _maps(l.get("lat"), l.get("lng"))
    ig = l.get("instagram_handle")
    ig_txt = f"@{ig.lstrip('@')} (https://instagram.com/{ig.lstrip('@')})" if ig and "http" not in ig else ig
    ficha = f"{SITIO_WEB}/espacio/{l.get('slug')}" if l.get("slug") else None
    if campo == "direccion":
        return f"{nombre} queda en {donde or 'una dirección que no tengo registrada'}." + (
            f"\nRuta en Google Maps: {mapa}" if mapa else "")
    if campo == "llegar":
        return (f"Ruta a {nombre}: {mapa}" if mapa else f"No tengo la ubicación exacta de {nombre}.") + (
            f"\nDirección: {donde}" if donde else "")
    if campo == "instagram":
        return f"El Instagram de {nombre} es {ig_txt}." if ig else f"No tengo el Instagram de {nombre}."
    if campo == "web":
        return f"La página de {nombre}: {l['sitio_web']}" if l.get("sitio_web") else \
            f"No tengo página web de {nombre}" + (f"; su Instagram es {ig_txt}." if ig else ".")
    if campo == "telefono":
        return f"El teléfono de {nombre}: {l['telefono']}" if l.get("telefono") else \
            f"No tengo el teléfono de {nombre}" + (f"; podés escribirles por Instagram: {ig_txt}." if ig else ".")
    if campo == "horario":
        return (f"No tengo el horario de {nombre} registrado. Te recomiendo confirmarlo en "
                + (ig_txt or l.get("sitio_web") or "sus redes") + ".")
    partes = [f"{nombre}"]
    if l.get("descripcion_corta"):
        partes.append(l["descripcion_corta"])
    if donde:
        partes.append(f"• Dónde: {donde}")
    if ig:
        partes.append(f"• Instagram: {ig_txt}")
    if l.get("sitio_web"):
        partes.append(f"• Web: {l['sitio_web']}")
    if mapa:
        partes.append(f"• Cómo llegar: {mapa}")
    if ficha:
        partes.append(f"Ficha: {ficha}")
    return "\n".join(partes)


# ─── Encontrar un evento nombrado en la pregunta ─────────────────────────

_VACIAS_TITULO = L.VACIAS_EXTRA | {"festival", "taller", "concierto", "evento", "obra", "exposicion", "charla"}


def eventos_nombrados(t: str) -> list[dict]:
    """Eventos próximos cuyo título se parece a la pregunta (≥2 palabras o ≥50 %), del más parecido al menos.
    Varias funciones del mismo título cuentan como una (la más próxima)."""
    palabras = {w for w in t.split() if len(w) >= 4 and w not in L.VACIAS_EXTRA and w not in L.PALABRAS_DE_CONTROL}
    if not palabras:
        return []
    candidatos: dict[str, tuple[float, dict]] = {}
    for ev in D.eventos_proximos():
        tit = {w for w in L.norm(ev.get("titulo")).split() if len(w) >= 4}
        if not tit:
            continue
        comunes = palabras & tit
        if not {w for w in comunes if w not in _VACIAS_TITULO and len(w) >= 5}:
            continue
        p = len(comunes) / len(tit) + 0.15 * len(comunes)
        if len(comunes) < 2 and p < 0.5:
            continue
        clave = L.norm(ev.get("titulo"))
        previo = candidatos.get(clave)
        if not previo or p > previo[0] or (p == previo[0] and (_inicio(ev) or datetime.max.replace(tzinfo=CO_TZ))
                                           < (_inicio(previo[1]) or datetime.max.replace(tzinfo=CO_TZ))):
            candidatos[clave] = (p, ev)
    return [ev for _, ev in sorted(candidatos.values(), key=lambda x: -x[0])]


def evento_en(t: str) -> Optional[dict]:
    lista = eventos_nombrados(t)
    return lista[0] if lista else None


# ─── Lugares ─────────────────────────────────────────────────────────────

def _tipo_lugar(t: str) -> Optional[str]:
    for nombre, disparadores in L.DISPARA_TIPO_LUGAR.items():
        if L.hay(t, *disparadores):
            return nombre
    return None


def buscar_lugares(t: str, c: Consulta, tipo_lugar: Optional[str], limite: int = 8) -> list[dict]:
    from app.services.ml_utils import haversine_km
    tipos_db, raices = L.TIPOS_LUGAR.get(tipo_lugar or "", (set(), ()))
    cats_plan = set()
    raices_plan: tuple[str, ...] = ()
    for nombre in c.tipos:
        cats_plan |= TIPOS[nombre][0]
        raices_plan += TIPOS[nombre][1]
    salida = []
    for l in D.lugares():
        nombre = L.norm(l.get("nombre"))
        desc = L.norm(l.get("descripcion_corta"))
        if tipos_db or raices:
            if l.get("tipo") not in tipos_db and l.get("categoria_principal") not in tipos_db \
                    and not any(f" {r.strip()}" in f" {nombre} " for r in raices):
                continue
        if cats_plan or raices_plan:
            if l.get("categoria_principal") not in cats_plan and not any(r in f"{nombre} {desc}" for r in raices_plan):
                continue
        if c.municipio and L.norm(l.get("municipio")).replace(" ", "_") != c.municipio:
            continue
        if c.zona and L.norm(l.get("barrio")) not in c.zona[1]:
            continue
        if c.barrio and c.barrio not in L.norm(f"{l.get('barrio')} {l.get('nombre')}"):
            continue
        p = 1 + (2 if l.get("lat") else 0) + (1 if l.get("instagram_handle") else 0) + \
            (1 if l.get("descripcion_corta") else 0)
        for w in c.palabras:
            if w in nombre:
                p += 4
            elif w in desc:
                p += 2
        if c.ubicacion and l.get("lat"):
            d = haversine_km(c.ubicacion[0], c.ubicacion[1], float(l["lat"]), float(l["lng"]))
            if c.cerca and d > 6:
                continue
            p += max(0, 6 - d)
        salida.append((p, l))
    salida.sort(key=lambda x: (-x[0], L.norm(x[1].get("nombre"))))
    return [l for _, l in salida[:limite]]


def _linea_lugar(l: dict) -> str:
    partes = []
    for x in (l.get("barrio"), _municipio_txt(l.get("municipio"))):
        if x and L.norm(x) not in {L.norm(p) for p in partes}:
            partes.append(x)
    donde = ", ".join(partes)
    ig = l.get("instagram_handle")
    extra = f" · @{ig.lstrip('@')}" if ig and "http" not in ig else ""
    return f"• {l.get('nombre')}" + (f" — {donde}" if donde else "") + extra


# ─── Recomendación ───────────────────────────────────────────────────────

def recomendar(c: Consulta, semilla: str, n: int = 3) -> list[dict]:
    candidatos, _ = buscar(c, limite=300)
    if not candidatos:
        return []

    def calidad(e):
        en_curso = bool(_inicio(e) and _inicio(e) < c.desde)
        return (2 if e.get("imagen_url") else 0) + (2 if e.get("hora_confirmada") else 0) + \
               (1 if e.get("es_gratuito") else 0) + (1 if 8 <= len(e.get("titulo") or "") <= 70 else 0) - \
               (3 if en_curso else 0)
    candidatos.sort(key=calidad, reverse=True)
    top = candidatos[:20]
    rnd = random.Random(int(hashlib.md5(semilla.encode()).hexdigest(), 16))
    rnd.shuffle(top)
    elegidos, cats, sitios = [], set(), set()
    for e in top:
        cat, sitio = e.get("categoria_principal"), L.norm(e.get("nombre_lugar"))
        if cat in cats or sitio in sitios:
            continue
        elegidos.append(e)
        cats.add(cat)
        sitios.add(sitio)
        if len(elegidos) == n:
            break
    for e in top:  # si no alcanzó con variedad, completar
        if len(elegidos) == n:
            break
        if e not in elegidos:
            elegidos.append(e)
    return sorted(elegidos, key=lambda e: _inicio(e) or c.hasta)


# ─── El árbol ────────────────────────────────────────────────────────────

def _lista(eventos: list[dict], desde: datetime) -> str:
    return "\n".join(_linea(e, desde) for e in eventos)


CIERRES = ("¿Querés saber más de alguno? Decime «el primero», «el segundo»…",
           "Preguntame por cualquiera: «¿a qué hora es el segundo?», «¿dónde queda el primero?».",
           "Si te interesa uno, preguntame la hora, el precio o cómo llegar.")


def _social(t: str, semilla: str) -> Optional[str]:
    solo = len(t.split()) <= 6
    if L.hay(t, *L.INSULTOS):
        return ("Perdón si no te ayudé bien. Probá decirme qué plan buscás y cuándo, por ejemplo "
                "«teatro gratis este finde» o «talleres en Bello mañana», y lo intento de nuevo.")
    if L.hay(t, *L.QUIEN_ERES):
        return ("Soy ETÉREA, la guía de Cultura Etérea. No soy una inteligencia artificial que inventa: "
                "busco en la agenda cultural real del Valle de Aburrá (más de 900 espacios y colectivos) "
                "y te respondo con lo que hay. " + AYUDA)
    if L.hay(t, *L.QUE_PUEDES):
        return ("Puedo:\n• Buscar planes por tipo, fecha, hora, barrio o municipio, precio y público "
                "(«jazz el viernes en la noche», «talleres para niños en Envigado», «planes de menos de 20 mil»).\n"
                "• Recomendarte algo («sorprendeme», «plan para una cita el sábado»).\n"
                "• Contarte detalles («¿a qué hora es el segundo?», «¿cuánto vale el festival de flamenco?»).\n"
                "• Darte datos de un lugar («¿dónde queda Otraparte?», «instagram de Casa Teatro»).\n"
                "• Listar lugares («teatros en Itagüí», «colectivos de hip hop en Bello»).\n"
                "• Contar («¿cuántos conciertos hay este finde?»).")
    if L.hay(t, *L.CHISTE):
        return _elige(("¿Por qué el libro de matemáticas fue al teatro? Porque tenía muchos problemas y quería "
                       "verlos en escena. 😄 ¿Te busco una obra de verdad?",
                       "Un músico entra a una biblioteca y pide silencio… para afinar. 🎻 ¿Te muestro conciertos?"),
                      semilla)
    if solo and L.hay(t, *L.GRACIAS):
        return _elige(("¡Con gusto! Que lo disfrutés. 🙌", "¡A la orden! Si querés otro plan, acá estoy.",
                       "¡De nada! Contame si buscás algo más."), semilla)
    if solo and L.hay(t, *L.DESPEDIDAS):
        return _elige(("¡Chao! Que tengás un buen plan. ✨", "¡Nos vemos! Volvé cuando querás otro plan."), semilla)
    if solo and L.hay(t, *L.COMO_ESTAS):
        return "¡Muy bien, con la agenda llena! ¿Qué te provoca hoy: música, teatro, cine o algo gratis?"
    if solo and L.hay(t, *L.SALUDOS):
        return _elige(("¡Hola! Soy ETÉREA. ", "¡Hola, qué más! Soy ETÉREA. ", "¡Buenas! Acá ETÉREA. "),
                      semilla) + AYUDA
    return None


def _sitio(t: str) -> Optional[str]:
    for clave, (frases, ruta) in L.SITIO.items():
        if not L.hay(t, *frases):
            continue
        if clave == "mapa" and len(t.split()) > 4:
            continue  # "¿en el mapa dónde queda…?" no es una pregunta por la página del mapa
        if clave == "app" and len(t.split()) > 6:
            continue
        textos = {
            "publicar": "Podés publicar tu evento gratis acá: {u}. Lo revisamos y sale en la agenda y el mapa.",
            "registrar": "Registrá tu espacio o colectivo acá: {u}. Así aparece en el mapa y su agenda se suma sola.",
            "boletin": ("El boletín llega a quienes tienen cuenta: los lunes con la agenda de esta semana y la "
                        "próxima, y los viernes con el plan del finde. Creá tu cuenta acá: {u}"),
            "baja": ("Cada boletín trae al final el enlace «darme de baja»: con un clic dejás de recibirlo. "
                     "Si no lo encontrás, escribinos desde la página Nosotros."),
            "cuenta": "Entrá o creá tu cuenta acá: {u}. Si olvidaste la contraseña, en esa misma página podés recuperarla.",
            "eliminar_cuenta": "Podés eliminar tu cuenta y tus datos acá: {u}",
            "guardados": "Tus planes guardados están acá: {u}. En cada evento tocá el ♡ para guardarlo.",
            "app": "La app para Android se descarga acá: {u}. También podés instalar la web en tu celular.",
            "aportar": "¡Gracias por querer apoyar! Acá podés aportar al proyecto: {u}",
            "nosotros": "Cultura Etérea es una agenda y mapa cultural vivo del Valle de Aburrá. Conocé el proyecto: {u}",
            "mapa": "El mapa cultural está acá: {u}. Muestra los espacios y los eventos de los próximos días.",
            "privacidad": "Nuestra política de protección de datos (Ley 1581) está acá: {u}",
            "contacto": ("Para escribirnos o reportar un error, entrá a {u}. Si un evento tiene un dato malo, "
                         "contanos cuál y lo corregimos."),
        }
        return textos[clave].format(u=f"{SITIO_WEB}{ruta}" if ruta else SITIO_WEB)
    return None


def _ubicar(c: Consulta, t: str) -> None:
    """Completa DÓNDE con datos de la base: lugar nombrado o zona/comuna."""
    if not c.lugar:
        c.lugar = D.lugar_en(t)
    if not c.lugar and not c.zona:
        zona = D.zona_en(t)
        if zona:  # la zona (comuna) es más útil que el barrio exacto: pocos eventos traen barrio
            c.zona, c.barrio = zona, None


def responder(mensaje: str, historial: Optional[list[tuple[str, str]]] = None,
              ahora: Optional[datetime] = None) -> Turno:
    ahora = ahora or datetime.now(CO_TZ)
    historial = historial or []
    crudo = mensaje or ""
    t = f" {L.norm(re.sub(r'\[[^\]]*\]', ' ', crudo))} "
    semilla = f"{t}{ahora.date()}"
    previos = [txt for rol, txt in historial if rol not in ROLES_ASISTENTE]

    # 1. SOCIAL
    social = _social(t, semilla)
    if social:
        return Turno(social, accion="social")

    # 2. SITIO
    sitio = _sitio(t)
    if sitio:
        return Turno(sitio, accion="sitio")

    c = entender(crudo, ahora)
    if previos and re.match(r"^\s*[¿¡]?\s*(y|e|tambien|entonces|pero)\b", crudo.lower()):
        c = heredar(c, entender(previos[-1], ahora))
    campo_ev = _campo(t, L.CAMPOS_EVENTO)
    campo_lu = _campo(t, L.CAMPOS_LUGAR)

    # 3. REFERENCIA a la lista anterior
    tipo_lista, lista = _ultima_lista(historial)
    if lista:
        i = _referencia(t, len(lista))
        if i is not None and (campo_ev or campo_lu or len(t.split()) <= 6 or L.hay(t, *L.DEICTICOS)):
            item = lista[i]
            if tipo_lista == "eventos":
                return Turno(detalle_evento(item, campo_ev), eventos=[item], accion="detalle_ref")
            return Turno(detalle_lugar(item, campo_lu), espacios=[item], accion="lugar_ref")

    lugar = D.lugar_en(t)
    pide_detalle = campo_ev or L.hay(t, "info", "informacion", "detalles", "cuentame", "contame")
    nombrados = eventos_nombrados(t) if pide_detalle else []

    tipo_lugar = _tipo_lugar(t)
    plural_lugar = re.search(r" (teatros|bibliotecas|museos|galerias|colectivos|bares|librerias|editoriales|uvas|"
                             r"casas de la cultura|centros culturales|universidades|parques|cafes|grupos|"
                             r"agrupaciones|academias|escuelas) ", t)
    # "¿dónde puedo ver teatro hoy?" pide eventos; "¿dónde hay teatros?" pide lugares
    pregunta_lugares = bool((L.hay(t, *L.LUGARES_PREGUNTA) and not (c.fecha_explicita and not plural_lugar))
                            or plural_lugar)

    # 3b. FOCO: "¿y cuánto vale?", "¿dónde queda?" sobre lo último que se mostró
    if (campo_ev or campo_lu) and not lugar and not nombrados and not c.tipos and not pregunta_lugares             and len(t.split()) <= 7:
        tipo_foco, foco = _foco(historial)
        if tipo_foco == "evento":
            return Turno(detalle_evento(foco, campo_ev or "descripcion"), eventos=[foco], accion="detalle_foco")
        if tipo_foco == "lugar":
            return Turno(detalle_lugar(foco, campo_lu), espacios=[foco], accion="lugar_foco")
        if not (c.fecha_explicita or c.municipio or c.zona or c.palabras):
            return Turno("¿De cuál evento o lugar? Decime el nombre (por ejemplo «¿a qué hora es el Festival "
                         "Flamenco?» o «¿dónde queda Otraparte?») o pedime una lista y elegí uno.", accion="aclarar")

    # 4. LUGAR nombrado
    ev_nombrado = nombrados[0] if nombrados else None
    if len(nombrados) > 1 and not lugar:
        # Varios títulos parecidos: que la persona elija
        opciones = nombrados[:4]
        return Turno("Encontré varios con ese nombre. ¿Cuál?\n" + _lista(opciones, _dia(ahora))
                     + "\nDecime «el primero», «el segundo»…", eventos=opciones, accion="desambiguar")
    if lugar and not ev_nombrado:
        pide_eventos = L.hay(t, "que hay", "eventos", "programacion", "agenda", "planes", "que tienen",
                             "que va a haber", "que presentan", "cartelera") or c.fecha_explicita or c.tipos
        if campo_lu and not pide_eventos:
            return Turno(detalle_lugar(lugar, campo_lu), espacios=[lugar], accion="lugar_info")
        c.lugar = lugar
        if not c.fecha_explicita:
            c.hasta = _dia(ahora) + timedelta(days=30)
            c.etiqueta = "los próximos 30 días"
        eventos, total = buscar(c)
        if eventos:
            texto = (f"En {lugar.get('nombre')} hay {total} {'plan' if total == 1 else 'planes'} "
                     f"para {c.etiqueta}:\n{_lista(eventos, c.desde)}\n{_elige(CIERRES, semilla)}")
            return Turno(texto, eventos=eventos, accion="eventos_lugar")
        return Turno(f"No tengo planes registrados en {lugar.get('nombre')} para {c.etiqueta}.\n\n"
                     + detalle_lugar(lugar, None), espacios=[lugar], accion="lugar_info")

    # 5. DETALLE de un evento nombrado
    if ev_nombrado:
        return Turno(detalle_evento(ev_nombrado, campo_ev), eventos=[ev_nombrado], accion="detalle")

    _ubicar(c, t)

    # 6. LUGARES
    if pregunta_lugares:
        lugares = buscar_lugares(t, c, tipo_lugar, limite=min(c.limite if c.limite != 6 else 8, 12))
        que = tipo_lugar or (" y ".join(c.tipos) and f"lugares de {' y '.join(c.tipos)}") or "lugares culturales"
        donde = (f" en {c.zona[0]}" if c.zona else f" en {c.barrio.title()}" if c.barrio else
                 f" en {MUNICIPIO_VISIBLE.get(c.municipio, (c.municipio or '').title())}" if c.municipio else
                 " cerca de vos" if c.cerca and c.ubicacion else " en el Valle de Aburrá")
        if lugares:
            encabezado = (f"Encontré este lugar{donde}:" if len(lugares) == 1
                          else f"Estos son {len(lugares)} {que}{donde}:")
            texto = (f"{encabezado}\n" + "\n".join(_linea_lugar(l) for l in lugares)
                     + "\nPreguntame por cualquiera: «¿dónde queda el primero?», «instagram del segundo».")
            return Turno(texto, espacios=lugares, accion="lugares")
        return Turno(f"No encontré {que}{donde} en el mapa. Probá con otro municipio o un tipo más general.",
                     accion="lugares")

    # 7. CONTAR
    if L.hay(t, *L.CONTAR):
        if c.vacia or not c.fecha_explicita:
            if not c.fecha_explicita:
                c.hasta, c.etiqueta = _dia(ahora) + timedelta(days=7), "los próximos 7 días"
        todos, total = buscar(c, limite=2000)
        if not total:
            return Turno(f"No hay planes {_descripcion_consulta(c)} en la agenda.", accion="contar")
        gratis = sum(1 for e in todos if e.get("es_gratuito"))
        cats = Counter(e.get("categoria_principal") for e in todos if e.get("categoria_principal"))
        nombres = {"musica_en_vivo": "música", "taller": "talleres", "conferencia": "charlas", "otro": "otros",
                   "arte_contemporaneo": "arte", "centro_cultural": "centro cultural", "galeria": "exposiciones",
                   "hip_hop": "hip hop", "poesia": "poesía", "electronica": "electrónica"}
        reparto = ", ".join(f"{n} de {nombres.get(k, k.replace('_', ' '))}" for k, n in cats.most_common(4))
        texto = (f"Hay {total} {'plan' if total == 1 else 'planes'} {_descripcion_consulta(c)}; "
                 f"{gratis} {'es gratis' if gratis == 1 else 'son gratis'}." + (f"\nPor tipo: {reparto}." if reparto else "")
                 + "\n¿Querés que te muestre algunos?")
        return Turno(texto, accion="contar")

    # 8. RECOMENDAR
    if L.hay(t, *L.RECOMENDAR) or c.publico == "pareja":
        if c.publico == "pareja":
            c.publico = None
            if not c.tipos:
                c.tipos = list(L.TIPOS_PAREJA)
            if not c.franja:
                c.franja = (17, 24, "en la noche")
        if not c.fecha_explicita:
            c.hasta, c.etiqueta = _dia(ahora) + timedelta(days=2), "hoy y mañana"
        n = c.limite if c.limite != 6 else 3
        elegidos = recomendar(c, semilla, n)
        if not elegidos:
            c.hasta, c.etiqueta = _dia(ahora) + timedelta(days=7), "esta semana"
            elegidos = recomendar(c, semilla, n)
        if elegidos:
            intro = _elige((f"Te propongo {'este plan' if len(elegidos) == 1 else f'estos {len(elegidos)} planes'} "
                            f"para {c.etiqueta}:",
                            f"Para {c.etiqueta}, yo iría a {'esto' if len(elegidos) == 1 else 'alguno de estos'}:",
                            f"Mirá {'este plan' if len(elegidos) == 1 else 'estos planes'} para {c.etiqueta}:"),
                           semilla)
            return Turno(f"{intro}\n{_lista(elegidos, c.desde)}\n{_elige(CIERRES, semilla)}", eventos=elegidos,
                         accion="recomendar")
        return Turno("No encontré planes que cumplan todo eso. Probá con menos condiciones o con otra fecha.",
                     accion="recomendar")

    # 9. FUERA DE TEMA
    if L.hay(t, *L.FUERA_DE_TEMA) and not (c.tipos or c.lugar or c.zona):
        hoy, _ = buscar(Consulta(desde=_dia(ahora), hasta=_dia(ahora) + timedelta(days=1), etiqueta="hoy",
                                 limite=3), ahora)
        texto = "De eso no sé: solo conozco la agenda cultural del Valle de Aburrá. 🙂"
        if hoy:
            texto += "\nPero mirá lo que hay hoy:\n" + _lista(hoy, _dia(ahora))
        return Turno(texto, eventos=hoy, accion="fuera_de_tema")

    # 10. EVENTOS (por defecto)
    if c.cerca and not c.ubicacion:
        return Turno("Para buscar cerca necesito tu ubicación: tocá «📍 Cerca de mí» en la agenda, o decime el "
                     "barrio o municipio (por ejemplo «teatro en Laureles»).", accion="eventos")
    no_entendi = c.vacia
    if no_entendi:
        c.etiqueta, c.hasta = "hoy", _dia(ahora) + timedelta(days=1)
        c.limite = 4
    eventos, total = buscar(c, ahora)
    if eventos:
        if no_entendi:
            intro = ("No estoy segura de qué buscás, pero esto es lo que hay hoy en el Valle de Aburrá:")
            pie = "\n" + AYUDA
        else:
            intro = f"Encontré {total} {'plan' if total == 1 else 'planes'} {_descripcion_consulta(c)}."
            if total > len(eventos):
                intro += f" Te muestro {'el que más coincide' if len(eventos) == 1 else f'los {len(eventos)} que más coinciden'}:"
            pie = "\n" + _elige(CIERRES, semilla)
        return Turno(f"{intro}\n{_lista(eventos, c.desde)}{pie}", eventos=eventos, accion="eventos")

    amplia = Consulta(**{**c.__dict__})
    amplia.desde, amplia.hasta, amplia.desde_hora = _dia(ahora), _dia(ahora) + timedelta(days=30), None
    amplia.etiqueta, amplia.franja = "los próximos 30 días", None
    eventos, total = buscar(amplia, ahora)
    if eventos:
        return Turno(f"No encontré planes {_descripcion_consulta(c)}. En {amplia.etiqueta} sí hay {total}:\n"
                     f"{_lista(eventos, amplia.desde)}", eventos=eventos, accion="eventos_ampliado")
    return Turno(f"No encontré planes {_descripcion_consulta(c)} en la agenda. Probá con otra fecha, otro municipio "
                 "o un tipo de plan más general (música, teatro, talleres, cine).", accion="sin_resultados")
