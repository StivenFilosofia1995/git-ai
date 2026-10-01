from app.services.comfama_scraper import gatsby_evento_a_dict
from app.services.event_gate import evaluar_evento

BASE = {"title": "Comunidad de impro y teatro", "startDate": "2026-10-03T10:00:00Z", "endDate": "2026-10-03T12:00:00Z",
        "municipality": "Medellín", "type": ["Gratis"], "paymentText": "Entrada libre con inscripción",
        "location": ["Edificio Comfama San Ignacio"], "formattedAddress": "Cra. 44 #48-18, La Candelaria, Medellín",
        "category": {"categoryName": "Talleres"}, "cardImage": {"url": "https://cdn.eventtia.com/x.jpg"}}


def test_hora_z_es_hora_local_de_bogota():
    ev = gatsby_evento_a_dict(BASE, "comunidad-impro-octubre1/")
    assert ev["fecha_inicio"] == "2026-10-03T10:00:00-05:00"
    assert ev["hora_confirmada"] and ev["es_gratuito"] and ev["barrio"] == "La Candelaria"
    assert ev["fuente_url"].endswith("/agenda/evento/comunidad-impro-octubre1/")


def test_cancelados_y_fuera_del_valle_se_descartan():
    assert gatsby_evento_a_dict({**BASE, "title": "(Cancelado) Vacaciones Creativas"}, "x") is None
    assert gatsby_evento_a_dict({**BASE, "municipality": "Rionegro"}, "x") is None


def test_tarifa_no_afiliado():
    ev = gatsby_evento_a_dict({**BASE, "type": [], "paymentText": "Entrada con cobro", "rateD": 25000}, "x")
    assert not ev["es_gratuito"] and ev["precio"].startswith("$25.000")


def test_puerta_rechaza_cancelados():
    r = evaluar_evento({"titulo": "Concierto de jazz (Aplazado)", "fecha_inicio": "2026-10-10T20:00:00-05:00",
                        "fuente": "agenda_x", "nombre_lugar": "X"})
    assert r.decision == "rechazar" and "cancelado" in r.motivos
