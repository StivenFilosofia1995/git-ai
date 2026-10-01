from datetime import datetime

from app.services.event_gate import (
    CO_TZ, anio_publicacion_antigua, evaluar_evento, es_prosa, es_texto_menu, limpiar_descripcion,
    limpiar_titulo, planear_revision,
)

AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=CO_TZ)


def ev(**kw):
    base = {"id": kw.pop("id", "x"), "titulo": "Concierto de La Muchacha", "fecha_inicio": "2026-10-03T20:00:00-05:00",
            "fuente": "agenda_Casa Teatro", "nombre_lugar": "Casa Teatro El Poblado", "hora_confirmada": True}
    base.update(kw)
    return base


def test_evento_normal_se_publica():
    assert evaluar_evento(ev(), ahora=AHORA).decision == "publicar"


def test_titulo_menu_web_se_rechaza():
    for t in ("Normatividad", "Municipio de Sabaneta", "Contáctenos", "Ver más"):
        r = evaluar_evento(ev(titulo=t, fuente="auto_scraper_sitio_web"), ahora=AHORA)
        assert r.decision == "rechazar" and "titulo_es_menu_web" in r.motivos, t


def test_plantilla_generica_solo_en_fuentes_no_estructuradas():
    r = evaluar_evento(ev(titulo="Festival de Danza", fuente="auto_scraper_sitio_web"), ahora=AHORA)
    assert r.decision == "rechazar"
    # Bibliotecas (estructurada) puede tener títulos genéricos reales
    assert evaluar_evento(ev(titulo="Taller de escritura", fuente="bibliotecas_mde"), ahora=AHORA).decision == "publicar"


def test_publicacion_antigua_por_dia_de_semana():
    # "sábado 30 de septiembre" fue sábado en 2023, no en 2026
    texto = "Este sábado 30 de septiembre gran noche de jazz"
    assert anio_publicacion_antigua(texto, datetime(2026, 9, 30, tzinfo=CO_TZ), AHORA) == 2023
    # "sábado 3 de octubre" sí es sábado en 2026 → consistente
    assert anio_publicacion_antigua("sábado 3 de octubre", datetime(2026, 10, 3, tzinfo=CO_TZ), AHORA) is None
    r = evaluar_evento(ev(titulo="Noche de jazz", descripcion="Este sábado 30 de septiembre",
                          fecha_inicio="2026-09-30T20:00:00-05:00", fecha_fin="2026-10-30T20:00:00-05:00",
                          fuente="auto_scraper_instagram"), ahora=AHORA)
    assert r.decision == "rechazar" and any(m.startswith("publicacion_antigua") for m in r.motivos)


def test_fechas_imposibles():
    assert "fecha_pasada" in evaluar_evento(ev(fecha_inicio="2026-05-07T00:00:00-05:00"), ahora=AHORA).motivos
    r = evaluar_evento(ev(fecha_inicio="2026-05-07T00:00:00-05:00", fecha_fin="2076-05-10T00:00:00-05:00"), ahora=AHORA)
    assert r.decision == "rechazar" and r.payload["fecha_fin"] is None
    assert "fecha_muy_lejana" in evaluar_evento(ev(fecha_inicio="2028-01-01T00:00:00-05:00"), ahora=AHORA).motivos


def test_fuera_del_valle():
    r = evaluar_evento(ev(titulo="Concierto en The Visulite Theatre - Charlotte", nombre_lugar=None,
                          fuente="auto_scraper_sitio_web"), ahora=AHORA)
    assert "otra_ciudad" in r.motivos
    r = evaluar_evento(ev(titulo="Lovin' Life Music Festival- Charlotte", espacio_id="x"), ahora=AHORA)
    assert "otra_ciudad" in r.motivos
    r = evaluar_evento(ev(lat=5.7, lng=-75.9), ahora=AHORA)
    assert "coordenadas_fuera_del_valle" in r.motivos


def test_cuarentena_fuente_baja_sin_lugar():
    r = evaluar_evento(ev(fuente="precision_web", nombre_lugar=None, titulo="Noche de tango con Orquesta Típica"),
                       ahora=AHORA)
    assert r.decision == "cuarentena"


def test_limpiar_titulo_bloque_html():
    t = "MIÉ 30 SEP Miércoles El Plan de la Mariposa en Medellín Concierto Compra tu Ticket | Hora: 8:00 p.m. PULEP: YRG335"
    assert limpiar_titulo(t) == "El Plan de la Mariposa en Medellín Concierto"
    largo = "El próximo jueves a las 7:00 PM te invitamos a vivir la exposición POLVO DE ESTRELLAS de una manera diferente y mágica con música"
    assert len(limpiar_titulo(largo)) <= 90


def test_descripcion_menu():
    menu = ("Nosotros Quiénes Somos Directorio administrativo Documentos institucionales Premios y Reconocimientos "
            "Plan estratégico 2022-2026 Estadística Estudio de valor Contáctenos Atención PQRS Preguntas Frecuentes")
    assert es_texto_menu(menu)
    assert limpiar_descripcion(menu) is None
    prosa = "Entre lecturas escalofriantes, dulces y mucha diversión, tendremos un encuentro para imaginar historias."
    assert es_prosa(prosa) and limpiar_descripcion(prosa) == prosa


def test_duplicados_mismo_dia_y_lugar_se_fusionan():
    a = ev(id="a", titulo="XVII Festival Flamenco Ciudad de Medellín. FLAMENCOS", fuente="agenda_Casa Teatro",
           imagen_url=None)
    b = ev(id="b", titulo="XVII Festival Flamenco Ciudad de Medellín FLAMENCOS ◈", fuente="precision_web",
           imagen_url="https://x/img.jpg")
    plan = planear_revision([a, b], ahora=AHORA)
    assert plan["ocultar"] == {"b": "gate:duplicado:a"}
    assert plan["actualizar"]["a"]["imagen_url"] == "https://x/img.jpg"


def test_misma_actividad_en_bibliotecas_distintas_no_es_duplicado():
    a = ev(id="a", titulo="Hora del cuento", fuente="bibliotecas_mde", espacio_id="bib1", nombre_lugar="Biblioteca Belén")
    b = ev(id="b", titulo="Hora del cuento", fuente="bibliotecas_mde", espacio_id="bib2", nombre_lugar="Biblioteca La Ladera")
    assert planear_revision([a, b], ahora=AHORA)["ocultar"] == {}


def test_dos_funciones_mismo_dia_no_son_duplicado():
    a = ev(id="a", fecha_inicio="2026-10-03T16:00:00-05:00")
    b = ev(id="b", fecha_inicio="2026-10-03T20:00:00-05:00")
    assert planear_revision([a, b], ahora=AHORA)["ocultar"] == {}
