"""
Seed script: inserts real Medellín cultural data into Supabase via REST API.
Run: python -m seeds.seed_db   (from the backend/ directory)
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent dir so 'app' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase

_now = datetime.utcnow()
_tomorrow = _now + timedelta(days=1)
_next_week = _now + timedelta(days=5)
_next_month = _now + timedelta(days=30)
_two_months = _now + timedelta(days=60)


ZONAS = [
    dict(nombre="Ciudad del Río", slug="ciudad-del-rio",
         descripcion="Distrito de arte y cultura contemporánea alrededor del MAMM. Galerías, restaurantes y espacios creativos en antiguas bodegas industriales renovadas.",
         vocacion="Arte contemporáneo y galerías", municipio="medellin"),
    dict(nombre="Barrio Prado", slug="barrio-prado",
         descripcion="Patrimonio arquitectónico republicano con casonas históricas convertidas en centros culturales. Cuna del teatro independiente de Medellín.",
         vocacion="Teatro y patrimonio", municipio="medellin"),
    dict(nombre="El Poblado - Manila", slug="el-poblado-manila",
         descripcion="Circuito gastronómico y de música en vivo. Bares con escena de jazz, electrónica y rock independiente.",
         vocacion="Música en vivo y vida nocturna cultural", municipio="medellin"),
    dict(nombre="Centro - La Candelaria", slug="centro-la-candelaria",
         descripcion="Corazón histórico con el Museo de Antioquia, Plaza Botero, Teatro Pablo Tobón Uribe y múltiples galerías independientes.",
         vocacion="Museos, teatro y arte público", municipio="medellin"),
    dict(nombre="Laureles - Estadio", slug="laureles-estadio",
         descripcion="Zona de cafés culturales, librerías independientes y espacios de spoken word. Epicentro de la escena literaria y poética.",
         vocacion="Literatura, cafés culturales y poesía", municipio="medellin"),
    dict(nombre="Comuna 13 - San Javier", slug="comuna-13-san-javier",
         descripcion="Referente mundial de transformación urbana a través del arte. Graffiti tours, hip-hop, breakdance y emprendimientos culturales comunitarios.",
         vocacion="Hip-hop, muralismo y arte urbano", municipio="medellin"),
    dict(nombre="Envigado Centro", slug="envigado-centro",
         descripcion="Escena cultural emergente con bares de rock, galerías pequeñas y la tradición del Festival de Cine. Pueblo dentro de la ciudad.",
         vocacion="Cine independiente y rock alternativo", municipio="envigado"),
    dict(nombre="Parque Explora - Jardín Botánico", slug="parque-explora-jardin-botanico",
         descripcion="Corredor de ciencia, naturaleza y cultura. Planetario, acuario, Jardín Botánico y Universidad de Antioquia conforman un ecosistema educativo-cultural único.",
         vocacion="Ciencia, educación y naturaleza", municipio="medellin"),
]

ESPACIOS = [
    dict(
        nombre="Museo de Arte Moderno de Medellín (MAMM)", slug="museo-de-arte-moderno-de-medellin",
        tipo="espacio_fisico", categorias=["arte_contemporaneo","galeria","fotografia"],
        categoria_principal="arte_contemporaneo", municipio="medellin", barrio="Ciudad del Río",
        comuna="14 - El Poblado", direccion="Cra. 44 #19A-100", lat=6.2282, lng=-75.5743,
        descripcion_corta="Principal museo de arte moderno y contemporáneo de Medellín.",
        descripcion="El MAMM es el epicentro del arte contemporáneo en Medellín, con exposiciones rotativas de artistas nacionales e internacionales, cine, talleres y una terraza con vista al río.",
        instagram_handle="@elmamm", instagram_seguidores=185000, sitio_web="https://elmamm.org",
        nivel_actividad="muy_activo", es_underground=False, es_institucional=True, año_fundacion=1978,
    ),
    dict(
        nombre="Teatro Matacandelas", slug="teatro-matacandelas",
        tipo="espacio_fisico", categorias=["teatro","danza"],
        categoria_principal="teatro", municipio="medellin", barrio="Prado",
        comuna="10 - La Candelaria", direccion="Calle 47 #43-47", lat=6.2552, lng=-75.5640,
        descripcion_corta="Ícono del teatro independiente colombiano desde 1979.",
        descripcion="Matacandelas es una de las compañías de teatro más importantes de Colombia. Su sede en el barrio Prado alberga funciones semanales, talleres y un bar cultural.",
        instagram_handle="@teatromatacandelas", sitio_web="https://matacandelas.com",
        nivel_actividad="muy_activo", es_underground=False, es_institucional=False, año_fundacion=1979,
    ),
    dict(
        nombre="Casa Teatro El Poblado", slug="casa-teatro-el-poblado",
        tipo="espacio_fisico", categorias=["teatro","musica_en_vivo"],
        categoria_principal="teatro", municipio="medellin", barrio="El Poblado",
        comuna="14 - El Poblado", direccion="Cra. 43A #25-38", lat=6.2105, lng=-75.5699,
        descripcion_corta="Pequeño teatro íntimo con programación variada de artes escénicas.",
        descripcion="Espacio independiente para teatro, música acústica y spoken word en el corazón de El Poblado. Ambiente íntimo para max 80 personas.",
        instagram_handle="@casateatroelpoblado",
        nivel_actividad="activo", es_underground=True, es_institucional=False, año_fundacion=2015,
    ),
    dict(
        nombre="Salón Málaga", slug="salon-malaga",
        tipo="espacio_fisico", categorias=["musica_en_vivo"],
        categoria_principal="musica_en_vivo", municipio="medellin", barrio="Centro",
        comuna="10 - La Candelaria", direccion="Cra. 51 #45-80", lat=6.2480, lng=-75.5660,
        descripcion_corta="Legendario bar de tango con más de 80 años de historia.",
        descripcion="El Salón Málaga es patrimonio vivo de la cultura tanguera de Medellín. Aquí soñaban tangos los abuelos y hoy convive la historia con nuevas generaciones.",
        instagram_handle="@salonmalaga",
        nivel_actividad="historico", es_underground=False, es_institucional=False, año_fundacion=1957,
    ),
    dict(
        nombre="Casa Tres Patios", slug="casa-tres-patios",
        tipo="espacio_fisico", categorias=["arte_contemporaneo","galeria"],
        categoria_principal="arte_contemporaneo", municipio="medellin", barrio="El Poblado",
        comuna="14 - El Poblado", direccion="Cra. 50A #63sur-55", lat=6.2028, lng=-75.5694,
        descripcion_corta="Espacio independiente de arte contemporáneo y residencias artísticas.",
        descripcion="Organización sin ánimo de lucro dedicada al arte contemporáneo, educación artística y residencias para artistas internacionales.",
        instagram_handle="@casatrespatios", sitio_web="https://casatrespatios.org",
        nivel_actividad="activo", es_underground=True, es_institucional=False, año_fundacion=2006,
    ),
    dict(
        nombre="La Pascasia", slug="la-pascasia",
        tipo="espacio_fisico", categorias=["musica_en_vivo","jazz"],
        categoria_principal="jazz", municipio="medellin", barrio="Laureles",
        comuna="11 - Laureles Estadio", direccion="Cra. 73 #circular 1-55", lat=6.2460, lng=-75.5900,
        descripcion_corta="Bar cultural con jazz en vivo, vinilos y coctelería artesanal.",
        descripcion="Espacio de música en vivo en Laureles con noches de jazz, blues y bossa nova. Colección de vinilos y ambiente bohemio.",
        instagram_handle="@lapascasia",
        nivel_actividad="activo", es_underground=True, es_institucional=False, año_fundacion=2018,
    ),
    dict(
        nombre="Museo de Antioquia", slug="museo-de-antioquia",
        tipo="espacio_fisico", categorias=["galeria","arte_contemporaneo"],
        categoria_principal="galeria", municipio="medellin", barrio="Centro",
        comuna="10 - La Candelaria", direccion="Calle 52 #52-43, Plaza Botero", lat=6.2518, lng=-75.5636,
        descripcion_corta="El museo más importante de Antioquia, sede de la colección Botero.",
        descripcion="Museo insignia de Medellín con la colección más importante de obras de Fernando Botero, arte colombiano y exposiciones temporales internacionales.",
        instagram_handle="@museodeantioquia", sitio_web="https://museodeantioquia.co",
        nivel_actividad="muy_activo", es_underground=False, es_institucional=True, año_fundacion=1881,
    ),
    dict(
        nombre="Casa Gardeliana", slug="casa-gardeliana",
        tipo="espacio_fisico", categorias=["musica_en_vivo","casa_cultura"],
        categoria_principal="casa_cultura", municipio="medellin", barrio="Manrique",
        comuna="3 - Manrique", direccion="Cra. 45 #76-50", lat=6.2740, lng=-75.5488,
        descripcion_corta="Museo vivo del tango dedicado a Carlos Gardel y la cultura tanguera de Medellín.",
        descripcion="Museo-bar donde se preserva la memoria de Carlos Gardel en Medellín. Milongas los fines de semana, clases de tango y una colección de objetos históricos.",
        instagram_handle="@casagardeliana",
        nivel_actividad="activo", es_underground=False, es_institucional=False, año_fundacion=1973,
    ),
    dict(
        nombre="Centro Colombo Americano", slug="centro-colombo-americano",
        tipo="espacio_fisico", categorias=["galeria","fotografia","cine"],
        categoria_principal="galeria", municipio="medellin", barrio="Centro",
        comuna="10 - La Candelaria", direccion="Cra. 45 #53-24", lat=6.2490, lng=-75.5630,
        descripcion_corta="Centro cultural con galería de fotografía, cine y biblioteca.",
        descripcion="Espacio cultural con la galería de fotografía más activa de Medellín, sala de cine alternativo y programación de artes visuales.",
        instagram_handle="@colomboamericano", sitio_web="https://colomboamericano.edu.co",
        nivel_actividad="muy_activo", es_underground=False, es_institucional=True, año_fundacion=1942,
    ),
    dict(
        nombre="Crew Peligrosos", slug="crew-peligrosos",
        tipo="colectivo", categorias=["hip_hop","batalla_freestyle","muralismo"],
        categoria_principal="hip_hop", municipio="medellin", barrio="San Javier",
        comuna="13 - San Javier", direccion="Calle 44 #100A-30", lat=6.2580, lng=-75.6140,
        descripcion_corta="Colectivo de hip-hop y transformación social en la Comuna 13.",
        descripcion="Crew Peligrosos es el colectivo cultural más emblemático de la Comuna 13. Hip-hop, breakdance, graffiti y procesos comunitarios que transformaron la historia del barrio.",
        instagram_handle="@crewpeligrosos", sitio_web="https://crewpeligrosos.com",
        nivel_actividad="muy_activo", es_underground=True, es_institucional=False, año_fundacion=2000,
    ),
]


def seed():
    print("ℹ️  Conectando a Supabase REST API...")

    # 1. Seed zonas
    for z in ZONAS:
        existing = supabase.table("zonas_culturales").select("id").eq("slug", z["slug"]).execute()
        if not existing.data:
            supabase.table("zonas_culturales").insert(z).execute()
    print(f"✅ {len(ZONAS)} zonas insertadas")

    # 2. Seed lugares — collect IDs for event references
    espacio_map = {}  # slug -> UUID
    for esp in ESPACIOS:
        existing = supabase.table("lugares").select("id,slug").eq("slug", esp["slug"]).execute()
        if existing.data:
            espacio_map[esp["slug"]] = existing.data[0]["id"]
            continue
        esp_row = {**esp, "fuente_datos": "investigacion_base"}
        resp = supabase.table("lugares").insert(esp_row).execute()
        if resp.data:
            espacio_map[esp["slug"]] = resp.data[0]["id"]
    print(f"✅ {len(ESPACIOS)} lugares insertados")

    # 3. Seed eventos (all future dates)
    EVENTOS = [
        dict(
            titulo="Noche de Jazz en La Pascasia", slug="noche-de-jazz-la-pascasia",
            espacio_slug="la-pascasia",
            fecha_inicio=_tomorrow.replace(hour=20, minute=0, second=0).isoformat(),
            fecha_fin=_tomorrow.replace(hour=23, minute=30, second=0).isoformat(),
            es_recurrente=True, patron_recurrencia={"dia": "viernes"},
            categorias=["jazz","musica_en_vivo"], categoria_principal="jazz",
            municipio="medellin", barrio="Laureles", nombre_lugar="La Pascasia",
            descripcion="Jazz en vivo todos los viernes con músicos locales e invitados especiales. Formato íntimo, coctelería artesanal.",
            precio="$20.000 cover", es_gratuito=False,
            fuente="instagram", fuente_url="https://instagram.com/lapascasia", verificado=True,
        ),
        dict(
            titulo="Graffiti Tour Comuna 13", slug="visita-guiada-comuna-13",
            espacio_slug="crew-peligrosos",
            fecha_inicio=_tomorrow.replace(hour=10, minute=0, second=0).isoformat(),
            fecha_fin=_tomorrow.replace(hour=13, minute=0, second=0).isoformat(),
            es_recurrente=True, patron_recurrencia={"dia": "sabado"},
            categorias=["hip_hop","muralismo"], categoria_principal="muralismo",
            municipio="medellin", barrio="San Javier",
            nombre_lugar="Comuna 13 - Escaleras Eléctricas",
            descripcion="Recorrido por los murales de la Comuna 13 con artistas locales que cuentan la historia de transformación del barrio a través del arte urbano.",
            es_gratuito=True, fuente="sitio_web", fuente_url="https://crewpeligrosos.com", verificado=True,
        ),
        dict(
            titulo="Exposición: Territorios Invisibles", slug="expo-temporal-mamm",
            espacio_slug="museo-de-arte-moderno-de-medellin",
            fecha_inicio=_tomorrow.replace(hour=10, minute=0, second=0).isoformat(),
            fecha_fin=_two_months.replace(hour=18, minute=0, second=0).isoformat(),
            es_recurrente=False,
            categorias=["arte_contemporaneo","fotografia"], categoria_principal="arte_contemporaneo",
            municipio="medellin", barrio="Ciudad del Río", nombre_lugar="MAMM - Sala Principal",
            descripcion="Muestra colectiva de artistas colombianos que exploran los territorios olvidados a través de fotografía, video e instalación.",
            precio="$18.000 general / $9.000 estudiantes", es_gratuito=False,
            fuente="sitio_web", fuente_url="https://elmamm.org", verificado=True,
        ),
        dict(
            titulo="Matacandelas: El último viaje de Julio Verne", slug="matacandelas-en-escena",
            espacio_slug="teatro-matacandelas",
            fecha_inicio=_tomorrow.replace(hour=19, minute=30, second=0).isoformat(),
            fecha_fin=_tomorrow.replace(hour=21, minute=30, second=0).isoformat(),
            es_recurrente=False,
            categorias=["teatro"], categoria_principal="teatro",
            municipio="medellin", barrio="Prado", nombre_lugar="Teatro Matacandelas",
            descripcion="Obra de la compañía residente inspirada en los viajes de Julio Verne. Dirección de Cristóbal Peláez, 45 años explorando la escena.",
            precio="$30.000", es_gratuito=False,
            fuente="instagram", fuente_url="https://instagram.com/teatromatacandelas", verificado=True,
        ),
        dict(
            titulo="Batalla de Freestyle - Plaza de la Resistencia", slug="batalla-de-freestyle-comuna13",
            espacio_slug="crew-peligrosos",
            fecha_inicio=_next_week.replace(hour=16, minute=0, second=0).isoformat(),
            fecha_fin=_next_week.replace(hour=20, minute=0, second=0).isoformat(),
            es_recurrente=True, patron_recurrencia={"dia": "domingo", "frecuencia": "quincenal"},
            categorias=["hip_hop","batalla_freestyle"], categoria_principal="batalla_freestyle",
            municipio="medellin", barrio="San Javier",
            nombre_lugar="Comuna 13 - Plaza de la Resistencia",
            descripcion="Batalla de freestyle abierta en la Plaza de la Resistencia. MC's de todo el Valle de Aburrá. Beat box y DJ en vivo.",
            es_gratuito=True, fuente="instagram", fuente_url="https://instagram.com/crewpeligrosos", verificado=True,
        ),
        dict(
            titulo="Milonga de los Sábados", slug="milonga-casa-gardeliana",
            espacio_slug="casa-gardeliana",
            fecha_inicio=_tomorrow.replace(hour=18, minute=0, second=0).isoformat(),
            fecha_fin=_tomorrow.replace(hour=22, minute=0, second=0).isoformat(),
            es_recurrente=True, patron_recurrencia={"dia": "sabado"},
            categorias=["musica_en_vivo","danza"], categoria_principal="danza",
            municipio="medellin", barrio="Manrique", nombre_lugar="Casa Gardeliana",
            descripcion="Milonga abierta todos los sábados. Clase de tango para principiantes a las 6 PM, baile social a las 7 PM. Orquesta en vivo una vez al mes.",
            precio="$15.000 con clase incluida", es_gratuito=False,
            fuente="instagram", fuente_url="https://instagram.com/casagardeliana", verificado=True,
        ),
        dict(
            titulo="Expo: Medellín desde el Lente Joven", slug="expo-fotografia-colombo",
            espacio_slug="centro-colombo-americano",
            fecha_inicio=_tomorrow.replace(hour=9, minute=0, second=0).isoformat(),
            fecha_fin=_next_month.replace(hour=17, minute=0, second=0).isoformat(),
            es_recurrente=False,
            categorias=["fotografia","galeria"], categoria_principal="fotografia",
            municipio="medellin", barrio="Centro",
            nombre_lugar="Centro Colombo Americano - Galería Paul Bardwell",
            descripcion="Exposición colectiva de fotógrafos emergentes menores de 30 años que retratan la Medellín contemporánea. Entrada libre.",
            es_gratuito=True, fuente="sitio_web", fuente_url="https://colomboamericano.edu.co", verificado=True,
        ),
        dict(
            titulo="Open Studio: Residencia Internacional 2026", slug="residencia-artistica-c3p",
            espacio_slug="casa-tres-patios",
            fecha_inicio=_next_week.replace(hour=14, minute=0, second=0).isoformat(),
            fecha_fin=_next_week.replace(hour=18, minute=0, second=0).isoformat(),
            es_recurrente=False,
            categorias=["arte_contemporaneo"], categoria_principal="arte_contemporaneo",
            municipio="medellin", barrio="El Poblado", nombre_lugar="Casa Tres Patios",
            descripcion="Jornada de estudio abierto donde los artistas en residencia muestran sus procesos creativos al público. Diálogos y recorridos.",
            es_gratuito=True, fuente="sitio_web", fuente_url="https://casatrespatios.org", verificado=True,
        ),
    ]

    for ev in EVENTOS:
        espacio_slug = ev.pop("espacio_slug")
        ev["espacio_id"] = espacio_map.get(espacio_slug)

        existing = supabase.table("eventos").select("id").eq("slug", ev["slug"]).execute()
        if existing.data:
            continue
        supabase.table("eventos").insert(ev).execute()
    print(f"✅ {len(EVENTOS)} eventos insertados")

    print("\n🎉 Seed completado — base de datos lista para producción")


if __name__ == "__main__":
    seed()
