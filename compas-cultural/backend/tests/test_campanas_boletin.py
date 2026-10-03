from datetime import date

from app.services import email_service as es


def test_ventana_finde():
    # 2026-10-02 viernes, 03 sábado, 04 domingo, 05 lunes
    assert es._ventana_finde(date(2026, 10, 2)) == (0, 3)
    assert es._ventana_finde(date(2026, 10, 3)) == (0, 2)
    assert es._ventana_finde(date(2026, 10, 4)) == (0, 1)
    assert es._ventana_finde(date(2026, 10, 5)) == (4, 7)


def test_campanas_separan_marcas():
    assert es.marca_campana("semanal", "2026-10-05") == "2026-10-05"
    assert es.marca_campana("finde", "2026-10-05") == "finde:2026-10-05"


def test_plantilla_valle_de_aburra():
    ev = {"titulo": "Concierto", "slug": "concierto", "fecha_inicio": "2026-10-09T19:00:00-05:00",
          "nombre_lugar": "Parque de los Deseos", "es_gratuito": True}
    cfg = es.CAMPANAS["finde"]
    html = es._build_weekly_digest_html("Ana", es.VALLE_LABEL, [ev], [ev], titulo_seccion=cfg["titulo"],
                                        intro=cfg["intro"], max_eventos=cfg["max"])
    assert "HOY EN EL VALLE DE ABURRÁ" in html
    assert "ESTE FIN DE SEMANA" in html
    assert "VALLE</div>" not in html
