# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services import evento_service


CO_TZ = ZoneInfo("America/Bogota")


def test_get_eventos_semana_empieza_manana(monkeypatch):
    ahora_fijo = datetime(2026, 4, 23, 15, 30, tzinfo=CO_TZ)
    llamado = {}

    def fake_get_eventos(**kwargs):
        llamado.update(kwargs)
        return []

    monkeypatch.setattr(evento_service, "_now_co", lambda: ahora_fijo)
    monkeypatch.setattr(evento_service, "get_eventos", fake_get_eventos)

    evento_service.get_eventos_semana()

    assert llamado["fecha_desde"] == datetime(2026, 4, 24, 0, 0, tzinfo=CO_TZ)
    assert llamado["fecha_hasta"] == datetime(2026, 5, 3, 23, 59, 59, tzinfo=CO_TZ)


def test_get_eventos_proximas_semanas_empieza_manana(monkeypatch):
    ahora_fijo = datetime(2026, 4, 23, 15, 30, tzinfo=CO_TZ)
    llamado = {}

    def fake_get_eventos(**kwargs):
        llamado.update(kwargs)
        return []

    monkeypatch.setattr(evento_service, "_now_co", lambda: ahora_fijo)
    monkeypatch.setattr(evento_service, "get_eventos", fake_get_eventos)

    evento_service.get_eventos_proximas_semanas(21)

    assert llamado["fecha_desde"] == datetime(2026, 4, 24, 0, 0, tzinfo=CO_TZ)
    assert llamado["fecha_hasta"] == datetime(2026, 5, 15, 0, 0, tzinfo=CO_TZ)


def test_get_eventos_proximas_semanas_limita_dias_invalidos(monkeypatch):
    ahora_fijo = datetime(2026, 4, 23, 15, 30, tzinfo=CO_TZ)
    llamado = {}

    def fake_get_eventos(**kwargs):
        llamado.update(kwargs)
        return []

    monkeypatch.setattr(evento_service, "_now_co", lambda: ahora_fijo)
    monkeypatch.setattr(evento_service, "get_eventos", fake_get_eventos)

    evento_service.get_eventos_proximas_semanas(0)
    assert llamado["fecha_desde"] == datetime(2026, 4, 24, 0, 0, tzinfo=CO_TZ)
    assert llamado["fecha_hasta"] == datetime(2026, 4, 25, 0, 0, tzinfo=CO_TZ)

    llamado.clear()
    evento_service.get_eventos_proximas_semanas(120)
    assert llamado["fecha_desde"] == datetime(2026, 4, 24, 0, 0, tzinfo=CO_TZ)
    assert llamado["fecha_hasta"] == datetime(2026, 7, 23, 0, 0, tzinfo=CO_TZ)