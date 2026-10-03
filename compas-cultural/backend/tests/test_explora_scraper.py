from app.services.explora_scraper import a_evento, parsear_hora


def test_hora_time_y_texto():
    assert parsear_hora({"time": 930}) == (9, 30)
    assert parsear_hora({"time": 0, "hour": "5:00 p. m."}) == (17, 0)
    assert parsear_hora({"time": 0, "hour": "10:00 a.m."}) == (10, 0)
    assert parsear_hora({"time": 0, "hour": ""}) is None


def test_evento_planetario_con_hora_bogota():
    ev = a_evento({"slug": "arqueologia", "title": "Arqueología de la Vía Láctea", "location": ["Planetario"],
                   "date": "2026-10-03", "hour": "5:00 p. m.", "time": 1700},
                  {"price_check": "Sin costo", "content": "<p>Charla en el auditorio</p>",
                   "banner": {"imgix_url": "https://imgix.cosmicjs.com/x.webp"}})
    assert ev["fecha_inicio"] == "2026-10-03T17:00:00-05:00"
    assert ev["nombre_lugar"] == "Planetario de Medellín" and ev["lat"] and ev["es_gratuito"]
    assert ev["imagen_url"].endswith("x.webp") and ev["fuente_url"].endswith("/programate/arqueologia")


def test_evento_en_otra_sede_sin_pin_del_museo():
    ev = a_evento({"slug": "halloween", "title": "Halloween sinfónico", "location": ["Planetario"],
                   "date": "2026-10-31", "time": 1000},
                  {"price_check": "Con costo", "content": "En el Teatro Fundadores de EAFIT"})
    assert ev["nombre_lugar"] == "Teatro Fundadores (Universidad EAFIT)"
    assert "lat" not in ev and not ev["es_gratuito"]
