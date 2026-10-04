from datetime import datetime

from app.services.eterea_buscador import CO_TZ, _puntaje, entender

AHORA = datetime(2026, 10, 3, 15, 0, tzinfo=CO_TZ)  # sábado


def test_fechas():
    c = entender("teatro este finde", AHORA)
    assert c.tipos == ["teatro"] and c.desde.day == 3 and c.hasta.day == 5
    c = entender("conciertos gratis hoy", AHORA)
    assert c.gratis and c.etiqueta == "hoy" and "música" in c.tipos
    assert entender("qué hay mañana", AHORA).desde.day == 4
    c = entender("cine la próxima semana", AHORA)
    assert c.desde.day == 5 and c.hasta.day == 12
    assert entender("planes el martes", AHORA).desde.day == 6


def test_lugar_y_texto_libre():
    c = entender("talleres en Envigado", AHORA)
    assert c.municipio == "envigado" and c.tipos == ["talleres"]
    assert "planetario" in entender("planetario", AHORA).palabras
    assert entender("[Ubicación: 6.25, -75.56] qué hay cerca", AHORA).ubicacion == (6.25, -75.56)


def test_puntaje_por_inicio_de_palabra():
    c = entender("arte", AHORA)
    assert _puntaje({"titulo": "Recital de piano en Otraparte", "categoria_principal": "musica_en_vivo"}, c) == 0
    assert _puntaje({"titulo": "Arte en crochet", "categoria_principal": "taller"}, c) > 0
