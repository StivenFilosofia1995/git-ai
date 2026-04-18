# -*- coding: utf-8 -*-
"""
Configuración del módulo de descubrimiento.
Categorías, hashtags, plantillas de búsqueda, fuentes directas.
"""

# ── Municipios del Valle de Aburrá ───────────────────────────
MUNICIPIOS = [
    "Medellín", "Bello", "Itagüí", "Envigado", "Sabaneta",
    "La Estrella", "Caldas", "Copacabana", "Girardota", "Barbosa",
]

MUNICIPIO_SLUG_MAP = {
    "medellín": "medellin", "medellin": "medellin",
    "bello": "bello", "itagüí": "itagui", "itagui": "itagui",
    "envigado": "envigado", "sabaneta": "sabaneta",
    "la estrella": "la_estrella", "caldas": "caldas",
    "copacabana": "copacabana", "girardota": "girardota",
    "barbosa": "barbosa", "valle de aburrá": "medellin",
}

# ── Categorías culturales con keywords ───────────────────────
CATEGORIAS = {
    "filosofia": [
        "filosofía", "filosofico", "pensamiento crítico", "café filosófico",
        "club de filosofía", "círculo filosófico", "filosofía práctica",
        "seminario filosofía", "grupo filosofía", "tertulia filosófica",
    ],
    "teatro": [
        "teatro", "artes escénicas", "dramaturgia", "performance",
        "grupo de teatro", "compañía de teatro", "teatro comunitario",
        "teatro independiente", "improvisación teatral", "títeres",
        "teatro experimental", "sala de teatro", "escuela de teatro",
    ],
    "musica": [
        "música", "colectivo musical", "ensamble", "orquesta",
        "coro", "grupo musical", "escuela de música", "banda",
        "festival de música", "jam session", "producción musical",
        "hip hop", "rap", "rock", "jazz", "música urbana",
        "música andina", "música folclórica", "trova",
    ],
    "literatura": [
        "literatura", "club de lectura", "poesía", "escritura creativa",
        "taller literario", "editorial independiente", "fanzine",
        "colectivo literario", "revista literaria", "narrativa",
        "slam poetry", "spoken word", "biblioteca comunitaria",
        "círculo de lectura", "tertulia literaria",
    ],
    "arte_general": [
        "colectivo cultural", "colectivo artístico", "gestión cultural",
        "arte urbano", "galería", "centro cultural", "casa de la cultura",
        "corporación cultural", "fundación cultural", "espacio cultural",
        "cultura ciudadana", "arte comunitario", "festival cultural",
        "danza", "cine club", "fotografía", "artes plásticas",
        "artes visuales", "grafiti", "muralismo",
    ],
    "cine": [
        "cine", "cineclub", "cine club", "cortometraje", "largometraje",
        "audiovisual", "documental", "cinemateca", "festival de cine",
        "producción audiovisual", "realización audiovisual", "filmmaker",
        "cine colombiano", "cine independiente", "cine comunitario",
    ],
    "fotografia": [
        "fotografía", "fotógrafo", "foto análoga", "fotografía analógica",
        "fotografía documental", "fotoperiodismo", "foto callejera",
        "laboratorio fotográfico", "colectivo fotográfico", "exposición fotográfica",
    ],
    "danza": [
        "danza", "danza contemporánea", "danza aérea", "ballet",
        "danza urbana", "danza folclórica", "biodanza", "compañía de danza",
        "escuela de danza", "coreografía",
    ],
}

# ── Hashtags de Instagram para monitoreo ─────────────────────
HASHTAGS_MEDELLIN = [
    # Cultura general
    "colectivocultural", "culturamedellin", "culturaantioquia",
    "valledeaburra", "gestorcultural", "agendaculturalmedellin",
    "eventosculturalesmedellin", "quehacerenmedellin", "medellincultural",
    "comunitariomedellin",
    # Teatro
    "teatromedellin", "teatroindependiente", "artescenicas",
    "teatroantioquia",
    # Música
    "musicamedellin", "rapmedellin", "hiphopmedellín",
    "jazzmedellin", "rockmedellin", "musicaenvivo",
    "altavozmedellin", "conciertomedellin",
    # Literatura
    "literaturamedellin", "poesiamedellin", "clublecturamedellin",
    "editorialindependiente", "fanzinecolombia", "tertulialiteraria",
    # Filosofía
    "filosofiamedellin", "cafefilosofico",
    # Arte y espacios
    "artesmedellin", "arteurbano", "muralismomedellin",
    "galeriamedellin", "exposicionmedellin",
    # Cine
    "cineclubmedellin", "cinemedellin", "cortometrajemedellin",
    "cinecolombia", "documentalmedellin",
    # Fotografía
    "fotomedellin", "fotografiamedellin", "fotografiaanalogamedellin",
    "fotostreet",
    # Danza
    "danzamedellin", "danzacontemporanea",
    # Festivales
    "festivalmedellin", "festivalcultural",
    # Municipios
    "culturasabaneta", "culturaenvigado", "culturabello",
    "culturaitagui", "culturacopacabana",
]

# ── Plantillas de búsqueda Google ────────────────────────────
GOOGLE_QUERY_TEMPLATES = [
    'site:instagram.com "{keyword}" "{municipio}" colectivo',
    'site:instagram.com colectivo cultural "{keyword}" medellín',
    'site:facebook.com "{keyword}" "{municipio}" colectivo',
    'site:facebook.com colectivo cultural "{keyword}" "valle de aburrá"',
    'colectivo "{keyword}" "{municipio}" @',
    'colectivo cultural "{keyword}" "{municipio}" instagram',
    '"{keyword}" "{municipio}" colectivo OR fundación OR corporación',
]

# ── Fuentes directas — directorios culturales ────────────────
FUENTES_DIRECTAS = [
    "https://www.medellincultura.gov.co",
    "https://www.medellin.gov.co/es/secretaria-de-cultura-ciudadana/",
    "https://patrimoniomedellin.gov.co",
    "https://www.viztaz.com.co",
    "https://www.colombiacultura.co",
    "https://www.timeout.com/medellin/things-to-do",
    "https://www.civico.com/medellin/cultura",
    "https://tefresco.co",
    "https://reddebibliotecas.org.co",
    "https://www.comfama.com/cultura-y-ocio/",
    "https://www.comfenalcoantioquia.com.co/cultura",
]

# ── Búsquedas específicas para Facebook ──────────────────────
FB_SEARCH_QUERIES = []
for _cat, _keywords in CATEGORIAS.items():
    for _kw in _keywords[:5]:
        for _mun in MUNICIPIOS[:4]:
            FB_SEARCH_QUERIES.append({
                "q": f"colectivo {_kw} {_mun}",
                "categoria": _cat,
                "municipio": _mun,
            })

# ── Límites ──────────────────────────────────────────────────
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 6
MAX_GOOGLE_RESULTS = 50
MAX_RETRIES = 3
TIMEOUT = 30

# ── Headers base ─────────────────────────────────────────────
BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
}
