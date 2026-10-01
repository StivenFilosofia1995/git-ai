from app.services import email_service as es


def test_fecha_hora_en_bogota_y_espanol():
    ev = {"fecha_inicio": "2026-10-03T01:00:00+00:00", "hora_confirmada": True}  # = vie 2 oct 8 p. m. en Bogotá
    assert es._fecha_hora_co(ev) == ("vie 2 oct", "8:00 p. m.")
    assert es._fecha_hora_co({"fecha_inicio": "2026-10-03T10:00:00-05:00"}) == ("sáb 3 oct", "")


def test_remitente_de_prueba_de_resend_no_esta_listo(monkeypatch):
    monkeypatch.setattr(es.settings, "resend_api_key", "re_x")
    monkeypatch.setattr(es.settings, "smtp_from_email", "onboarding@resend.dev")
    monkeypatch.setattr(es.settings, "smtp_password", "")
    listo, motivo = es.remitente_listo()
    assert not listo and "resend.dev" in motivo
    monkeypatch.setattr(es.settings, "smtp_from_email", "agenda@culturaetereamed.com")
    assert es.remitente_listo()[0]


def test_lugares_scrapeados_no_reciben_boletin(monkeypatch):
    monkeypatch.setattr(es, "_load_auth_users", lambda limit: [{"email": "a@x.co", "nombre": "A"}])
    monkeypatch.setattr(es, "_load_profile_recipients", lambda limit: [])
    monkeypatch.setattr(es, "_load_place_recipients", lambda limit: [{"email": "teatro@x.co", "nombre": "T"}])
    monkeypatch.delenv("EMAIL_INCLUIR_LUGARES", raising=False)
    assert [r["email"] for r in es.cargar_destinatarios()] == ["a@x.co"]


def test_enlaces_del_correo_van_a_evento():
    html = es._build_event_card_large({"titulo": "X", "slug": "x-2026", "fecha_inicio": "2026-10-03T20:00:00-05:00"},
                                      "https://culturaetereamed.com")
    assert "/evento/x-2026" in html and "/agenda/x-2026" not in html
