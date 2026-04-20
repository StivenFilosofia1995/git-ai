# -*- coding: utf-8 -*-
"""
Tests para app/services/data_quality.py
Cubre: slugify, normalización de municipio/categoría/instagram/precio,
y construcción de eventos y lugares normalizados.
"""
from datetime import datetime, timedelta

import pytest

from app.services.data_quality import (
    CATEGORIAS_VALIDAS,
    MUNICIPIOS_VALIDOS,
    normalizar_categoria,
    normalizar_evento,
    normalizar_instagram,
    normalizar_lugar,
    normalizar_municipio,
    normalizar_precio,
    slugify,
)


# ═══════════════════════════════════════════════════════════════
# slugify
# ═══════════════════════════════════════════════════════════════


class TestSlugify:
    def test_basic(self):
        assert slugify("Teatro Matacandelas") == "teatro-matacandelas"

    def test_accents_removed(self):
        assert slugify("Medellín Cultural") == "medellin-cultural"

    def test_special_chars(self):
        assert slugify("Teatro Matacandelas — Obra nueva!") == "teatro-matacandelas-obra-nueva"

    def test_extra_spaces(self):
        assert slugify("  Jazz   en   vivo  ") == "jazz-en-vivo"

    def test_already_slug(self):
        assert slugify("jazz-en-vivo") == "jazz-en-vivo"

    def test_leading_trailing_dashes(self):
        result = slugify("!punk!")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_long_text_truncated(self):
        long_text = "a" * 300
        assert len(slugify(long_text)) <= 250

    def test_empty_string(self):
        assert slugify("") == ""

    def test_numbers_preserved(self):
        assert slugify("Evento 2026") == "evento-2026"


# ═══════════════════════════════════════════════════════════════
# normalizar_municipio
# ═══════════════════════════════════════════════════════════════


class TestNormalizarMunicipio:
    def test_medellin_con_tilde(self):
        assert normalizar_municipio("Medellín") == "medellin"

    def test_medellin_sin_tilde(self):
        assert normalizar_municipio("medellin") == "medellin"

    def test_itagui_con_dieresis(self):
        assert normalizar_municipio("Itagüí") == "itagui"

    def test_itagui_acento(self):
        assert normalizar_municipio("Itaguí") == "itagui"

    def test_envigado(self):
        assert normalizar_municipio("envigado") == "envigado"

    def test_sabaneta(self):
        assert normalizar_municipio("SABANETA") == "sabaneta"

    def test_la_estrella_con_espacio(self):
        assert normalizar_municipio("la estrella") == "la_estrella"

    def test_none_fallback(self):
        assert normalizar_municipio("") == "medellin"

    def test_desconocido_fallback(self):
        assert normalizar_municipio("Bogotá") == "medellin"

    def test_todos_validos_en_set(self):
        for municipio in MUNICIPIOS_VALIDOS:
            # El resultado de normalizar un slug válido debe estar en MUNICIPIOS_VALIDOS
            result = normalizar_municipio(municipio)
            assert result in MUNICIPIOS_VALIDOS, f"{municipio} → {result} no está en MUNICIPIOS_VALIDOS"


# ═══════════════════════════════════════════════════════════════
# normalizar_categoria
# ═══════════════════════════════════════════════════════════════


class TestNormalizarCategoria:
    def test_categoria_valida(self):
        assert normalizar_categoria("teatro") == "teatro"

    def test_alias_musica(self):
        assert normalizar_categoria("musica") == "musica_en_vivo"

    def test_alias_concierto(self):
        assert normalizar_categoria("concierto") == "musica_en_vivo"

    def test_alias_exposicion(self):
        assert normalizar_categoria("exposicion") == "galeria"

    def test_alias_workshop(self):
        assert normalizar_categoria("workshop") == "taller"

    def test_alias_charla(self):
        assert normalizar_categoria("charla") == "conferencia"

    def test_alias_punk(self):
        assert normalizar_categoria("punk") == "rock"

    def test_alias_rap(self):
        assert normalizar_categoria("rap") == "hip_hop"

    def test_alias_techno(self):
        assert normalizar_categoria("techno") == "electronica"

    def test_desconocida_retorna_otro(self):
        assert normalizar_categoria("algo_raro") == "otro"

    def test_vacio_retorna_otro(self):
        assert normalizar_categoria("") == "otro"

    def test_mayusculas(self):
        assert normalizar_categoria("TEATRO") == "teatro"

    def test_espacio_a_underscore(self):
        assert normalizar_categoria("musica en vivo") == "musica_en_vivo"

    def test_todos_validos_en_set(self):
        for cat in CATEGORIAS_VALIDAS:
            result = normalizar_categoria(cat)
            assert result in CATEGORIAS_VALIDAS, f"{cat} → {result} no está en CATEGORIAS_VALIDAS"


# ═══════════════════════════════════════════════════════════════
# normalizar_instagram
# ═══════════════════════════════════════════════════════════════


class TestNormalizarInstagram:
    def test_url_completa(self):
        assert normalizar_instagram("https://instagram.com/teatromatacandelas/") == "@teatromatacandelas"

    def test_url_con_query(self):
        assert normalizar_instagram("https://www.instagram.com/teatromatacandelas?hl=es") == "@teatromatacandelas"

    def test_handle_con_arroba(self):
        assert normalizar_instagram("@colectivojazz") == "@colectivojazz"

    def test_handle_sin_arroba(self):
        assert normalizar_instagram("colectivojazz") == "@colectivojazz"

    def test_handle_mayusculas(self):
        assert normalizar_instagram("@ColectivoJazz") == "@colectivojazz"

    def test_handle_con_punto_underscore(self):
        assert normalizar_instagram("@colectivo.hip_hop") == "@colectivo.hip_hop"

    def test_none_retorna_none(self):
        assert normalizar_instagram("") is None

    def test_invalido_retorna_none(self):
        assert normalizar_instagram("no es un handle!") is None


# ═══════════════════════════════════════════════════════════════
# normalizar_precio
# ═══════════════════════════════════════════════════════════════


class TestNormalizarPrecio:
    def test_gratis(self):
        precio, es_gratuito = normalizar_precio("gratis")
        assert es_gratuito is True
        assert precio == "Entrada libre"

    def test_gratuito(self):
        _, es_gratuito = normalizar_precio("Gratuito")
        assert es_gratuito is True

    def test_entrada_libre(self):
        _, es_gratuito = normalizar_precio("Entrada libre")
        assert es_gratuito is True

    def test_free(self):
        _, es_gratuito = normalizar_precio("free")
        assert es_gratuito is True

    def test_sin_costo(self):
        _, es_gratuito = normalizar_precio("Sin costo")
        assert es_gratuito is True

    def test_precio_numerico(self):
        precio, es_gratuito = normalizar_precio("$50.000")
        assert es_gratuito is False
        assert precio == "$50.000"

    def test_vacio(self):
        precio, es_gratuito = normalizar_precio("")
        assert es_gratuito is False
        assert precio == ""

    def test_none_like(self):
        precio, es_gratuito = normalizar_precio("no especificado")
        assert es_gratuito is False


# ═══════════════════════════════════════════════════════════════
# normalizar_evento
# ═══════════════════════════════════════════════════════════════


def _fecha_futura(dias: int = 7) -> str:
    """Retorna una fecha futura válida como ISO string."""
    return (datetime.utcnow() + timedelta(days=dias)).isoformat()


class TestNormalizarEvento:
    def test_evento_basico_valido(self):
        raw = {
            "titulo": "Concierto de Jazz",
            "fecha_inicio": _fecha_futura(7),
            "municipio": "Medellín",
            "categoria_principal": "jazz",
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert ev["titulo"] == "Concierto de Jazz"
        assert ev["municipio"] == "medellin"
        assert ev["categoria_principal"] == "jazz"
        assert ev["slug"] == "concierto-de-jazz"

    def test_titulo_vacio_retorna_none(self):
        assert normalizar_evento({"titulo": "", "fecha_inicio": _fecha_futura()}) is None

    def test_titulo_muy_corto_retorna_none(self):
        assert normalizar_evento({"titulo": "AB", "fecha_inicio": _fecha_futura()}) is None

    def test_sin_fecha_retorna_none(self):
        assert normalizar_evento({"titulo": "Evento sin fecha"}) is None

    def test_fecha_invalida_retorna_none(self):
        assert normalizar_evento({"titulo": "Evento", "fecha_inicio": "no es fecha"}) is None

    def test_fecha_muy_pasada_retorna_none(self):
        hace_30_dias = (datetime.utcnow() - timedelta(days=30)).isoformat()
        assert normalizar_evento({"titulo": "Evento antiguo", "fecha_inicio": hace_30_dias}) is None

    def test_fecha_muy_futura_retorna_none(self):
        en_2_años = (datetime.utcnow() + timedelta(days=800)).isoformat()
        assert normalizar_evento({"titulo": "Evento futuro", "fecha_inicio": en_2_años}) is None

    def test_evento_gratuito(self):
        raw = {
            "titulo": "Concierto Gratis",
            "fecha_inicio": _fecha_futura(3),
            "precio": "Entrada libre",
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert ev["es_gratuito"] is True

    def test_precio_normalizado(self):
        raw = {
            "titulo": "Evento de Pago",
            "fecha_inicio": _fecha_futura(3),
            "precio": "$30.000",
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert ev["precio"] == "$30.000"
        assert ev["es_gratuito"] is False

    def test_descripcion_truncada(self):
        raw = {
            "titulo": "Evento largo",
            "fecha_inicio": _fecha_futura(5),
            "descripcion": "x" * 1000,
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert len(ev["descripcion"]) <= 500

    def test_titulo_truncado(self):
        raw = {
            "titulo": "T" * 300,
            "fecha_inicio": _fecha_futura(5),
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert len(ev["titulo"]) <= 200

    def test_categorias_normalizadas(self):
        raw = {
            "titulo": "Festival de Punk",
            "fecha_inicio": _fecha_futura(10),
            "categoria_principal": "punk",
            "categorias": ["metal", "punk", "rock"],
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert ev["categoria_principal"] == "rock"
        # Todas las categorías deben ser válidas
        for cat in ev["categorias"]:
            assert cat in CATEGORIAS_VALIDAS

    def test_instagram_normalizado(self):
        raw = {
            "titulo": "Evento con Instagram",
            "fecha_inicio": _fecha_futura(5),
            "instagram_handle": "https://instagram.com/colectivoarte/",
        }
        ev = normalizar_evento(raw)
        assert ev is not None
        assert ev.get("instagram_handle") is None or ev.get("instagram_handle") == "@colectivoarte"


# ═══════════════════════════════════════════════════════════════
# normalizar_lugar
# ═══════════════════════════════════════════════════════════════


class TestNormalizarLugar:
    def test_lugar_basico(self):
        raw = {
            "nombre": "Casa Tres Patios",
            "municipio": "Medellín",
            "categoria_principal": "galeria",
        }
        lugar = normalizar_lugar(raw)
        assert lugar is not None
        assert lugar["nombre"] == "Casa Tres Patios"
        assert lugar["slug"] == "casa-tres-patios"
        assert lugar["municipio"] == "medellin"

    def test_nombre_vacio_retorna_none(self):
        assert normalizar_lugar({"nombre": ""}) is None

    def test_nombre_muy_corto_retorna_none(self):
        assert normalizar_lugar({"nombre": "X"}) is None

    def test_instagram_normalizado(self):
        raw = {
            "nombre": "Teatro Metro",
            "instagram_handle": "@teatrometro",
        }
        lugar = normalizar_lugar(raw)
        assert lugar is not None
        assert lugar["instagram_handle"] == "@teatrometro"

    def test_tipo_default(self):
        raw = {"nombre": "Colectivo sin tipo"}
        lugar = normalizar_lugar(raw)
        assert lugar is not None
        assert lugar["tipo"] == "colectivo"

    def test_nombre_truncado(self):
        raw = {"nombre": "N" * 300}
        lugar = normalizar_lugar(raw)
        assert lugar is not None
        assert len(lugar["nombre"]) <= 200
