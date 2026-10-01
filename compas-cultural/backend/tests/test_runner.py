from datetime import datetime
from zoneinfo import ZoneInfo

from runner.fb import parsear_fecha_fb
from runner.ig import _items_de_json, _perfil_desde_capturas
from runner.pipeline import eventos_desde_feed, handle_ig, url_fb

CO = ZoneInfo("America/Bogota")
AHORA = datetime(2026, 10, 1, 12, tzinfo=CO)


def test_handle_ig_desde_urls_y_arrobas():
    assert handle_ig("@Casa_X") == "casa_x"
    assert handle_ig("https://www.instagram.com/decabezaediciones/") == "decabezaediciones"
    assert handle_ig("instagram.com/teatro.y?igsh=abc") == "teatro.y"
    assert handle_ig("https://www.instagram.com/p/ABC123/") is None
    assert handle_ig(None) is None


def test_url_fb():
    assert url_fb("https://www.facebook.com/casateatro?ref=x") == "https://www.facebook.com/casateatro"
    assert url_fb("casateatro") == "https://www.facebook.com/casateatro"
    assert url_fb("no es una url") is None


def test_fecha_fb_espanol_e_ingles():
    dt, hora = parsear_fecha_fb("SÁBADO, 3 DE OCTUBRE DE 2026 DE 20:00 A 23:00 COT", AHORA)
    assert dt.isoformat().startswith("2026-10-03T20:00") and hora
    dt, hora = parsear_fecha_fb("vie, 9 oct a las 8 p. m.", AHORA)
    assert dt.isoformat().startswith("2026-10-09T20:00") and hora
    dt, hora = parsear_fecha_fb("Saturday, October 3, 2026 at 8 PM", AHORA)
    assert dt.isoformat().startswith("2026-10-03T20:00") and hora
    dt, hora = parsear_fecha_fb("15 de marzo", AHORA)  # sin año y ya pasó → año siguiente
    assert dt.year == 2027 and not hora
    assert parsear_fecha_fb("sin fecha aquí", AHORA) == (None, False)


def _item(code, user, caption, ts=1790000000):
    return {"code": code, "caption": {"text": caption}, "user": {"username": user},
            "image_versions2": {"candidates": [{"url": f"https://img/{code}.jpg"}]}, "taken_at": ts}


def test_items_de_json_y_perfil():
    data = {"data": {"xdt_api__v1__feed__timeline__connection": {"edges": [
        {"node": {"media": _item("A1", "casateatro", "Este sábado 3 de octubre concierto 8pm")}},
        {"node": {"media": _item("B2", "amiga_personal", "Mi cumpleaños")}},
    ]}}}
    items = _items_de_json(data)
    assert [i["shortcode"] for i in items] == ["A1", "B2"]
    perfil = _perfil_desde_capturas([data])
    assert perfil["permalink_urls"][0] == "https://www.instagram.com/p/A1/"


def test_feed_descarta_cuentas_que_no_son_lugares():
    posts = [
        {"caption": "Este sábado 3 de octubre gran concierto de jazz a las 8:00 pm entrada libre",
         "username": "casateatro", "image_url": "https://img/a.jpg", "permalink": "https://www.instagram.com/p/A1/",
         "taken_at": int(datetime(2026, 9, 29, tzinfo=CO).timestamp())},
        {"caption": "Este sábado 3 de octubre fiesta en mi casa a las 8:00 pm", "username": "amiga_personal",
         "image_url": "", "permalink": "https://www.instagram.com/p/B2/", "taken_at": 0},
    ]
    lugares = {"casateatro": {"id": "L1", "slug": "casa-teatro", "nombre": "Casa Teatro El Poblado",
                              "municipio": "medellin", "categoria_principal": "teatro", "instagram_handle": "casateatro"}}
    evs = eventos_desde_feed(posts, lugares)
    assert evs and all(e["espacio_id"] == "L1" and e["fuente"] == "runner_ig_feed" for e in evs)
    assert all("amiga" not in (e.get("fuente_url") or "") for e in evs)
