"""
Ars combinatoria de ETÉREA: miles de preguntas generadas cruzando los ejes
(QUÉ × CUÁNDO × DÓNDE × CUÁNTO × forma de preguntar) contra datos sintéticos.
Cada combinación debe entenderse bien y ninguna puede romper el árbol.
"""
import itertools
from datetime import datetime, timedelta

import pytest

from app.services import eterea_buscador as B
from app.services import eterea_datos as D
from app.services import eterea_dialogo as G

AHORA = datetime(2026, 10, 3, 9, 0, tzinfo=B.CO_TZ)  # sábado, 9 a. m.

LUGARES = [
    {"id": "l1", "nombre": "Casa Teatro El Poblado", "slug": "casa-teatro", "tipo": "teatro", "categoria_principal": "teatro",
     "municipio": "medellin", "barrio": "El Poblado", "direccion": "Calle 9 # 39-21", "lat": 6.2091, "lng": -75.5683,
     "instagram_handle": "casateatroelpoblado", "sitio_web": "https://casateatro.co", "telefono": None,
     "descripcion_corta": "Sala de teatro independiente.", "nivel_actividad": "activo"},
    {"id": "l2", "nombre": "Corporación Otraparte", "slug": "otraparte", "tipo": "centro_cultural",
     "categoria_principal": "centro_cultural", "municipio": "envigado", "barrio": "Centro", "direccion": "Cra 43A # 27A Sur-11",
     "lat": 6.1745, "lng": -75.5818, "instagram_handle": "otraparte", "sitio_web": None, "telefono": "3001234567",
     "descripcion_corta": "Casa museo de Fernando González.", "nivel_actividad": "activo"},
    {"id": "l3", "nombre": "Biblioteca Pública de Bello", "slug": "biblio-bello", "tipo": "biblioteca",
     "categoria_principal": "biblioteca", "municipio": "bello", "barrio": "Centro", "direccion": None, "lat": 6.3373,
     "lng": -75.5579, "instagram_handle": None, "sitio_web": None, "telefono": None, "descripcion_corta": None,
     "nivel_actividad": "activo"},
    {"id": "l4", "nombre": "Crew Hip Hop Niquía", "slug": "crew-niquia", "tipo": "colectivo", "categoria_principal": "hip_hop",
     "municipio": "bello", "barrio": "Niquía", "direccion": None, "lat": None, "lng": None, "instagram_handle": "crewniquia",
     "sitio_web": None, "telefono": None, "descripcion_corta": "Colectivo de hip hop y breaking.", "nivel_actividad": "activo"},
]
ZONAS = {"alias": {"laureles": ("Laureles Estadio (Comuna 11)", "11"), "san javier": ("San Javier (Comuna 13)", "13"),
                   "la candelaria": ("La Candelaria (Comuna 10)", "10"), "el poblado": ("El Poblado (Comuna 14)", "14")},
         "barrios": {"Laureles Estadio (Comuna 11)": {"laureles"}, "San Javier (Comuna 13)": {"san javier"},
                     "La Candelaria (Comuna 10)": {"la candelaria"}, "El Poblado (Comuna 14)": {"el poblado"}}}


def _ev(i, titulo, dias, hora, cat, lugar, municipio="medellin", gratis=True, precio=None, barrio=None, lat=6.25, lng=-75.57):
    ini = (AHORA.replace(hour=0, minute=0) + timedelta(days=dias)).replace(hour=hora or 0)
    return {"id": f"e{i}", "slug": f"ev-{i}", "titulo": titulo, "fecha_inicio": ini.isoformat(), "fecha_fin": None,
            "hora_confirmada": hora is not None, "categoria_principal": cat, "categorias": [cat],
            "nombre_lugar": lugar, "municipio": municipio, "barrio": barrio, "es_gratuito": gratis,
            "precio": precio or ("Gratis" if gratis else "$30.000"), "descripcion": f"{titulo}. Público: todo público.",
            "imagen_url": "https://x/img.jpg", "lat": lat, "lng": lng, "espacio_id": None, "fuente_url": "https://x"}


EVENTOS = [
    _ev(1, "Hamlet en versión clown", 0, 20, "teatro", "Casa Teatro El Poblado", barrio="El Poblado"),
    _ev(2, "Concierto de jazz latino", 1, 19, "jazz", "Teatro Pablo Tobón Uribe", gratis=False, precio="$25.000"),
    _ev(3, "Taller de cerámica para niños", 0, 10, "taller", "Biblioteca Pública de Bello", municipio="bello"),
    _ev(4, "Cineclub: El sueño de la sultana", 4, 18, "cine", "Corporación Otraparte", municipio="envigado"),
    _ev(5, "Noche de rock alternativo", 6, 21, "rock", "Bar La Tienda", gratis=False, precio="$15.000"),
    _ev(6, "Exposición: Formas de habitar", 2, None, "galeria", "Bodega Comfama", barrio="La Candelaria"),
    _ev(7, "Recital de poesía en el parque", 1, 16, "poesia", "Parque Biblioteca San Javier", barrio="San Javier"),
    _ev(8, "Batalla de freestyle hip hop", 5, 17, "hip_hop", "UVA San Fernando", municipio="itagui"),
    _ev(9, "Clase abierta de salsa", 3, 19, "danza", "Comfama Laureles", barrio="Laureles"),
    _ev(10, "Charla: astronomía para todos", 2, 18, "conferencia", "Planetario de Medellín"),
    _ev(11, "Festival de Halloween para la familia", 28, 15, "festival", "Parque de los Deseos"),
    _ev(12, "Obra de teatro: La casa de Bernarda Alba", 1, 19, "teatro", "Teatro Matacandelas", gratis=False, precio="$40.000"),
]


@pytest.fixture(autouse=True)
def datos_sinteticos(monkeypatch):
    D._CACHE.clear()
    monkeypatch.setattr(D, "lugares", lambda: LUGARES)
    monkeypatch.setattr(D, "zonas", lambda: ZONAS)
    monkeypatch.setattr(D, "eventos_proximos", lambda dias=60: EVENTOS)

    def get_eventos(fecha_desde=None, fecha_hasta=None, municipio=None, limit=1000, **_):
        out = []
        for e in EVENTOS:
            ini = B._inicio(e)
            if fecha_desde and ini < fecha_desde:
                continue
            if fecha_hasta and ini > fecha_hasta:
                continue
            if municipio and e["municipio"] != municipio:
                continue
            out.append(e)
        return out
    monkeypatch.setattr(B, "get_eventos", get_eventos)
    monkeypatch.setattr(B, "get_eventos_cerca", lambda lat, lng, **k: get_eventos(
        fecha_desde=AHORA.replace(hour=0), fecha_hasta=AHORA + timedelta(days=k.get("dias", 7))))
    yield
    D._CACHE.clear()


# ─── Los ejes ────────────────────────────────────────────────────────────
QUE = [("teatro", "teatro"), ("obras de teatro", "teatro"), ("conciertos", "música"), ("jazz", "jazz"),
       ("rock", "rock"), ("talleres", "talleres"), ("cine", "cine"), ("poesía", "literatura"),
       ("danza", "danza"), ("hip hop", "hip hop"), ("exposiciones", "arte"), ("charlas", "charlas"), ("", None)]
CUANDO = [("hoy", "hoy"), ("esta noche", "esta noche"), ("mañana", "mañana"), ("este finde", "este fin de semana"),
          ("el martes", "el martes"), ("esta semana", "esta semana"), ("la próxima semana", "la próxima semana"),
          ("el 15 de octubre", "el 15 de octubre"), ("en noviembre", "noviembre"), ("", "los próximos 7 días")]
DONDE = [("en Envigado", "envigado", None), ("en Bello", "bello", None), ("en Itagüí", "itagui", None),
         ("en Laureles", None, "Laureles Estadio (Comuna 11)"), ("en la comuna 13", None, "San Javier (Comuna 13)"),
         ("", None, None)]
CUANTO = [("gratis", "gratis"), ("baratos", "barato"), ("de menos de 30 mil", 30000), ("", None)]
FORMAS = ["{que} {cuando} {donde} {cuanto}", "¿qué hay de {que} {cuanto} {donde} {cuando}?",
          "quiero ver {que} {donde} {cuando} {cuanto}", "busco planes de {que} {cuando} {cuanto} {donde}"]


def _combinaciones():
    for (q, f) in itertools.product(itertools.product(QUE, CUANDO, DONDE, CUANTO), range(len(FORMAS))):
        (que, cuando, donde, cuanto) = q
        if f and not (que[0] or cuando[0] or donde[0] or cuanto[0]):
            continue
        yield que, cuando, donde, cuanto, FORMAS[f]


def test_ars_combinatoria_slots():
    """13 × 10 × 6 × 4 × 4 ≈ 12 000 preguntas: cada eje se entiende sin contaminar a los otros."""
    n = 0
    for que, cuando, donde, cuanto, forma in _combinaciones():
        msg = " ".join(forma.format(que=que[0], cuando=cuando[0], donde=donde[0], cuanto=cuanto[0]).split())
        c = B.entender(msg, AHORA)
        G._ubicar(c, f" {B._n(msg)} ")
        n += 1
        if que[1]:
            assert que[1] in c.tipos, msg
        assert c.etiqueta == cuando[1], (msg, c.etiqueta)
        if donde[1]:
            assert c.municipio == donde[1], msg
        if donde[2]:
            assert c.zona and c.zona[0] == donde[2], (msg, c.zona)
        if cuanto[1] == "gratis":
            assert c.gratis, msg
        elif cuanto[1] == "barato":
            assert c.precio_max == 20000, msg
        elif cuanto[1]:
            assert c.precio_max == cuanto[1], (msg, c.precio_max)
        # Las palabras de los ejes nunca se cuelan como texto libre
        assert not set(c.palabras) & {"gratis", "hoy", "noche", "finde", "semana", "comuna", "baratos", "menos"}, (msg, c.palabras)
    assert n > 9000


def test_ars_combinatoria_respuestas_sin_errores():
    """Una muestra amplia pasa por el árbol completo: siempre responde, nunca revienta."""
    for i, (que, cuando, donde, cuanto, forma) in enumerate(_combinaciones()):
        if i % 7:
            continue
        msg = " ".join(forma.format(que=que[0], cuando=cuando[0], donde=donde[0], cuanto=cuanto[0]).split())
        turno = G.responder(msg, [], AHORA)
        assert turno.texto and turno.accion, msg
        for e in turno.eventos:  # lo que se muestra cumple lo pedido
            if cuanto[1] == "gratis" and turno.accion == "eventos":
                assert e["es_gratuito"], msg


INTENCIONES = [
    ("hola", "social"), ("buenas tardes", "social"), ("¿quién sos?", "social"), ("¿qué podés hacer?", "social"),
    ("gracias", "social"), ("chao", "social"), ("cuéntame un chiste", "social"), ("no servís para nada", "social"),
    ("¿cómo publico mi evento?", "sitio"), ("quiero registrar mi colectivo", "sitio"),
    ("quiero recibir la agenda por correo", "sitio"), ("¿cómo me doy de baja? no quiero más correos", "sitio"),
    ("quiero aportar al proyecto", "sitio"), ("¿dónde descargo la app?", "sitio"),
    ("¿dónde queda Otraparte?", "lugar_info"), ("instagram de Casa Teatro El Poblado", "lugar_info"),
    ("teléfono de Otraparte", "lugar_info"), ("qué hay en Otraparte", "eventos_lugar"),
    ("¿a qué hora es Hamlet en versión clown?", "detalle"), ("¿cuánto vale el concierto de jazz latino?", "detalle"),
    ("¿dónde es el recital de poesía?", "detalle"),
    ("¿dónde hay teatros?", "lugares"), ("colectivos de hip hop en Bello", "lugares"), ("bibliotecas en Bello", "lugares"),
    ("¿cuántos eventos hay esta semana?", "contar"), ("¿cuántos conciertos hay este finde?", "contar"),
    ("sorprendeme", "recomendar"), ("estoy aburrido", "recomendar"), ("plan para una cita el sábado", "recomendar"),
    ("recomendame algo gratis para mañana", "recomendar"),
    ("¿va a llover hoy?", "fuera_de_tema"), ("¿cómo quedó el partido de Nacional?", "fuera_de_tema"),
    ("teatro esta noche", "eventos"), ("talleres para niños en Bello", "eventos"), ("jazz mañana", "eventos"),
    ("qué hay cerca", "eventos"), ("¿cuánto vale?", "aclarar"),
]


@pytest.mark.parametrize("mensaje,accion", INTENCIONES)
def test_arbol_de_intenciones(mensaje, accion):
    assert G.responder(mensaje, [], AHORA).accion == accion


def test_conversacion_con_referencias_y_foco():
    h = []

    def decir(m):
        tu = G.responder(m, h, AHORA)
        h.extend([("usuario", m), ("compas", tu.texto)])
        return tu

    lista = decir("teatro esta semana")
    assert lista.accion == "eventos" and len(lista.eventos) >= 2
    segundo = lista.eventos[1]
    tu = decir("¿a qué hora es el segundo?")
    assert tu.accion == "detalle_ref" and tu.eventos[0]["id"] == segundo["id"]
    tu = decir("¿y cuánto vale?")
    assert tu.accion == "detalle_foco" and tu.eventos[0]["id"] == segundo["id"]
    tu = decir("¿dónde queda el primero?")
    assert tu.accion == "detalle_ref" and tu.eventos[0]["id"] == lista.eventos[0]["id"]
    tu = decir("y gratis?")
    assert all(e["es_gratuito"] for e in tu.eventos)


def test_pregunta_nueva_tras_una_lista_no_es_referencia():
    h = []
    tu = G.responder("sorprendeme", h, AHORA)
    h += [("usuario", "sorprendeme"), ("compas", tu.texto)]
    assert G.responder("¿cuántos conciertos hay este finde?", h, AHORA).accion == "contar"
    assert G.responder("teatro esta noche", h, AHORA).accion == "eventos"
    assert G.responder("¿y el segundo a qué hora es?", h, AHORA).accion == "detalle_ref"


def test_lugares_y_luego_su_instagram():
    h = []
    tu = G.responder("colectivos de hip hop en Bello", h, AHORA)
    h += [("usuario", "colectivos de hip hop en Bello"), ("compas", tu.texto)]
    tu = G.responder("instagram del primero", h, AHORA)
    assert tu.accion == "lugar_ref" and "crewniquia" in tu.texto


def test_ejes_finos():
    c = B.entender("rock después de las 8 de la noche", AHORA)
    assert c.franja[0] == 20
    c = B.entender("algo para Halloween", AHORA)
    assert c.etiqueta == "Halloween" and c.desde.day == 31
    c = B.entender("talleres en la mañana el sábado", AHORA)
    assert c.franja[:2] == (6, 12) and c.etiqueta == "el sábado"
    c = B.entender("dame 3 planes gratis", AHORA)
    assert c.limite == 3 and c.gratis
    c = B.entender("planes para ir con mi perro", AHORA)
    assert c.publico == "mascotas"
    c = B.entender("entre el 10 y el 12 de octubre", AHORA)
    assert c.desde.day == 10 and c.hasta.day == 13
