"""Casos tomados de errores reales del extractor anterior (producción, 2026-10-01)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.ig_precision import analizar_post, extraer_hora

CO = ZoneInfo("America/Bogota")
AHORA = datetime(2026, 10, 1, 12, tzinfo=CO)


def post(dia: str):
    return datetime.fromisoformat(dia).replace(tzinfo=CO)


def test_dia_del_mes_no_es_hora():
    # Antes: "este 19 de Febrero" → 19:00 confirmada
    assert extraer_hora("programese para este 19 de febrero") == (None, "")
    assert extraer_hora("entrada $20.000 general") == (None, "")
    assert extraer_hora("plan estrategico 2022-2026") == (None, "")


def test_horas_explicitas():
    assert extraer_hora("el 7 de octubre a las 6:00 p.m. en el teatro")[0] == (18, 0)
    assert extraer_hora("abrimos puertas 8pm")[0] == (20, 0)
    assert extraer_hora("inicia 20:30 en punto")[0] == (20, 30)
    assert extraer_hora("a las 7 de la noche")[0] == (19, 0)
    assert extraer_hora("nos vemos a las 7:30")[0] is None  # ambiguo: no se inventa


def test_post_viejo_no_se_manda_al_anio_siguiente():
    # Post de febrero 2026: "este 19 de febrero" es 2026 → ya pasó (antes quedaba en 2027)
    r = analizar_post("Prográmese para este 19 de Febrero: concierto de Afaz Natural en Medellín",
                      post("2026-02-10T10:00"), AHORA)
    assert not r.ok and r.motivo == "ya_paso"


def test_sin_fecha_de_publicacion_no_se_adivina_el_anio():
    r = analizar_post("Concierto de jazz el 19 de febrero en Casa Teatro, entrada libre", None, AHORA)
    assert not r.ok and r.motivo == "sin_ancla_para_el_anio"
    r = analizar_post("Concierto de jazz el viernes 19 de febrero en Casa Teatro", None, AHORA)
    assert r.ok and r.fecha_inicio.date().isoformat() == "2027-02-19"  # 19-feb-2027 sí es viernes


def test_no_eventos_reales():
    for cap in ("CASTING CERRADO Buscamos hombres y mujeres entre 20 y 28 años para la obra",
                "27 de Enero. Feliz día del Conservador, te invitamos a celebrarlo",
                "Las urgencias en Medellín superan el 150 % de ocupación según la Alcaldía",
                "El pasado domingo, 5 de noviembre, nos reunimos en el teatro. Gracias a todos"):
        assert not analizar_post(cap, post("2026-09-28T10:00"), AHORA).ok, cap


def test_gira_en_otro_pais():
    r = analizar_post("¡GalactiGatos en República Dominicana! Función el 23 de octubre en el festival",
                      post("2026-09-28T10:00"), AHORA)
    assert not r.ok and r.motivo.startswith("otra_ciudad")


def test_evento_bien_formado_se_publica_con_evidencia():
    cap = ("“Mi peor enemigo” — stand up con Arcángel Aristizábal\n"
           "Sábado 3 de octubre a las 8:00 p. m. en el Teatro Acción Impro, Cll 9 #43B-80. Boletas $40.000")
    r = analizar_post(cap, post("2026-09-27T10:00"), AHORA)
    assert r.ok and r.decision == "publicar"
    assert r.titulo == "Mi peor enemigo"
    assert r.fecha_inicio.isoformat() == "2026-10-03T20:00:00-05:00" and r.hora_confirmada
    assert r.evidencia["fecha"].startswith("sabado 3 de octubre") and "8:00 p. m" in r.evidencia["hora"]
    assert r.precio == "$40.000"


def test_sin_hora_queda_sin_confirmar_y_dia_semana_debe_coincidir():
    r = analizar_post("Taller de grabado el sábado 10 de octubre en nuestra casa. Entrada libre",
                      post("2026-09-30T10:00"), AHORA)
    assert r.ok and not r.hora_confirmada and r.fecha_inicio.hour == 0
    r = analizar_post("Concierto el viernes 10 de octubre", post("2026-09-30T10:00"), AHORA)
    assert not r.ok and r.motivo == "dia_semana_no_coincide"  # 10-oct-2026 es sábado


def test_fecha_relativa_solo_con_post_reciente():
    r = analizar_post("Hoy concierto en vivo 8pm, los esperamos", post("2026-09-30T10:00"), AHORA)
    assert not r.ok  # "hoy" del post (30 sep) ya pasó
    r = analizar_post("Este sábado concierto en vivo 8pm, los esperamos", post("2026-09-30T10:00"), AHORA)
    assert r.ok and r.fecha_inicio.date().isoformat() == "2026-10-03"
    r = analizar_post("Este sábado concierto en vivo 8pm", post("2026-08-01T10:00"), AHORA)
    assert not r.ok  # post de hace 2 meses: "este sábado" no se puede saber


def test_rango_de_fechas():
    r = analizar_post("Festival de teatro del 15 al 18 de octubre en Medellín. Entrada libre",
                      post("2026-09-29T10:00"), AHORA)
    assert r.ok and r.fecha_inicio.day == 15 and r.fecha_fin.day == 18


def test_cursos_van_a_cuarentena():
    r = analizar_post("INSCRIPCIONES ABIERTAS Taller de Rakú. El próximo 17 de noviembre iniciamos un nuevo curso",
                      post("2026-09-29T10:00"), AHORA)
    assert r.ok and r.decision == "cuarentena"
