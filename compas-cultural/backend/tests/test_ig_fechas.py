from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.ig_event_extractor import _resolve_daynum_date

NOW = datetime(2026, 10, 1, 12, tzinfo=ZoneInfo("America/Bogota"))


def test_dia_de_semana_decide_el_anio():
    assert _resolve_daynum_date("sábado 3 de octubre", NOW).date().isoformat() == "2026-10-03"
    assert _resolve_daynum_date("viernes 26 de febrero", NOW).date().isoformat() == "2027-02-26"


def test_post_viejo_se_descarta():
    # 30-sep fue sábado en 2023 y 26-feb fue jueves en 2026 (ya pasó): no son eventos futuros
    assert _resolve_daynum_date("este sábado 30 de septiembre", NOW) is None
    assert _resolve_daynum_date("jueves 26 de febrero", NOW) is None
