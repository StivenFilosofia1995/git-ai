"""Con los Excel reales de octubre 2026 (seeds/data/programacion/2026-10)."""
from datetime import date
from pathlib import Path

from app.services.programacion_excel import corregir_rango, leer_programacion, parsear_fechas, parsear_hora

DIR = Path(__file__).resolve().parents[1] / "seeds" / "data" / "programacion" / "2026-10"
HOY = date(2026, 10, 3)


def leer(nombre):
    return leer_programacion((DIR / nombre).read_bytes(), nombre, HOY)


def test_horas_de_los_excel():
    assert parsear_hora("9:00 a.m") == (9, 0)
    assert parsear_hora("2:00 p.m") == (14, 0)
    assert parsear_hora("12:00:00 m") == (12, 0)
    assert parsear_hora("11:00m") == (11, 0)
    assert parsear_hora("10:00:009") == (10, 0)
    assert corregir_rango((21, 0), (12, 0)) == ((9, 0), (12, 0))     # "9:00 p.m a 12:00 m"
    assert corregir_rango((23, 30), (13, 0)) == ((11, 30), (13, 0))  # UVA: 23:30 a 13:00


def test_fechas_de_los_excel():
    assert parsear_fechas("06/10/2026 13/10/2026 20/10/2026", 2026, 10)[0] == [date(2026, 10, 6), date(2026, 10, 13), date(2026, 10, 20)]
    assert parsear_fechas("10 y 24 de octubre", 2026, None)[0] == [date(2026, 10, 10), date(2026, 10, 24)]
    jueves = parsear_fechas("Todos los jueves de octubre", 2026, None)[0]
    assert jueves[0] == date(2026, 10, 1) and all(d.weekday() == 3 for d in jueves) and len(jueves) == 5
    assert parsear_fechas("pendiente", 2026, 10) == ([], False)
    fechas, tentativo = parsear_fechas("tentativo 18 de octubre", 2026, 10)
    assert fechas == [date(2026, 10, 18)] and tentativo


def test_parque_archivo_cortado_se_repara():
    r = leer("parque_de_los_deseos.xlsx")
    assert r.reparado and "Octubre" in r.formatos
    titulos = {e["titulo"] for e in r.eventos}
    assert "Festi Afro" in titulos
    assert not any("Laboratorio para cuidadores" in t for t in titulos)  # "Abierto al público: No"
    assert all(e["lat"] for e in r.eventos)  # Parque de los Deseos verificado en OSM


def test_museo_excluye_grupos_cerrados_y_hereda_filas():
    r = leer("museo_del_agua.xlsx")
    assert not any("Club Amigos del Agua" in e["titulo"] for e in r.eventos)  # cerrado
    kahoot = [e for e in r.eventos if "Kahoot" in e["titulo"]]
    assert {e["fecha_inicio"][:10] for e in kahoot} == {"2026-10-03", "2026-10-24", "2026-10-31"}  # filas heredadas


def test_uva_cursos_un_solo_evento_y_talleres_por_sesion():
    r = leer("uva.xlsx")
    curso = [e for e in r.eventos if e["titulo"] == "Tecnología para todos" and e["nombre_lugar"] == "UVA Nuevo Amanecer"]
    assert len(curso) == 1 and "4 sesiones" in curso[0]["descripcion"] and curso[0]["categoria_principal"] == "taller"
    assert all(e["fuente"] == "fundacion_epm_excel" and e["es_gratuito"] for e in r.eventos)


def test_biblioteca_mes_desde_el_titulo_de_la_hoja():
    r = leer("biblioteca_epm.xlsx")
    hora_cuento = [e for e in r.eventos if e["titulo"].startswith("Hora del cuento")]
    assert hora_cuento and all(e["fecha_inicio"][:7] == "2026-10" for e in hora_cuento)
    assert all(e["hora_confirmada"] for e in hora_cuento) and hora_cuento[0]["fecha_inicio"][11:16] == "14:00"
