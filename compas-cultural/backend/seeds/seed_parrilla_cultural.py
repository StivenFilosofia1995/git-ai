"""
Seed — Parrilla Cultural Medellín
Agrega los espacios culturales clave que no estaban en el sistema.
Incluye teatros, librerías, bibliotecas, corporaciones y espacios independientes.
Ejecutar: python seeds/seed_parrilla_cultural.py
"""
import sys, os, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.database import supabase


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:250]


LUGARES = [
    # ── TEATROS GRANDES ────────────────────────────────────────────────────
    {
        "nombre": "Teatro Pablo Tobón Uribe",
        "tipo": "espacio_fisico",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "danza"],
        "municipio": "medellin",
        "barrio": "Jesús Nazareno",
        "comuna": "Boston",
        "direccion": "Carrera 40 #51-24, Medellín",
        "descripcion_corta": "Teatro principal de Medellín. Programación de teatro, música, danza y ópera.",
        "descripcion": "El Teatro Pablo Tobón Uribe es uno de los recintos culturales más importantes de Medellín y Colombia. Ofrece temporadas de teatro, música, danza, ballet y eventos especiales. Sede de producciones nacionales e internacionales.",
        "instagram_handle": "teatropablotobon",
        "sitio_web": "https://teatropablotobon.com/eventos/",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": True,
    },
    {
        "nombre": "Teatro Matacandelas",
        "tipo": "espacio_fisico",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo"],
        "municipio": "medellin",
        "barrio": "Boston",
        "direccion": "Calle 47 #43-47, Medellín",
        "descripcion_corta": "Colectivo teatral independiente fundado en 1979. Sala Matacandelas y Cabaret El Cantadero.",
        "descripcion": "Teatro Matacandelas es uno de los colectivos teatrales más longevos e importantes de Colombia. Con su Sala y el Cabaret El Cantadero, ofrece teatro, conciertos de rock, metal, jazz y eventos culturales diversos.",
        "instagram_handle": "teatromatacandelas",
        "sitio_web": "https://www.matacandelas.com/index.html",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "Teatro El Perpetuo Socorro",
        "tipo": "espacio_fisico",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "arte_contemporaneo", "taller"],
        "municipio": "medellin",
        "barrio": "Distrito Creativo",
        "direccion": "Calle 35 #46-63, Medellín",
        "descripcion_corta": "Teatro y espacio cultural del Distrito Creativo de Medellín. Obras, talleres y eventos.",
        "descripcion": "El Perpetuo Socorro es un espacio cultural ubicado en el Distrito Creativo de Medellín. Ofrece programación de teatro, danza, talleres creativos y eventos artísticos de diversas disciplinas.",
        "instagram_handle": "elperpetuosocorro",
        "sitio_web": "https://www.elperpetuosocorro.org/",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "AgiTeatro",
        "tipo": "colectivo",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza"],
        "municipio": "medellin",
        "barrio": "Centro",
        "descripcion_corta": "Colectivo y escuela de teatro en Medellín con programación propia y formación.",
        "descripcion": "AgiTeatro es un espacio de formación y creación teatral en Medellín. Desarrolla temporadas de teatro, talleres de actuación y proyectos de teatro comunitario.",
        "instagram_handle": "agiteatro",
        "sitio_web": "https://agiteatro.co",
        "nivel_actividad": "activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "Teatro Teococ",
        "tipo": "espacio_fisico",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "taller"],
        "municipio": "medellin",
        "barrio": "Laureles",
        "descripcion_corta": "Espacio teatral con temporadas propias, talleres de formación y alquiler de sala.",
        "descripcion": "Teatro Teococ es un espacio cultural dedicado a las artes escénicas en Medellín. Ofrece temporadas de teatro, danza y programas de formación artística.",
        "instagram_handle": "teatroteococ",
        "sitio_web": "https://www.teatroteococ.com",
        "nivel_actividad": "activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "TeatroScena",
        "tipo": "colectivo",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza"],
        "municipio": "medellin",
        "barrio": "El Poblado",
        "descripcion_corta": "Compañía y espacio teatral con producción propia y formación escénica.",
        "instagram_handle": "teatroscena",
        "nivel_actividad": "activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "Casa Taller Madriguera",
        "tipo": "colectivo",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "arte_contemporaneo", "taller"],
        "municipio": "medellin",
        "barrio": "La América",
        "descripcion_corta": "Casa taller de artes escénicas y corporales. Residencias, talleres y creación colectiva.",
        "descripcion": "Casa Taller Madriguera es un espacio de investigación y creación en artes del cuerpo y escénicas. Ofrece talleres, residencias artísticas y presentaciones de trabajo en proceso.",
        "instagram_handle": "casatallermadriguera",
        "nivel_actividad": "activo",
        "es_underground": True,
        "es_institucional": False,
    },
    {
        "nombre": "Altavista Corporación Cultural",
        "tipo": "colectivo",
        "categoria_principal": "centro_cultural",
        "categorias": ["teatro", "danza", "musica_en_vivo", "taller"],
        "municipio": "medellin",
        "barrio": "Altavista",
        "descripcion_corta": "Corporación cultural del corregimiento de Altavista. Arte, cultura y territorio.",
        "descripcion": "Altavista Corporación Cultural trabaja el arte y la cultura como herramientas de transformación social en el corregimiento de Altavista, Medellín.",
        "instagram_handle": "altavistacorpo",
        "sitio_web": "https://altavistacorpo.com",
        "nivel_actividad": "activo",
        "es_underground": True,
        "es_institucional": False,
    },

    # ── LIBRERÍAS ──────────────────────────────────────────────────────────
    {
        "nombre": "Librería Café Exlibris",
        "tipo": "espacio_fisico",
        "categoria_principal": "libreria",
        "categorias": ["libreria", "poesia", "editorial"],
        "municipio": "medellin",
        "barrio": "El Poblado",
        "descripcion_corta": "Librería, café y repostería en Medellín. Libros, eventos literarios y espacios de encuentro.",
        "descripcion": "Exlibris es una librería-café en Medellín con amplio catálogo de libros, novedades editoriales, papelería y programación de eventos literarios, charlas y presentaciones de libros.",
        "instagram_handle": "cafexlibris",
        "sitio_web": "https://www.exlibris.com.co/",
        "nivel_actividad": "activo",
        "es_underground": False,
        "es_institucional": False,
    },
    {
        "nombre": "El Ateneo – Librería Porfirio Barba Jacob",
        "tipo": "espacio_fisico",
        "categoria_principal": "libreria",
        "categorias": ["libreria", "poesia", "editorial", "filosofia"],
        "municipio": "medellin",
        "barrio": "El Poblado",
        "descripcion_corta": "Librería cultural con enfoque en literatura colombiana y poesía. Homenaje a Porfirio Barba Jacob.",
        "descripcion": "El Ateneo es una librería cultural en Medellín dedicada a la literatura, la poesía y el pensamiento. Rinde homenaje al poeta Porfirio Barba Jacob y promueve la cultura literaria antioqueña.",
        "instagram_handle": "elateneomedellin",
        "nivel_actividad": "activo",
        "es_underground": False,
        "es_institucional": False,
    },

    # ── BIBLIOTECAS ─────────────────────────────────────────────────────────
    {
        "nombre": "Biblioteca Pública Piloto de Medellín",
        "tipo": "espacio_fisico",
        "categoria_principal": "casa_cultura",
        "categorias": ["casa_cultura", "cine", "poesia", "taller", "conferencia"],
        "municipio": "medellin",
        "barrio": "Carlos E. Restrepo",
        "comuna": "La América",
        "direccion": "Calle 44 #39-100, Medellín",
        "descripcion_corta": "Biblioteca pública más importante de Medellín. Programación cultural, talleres, cine y exposiciones.",
        "descripcion": "La Biblioteca Pública Piloto es la institución bibliotecaria más importante de Medellín y una de las más destacadas de Colombia. Ofrece una programación cultural amplia: cine, talleres, clubs de lectura, conferencias, exposiciones y eventos infantiles.",
        "instagram_handle": "bppiloto",
        "sitio_web": "https://bibliotecapiloto.gov.co/agenda",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": True,
    },
    {
        "nombre": "Sistema de Bibliotecas Públicas de Medellín",
        "tipo": "programa_institucional",
        "categoria_principal": "casa_cultura",
        "categorias": ["casa_cultura", "taller", "poesia", "cine"],
        "municipio": "medellin",
        "barrio": "Centro",
        "descripcion_corta": "Red de parques-biblioteca y bibliotecas barriales de Medellín. España, La Ladera, Belén, La Quintana, etc.",
        "descripcion": "El Sistema de Bibliotecas Públicas de Medellín comprende los parques-biblioteca (España, La Ladera, San Javier, Belén, La Quintana, La Floresta) y bibliotecas barriales con programación cultural, talleres y actividades comunitarias.",
        "instagram_handle": "bibliotecasmedellin",
        "sitio_web": "https://www.medellin.gov.co/es/sistema-de-bibliotecas/",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": True,
    },

    # ── COMFAMA / COMFENALCO ────────────────────────────────────────────────
    {
        "nombre": "Comfenalco Antioquia – Agenda Cultural",
        "tipo": "programa_institucional",
        "categoria_principal": "centro_cultural",
        "categorias": ["teatro", "musica_en_vivo", "taller", "cine", "danza"],
        "municipio": "medellin",
        "barrio": "El Centro",
        "descripcion_corta": "Caja de compensación con amplia agenda cultural: teatro, talleres, cine y eventos para toda la familia.",
        "descripcion": "Comfenalco Antioquia ofrece una de las agendas culturales más amplias del Valle de Aburrá: espectáculos de teatro, conciertos, talleres de arte, cine y actividades para niños y adultos en sus sedes.",
        "instagram_handle": "comfenalcoant",
        "sitio_web": "https://www.comfenalcoantioquia.com.co/personas/eventos",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": True,
    },
    {
        "nombre": "Fundación EPM – Agenda Cultural",
        "tipo": "programa_institucional",
        "categoria_principal": "centro_cultural",
        "categorias": ["teatro", "musica_en_vivo", "taller", "conferencia"],
        "municipio": "medellin",
        "barrio": "El Centro",
        "direccion": "Carrera 58 #42-125, Medellín",
        "descripcion_corta": "Fundación de EPM con programación cultural, espectáculos y proyectos educativos en el Valle de Aburrá.",
        "descripcion": "La Fundación EPM desarrolla proyectos culturales, educativos y sociales en Medellín y Antioquia. Ofrece programación de artes escénicas, música y eventos en espacios propios.",
        "instagram_handle": "fundacionepm",
        "sitio_web": "https://www.fundacionepm.org.co/",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": True,
    },

    # ── DISTRITOS CULTURALES ────────────────────────────────────────────────
    {
        "nombre": "Distrito San Ignacio – Agenda Cultural",
        "tipo": "red_articuladora",
        "categoria_principal": "centro_cultural",
        "categorias": ["teatro", "galeria", "libreria", "musica_en_vivo", "poesia", "filosofia"],
        "municipio": "medellin",
        "barrio": "San Ignacio / Centro Histórico",
        "comuna": "La Candelaria",
        "descripcion_corta": "Distrito cultural del centro histórico de Medellín. 62 hectáreas con teatros, galerías, librerías y bares.",
        "descripcion": "El Distrito San Ignacio es el corazón cultural del centro histórico de Medellín: 62 hectáreas con teatros, librerías, galerías, bares culturales, instituciones educativas y espacios bohemios. Articula más de 40 organizaciones culturales.",
        "instagram_handle": "distritosanignacio",
        "sitio_web": "http://agendacultural.distritosanignacio.com/",
        "nivel_actividad": "muy_activo",
        "es_underground": False,
        "es_institucional": False,
    },

    # ── COLECTIVOS INDEPENDIENTES ──────────────────────────────────────────
    {
        "nombre": "Colectivo Aymuray",
        "tipo": "colectivo",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "danza", "teatro"],
        "municipio": "medellin",
        "barrio": "Popular",
        "descripcion_corta": "Colectivo de música andina, danza y expresiones culturales ancestrales en Medellín.",
        "descripcion": "Colectivo Aymuray trabaja la música andina colombiana y latinoamericana, la danza folclórica y las expresiones culturales de raíz en Medellín. Conciertos, talleres y trabajo comunitario.",
        "instagram_handle": "colectivoaymuray",
        "nivel_actividad": "activo",
        "es_underground": True,
        "es_institucional": False,
    },
    {
        "nombre": "Colectivo VII",
        "tipo": "colectivo",
        "categoria_principal": "arte_contemporaneo",
        "categorias": ["arte_contemporaneo", "galeria", "fotografia", "muralismo"],
        "municipio": "medellin",
        "barrio": "Laureles",
        "descripcion_corta": "Colectivo de artes visuales, fotografía y arte contemporáneo en Medellín.",
        "descripcion": "Colectivo VII es un grupo de artistas visuales de Medellín que trabaja en fotografía, arte contemporáneo, instalaciones y muralismo. Exposiciones, intervenciones urbanas y publicaciones.",
        "instagram_handle": "colectivo_vii",
        "nivel_actividad": "activo",
        "es_underground": True,
        "es_institucional": False,
    },
    {
        "nombre": "Eticketa Blanca",
        "tipo": "colectivo",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "hip_hop", "electronica", "festival"],
        "municipio": "medellin",
        "barrio": "Boston",
        "descripcion_corta": "Productora y colectivo musical underground de Medellín. Hip-hop, electrónica y eventos culturales.",
        "descripcion": "Eticketa Blanca es un colectivo y productora musical de Medellín especializada en hip-hop, electrónica y música underground. Organiza conciertos, festivales y eventos en el Matacandelas y otros espacios.",
        "instagram_handle": "eticketablanca",
        "sitio_web": "https://www.eticketablanca.com/",
        "nivel_actividad": "activo",
        "es_underground": True,
        "es_institucional": False,
    },
]


def seed():
    insertados = 0
    actualizados = 0
    errores = 0

    for lugar in LUGARES:
        nombre = lugar["nombre"]
        slug = slugify(nombre)
        lugar["slug"] = slug

        try:
            # Check if already exists by slug or sitio_web
            existing = None
            check = supabase.table("lugares").select("id, slug").eq("slug", slug).execute()
            if check.data:
                existing = check.data[0]

            if not existing and lugar.get("sitio_web"):
                check2 = supabase.table("lugares").select("id, slug").eq("sitio_web", lugar["sitio_web"]).execute()
                if check2.data:
                    existing = check2.data[0]

            if existing:
                supabase.table("lugares").update(lugar).eq("id", existing["id"]).execute()
                print(f"  ↻ Actualizado: {nombre}")
                actualizados += 1
            else:
                supabase.table("lugares").insert(lugar).execute()
                print(f"  ✓ Insertado:  {nombre}")
                insertados += 1

        except Exception as e:
            print(f"  ✗ Error con {nombre}: {e}")
            errores += 1

    print(f"\n{'='*50}")
    print(f"Insertados: {insertados} | Actualizados: {actualizados} | Errores: {errores}")
    print(f"Total: {len(LUGARES)} espacios procesados")


if __name__ == "__main__":
    print("🎭 Seeding parrilla cultural de Medellín...\n")
    seed()
    print("\n✅ Listo. El auto-scraper usará estas webs en el próximo ciclo.")
