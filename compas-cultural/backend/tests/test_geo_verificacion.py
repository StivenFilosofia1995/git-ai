from app.services.geo_verificacion import clasificar, elegir_resultado, es_placeholder


def _res(name, lat, lon, typ="theatre", addresstype="amenity"):
    return {"name": name, "lat": str(lat), "lon": str(lon), "type": typ, "addresstype": addresstype,
            "osm_type": "node", "osm_id": 1}


def test_elegir_resultado_ignora_zonas_y_nombres_distintos():
    resultados = [
        _res("Medellín", 6.2476, -75.5658, typ="city", addresstype="city"),
        _res("Teatro Metropolitano", 6.2415, -75.5715),
        _res("Teatro Pablo Tobón Uribe", 6.2449, -75.5594),
    ]
    m = elegir_resultado("Teatro Pablo Tobón Uribe", resultados)
    assert m and abs(m["lat"] - 6.2449) < 1e-6


def test_elegir_resultado_sin_coincidencia():
    assert elegir_resultado("Colectivo Inventado XYZ", [_res("Parque Explora", 6.27, -75.56)]) is None


def test_clasificar_estados():
    match = {"lat": 6.2449, "lng": -75.5594}
    assert clasificar((6.2450, -75.5595), match)[0] == "ok"
    estado, dist = clasificar((6.2442, -75.5812), match)
    assert estado == "corregir" and dist > 250
    assert clasificar(None, match)[0] == "nuevo"
    assert clasificar((6.2442, -75.5812), None)[0] == "placeholder"
    assert clasificar((6.21, -75.57), None)[0] == "sin_verificar"


def test_placeholder_centro_medellin():
    assert es_placeholder(6.2442, -75.5812)
    assert not es_placeholder(6.2088, -75.5672)


def test_ejes_direccion_cuadricula_medellin():
    from app.services.geo_verificacion import ejes_direccion
    assert ejes_direccion("Calle 44 #39-100, Medellín") == {"calle": 44, "carrera": 39}
    assert ejes_direccion("Carrera 64 No. 50-32") == {"carrera": 64, "calle": 50}
    assert ejes_direccion("sin dirección") == {}


def test_direccion_incompatible_descarta_resultado():
    from app.services.geo_verificacion import elegir_resultado
    res = _res("Biblioteca Pública Piloto", 6.3005, -75.5742, typ="library")
    res["address"] = {"road": "Calle 102B", "city": "Medellín"}
    assert elegir_resultado("Biblioteca Pública Piloto", [res], "medellin", "Calle 44 #39-100") is None
    assert elegir_resultado("Biblioteca Pública Piloto", [res], "medellin", None) is not None


def test_homonimos_lejanos_son_ambiguos():
    from app.services.geo_verificacion import es_ambiguo, token_distintivo
    assert token_distintivo("Biblioteca Pública Piloto") == "piloto"
    match = {"lat": 6.3005, "lng": -75.5742}
    homs = [{"name": "Biblioteca Pública Piloto", "lat": 6.3005, "lng": -75.5742},
            {"name": "Biblioteca Pública Piloto de Medellín para América Latina", "lat": 6.2554, "lng": -75.5775}]
    assert es_ambiguo("Biblioteca Pública Piloto", match, homs)
    assert not es_ambiguo("Biblioteca Pública Piloto", match, homs[:1])
