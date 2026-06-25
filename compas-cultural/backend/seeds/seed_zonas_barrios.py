"""
Seed: Agregar zonas/barrios faltantes de Medellín y el Valle de Aburrá.
Ejecutar: python -m seeds.seed_zonas_barrios
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from supabase import create_client
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

NUEVAS_ZONAS = [
    # ── Medellín: barrios y comunas ──
    dict(
        nombre="Belén",
        slug="belen",
        descripcion="Barrio tradicional con Casa de la Cultura de Belén, murales comunitarios, festivales barriales y una escena de grafiti en crecimiento. Vida cultural de barrio auténtico.",
        vocacion="Cultura comunitaria y festivales barriales",
        municipio="medellin",
    ),
    dict(
        nombre="Robledo",
        slug="robledo",
        descripcion="Sede de la Universidad Nacional, con escena universitaria vibrante, grafiti, colectivos estudiantiles y espacios de debate cultural y político.",
        vocacion="Cultura universitaria y arte urbano",
        municipio="medellin",
    ),
    dict(
        nombre="Aranjuez",
        slug="aranjuez",
        descripcion="Barrio histórico con el Cementerio Museo de San Pedro, la Casa Gardeliana y una fuerte tradición tanguera. Arquitectura patrimonial y memoria cultural.",
        vocacion="Tango, patrimonio y memoria",
        municipio="medellin",
    ),
    dict(
        nombre="Buenos Aires",
        slug="buenos-aires",
        descripcion="Comuna con Casa de la Cultura, teatro comunitario, colectivos de base y procesos de memoria histórica. Mirador con vista panorámica de la ciudad.",
        vocacion="Teatro comunitario y memoria",
        municipio="medellin",
    ),
    dict(
        nombre="Castilla",
        slug="castilla",
        descripcion="Epicentro del hip-hop y breakdance en Medellín. Semilleros de rap, batallas de freestyle y cultura de barrio con fuerte identidad juvenil.",
        vocacion="Hip-hop, breakdance y cultura juvenil",
        municipio="medellin",
    ),
    dict(
        nombre="Manrique",
        slug="manrique",
        descripcion="Comuna con murales comunitarios, colectivos de base, procesos de transformación social a través del arte y bibliotecas populares.",
        vocacion="Muralismo y colectivos comunitarios",
        municipio="medellin",
    ),
    dict(
        nombre="Santo Domingo - Popular",
        slug="santo-domingo-popular",
        descripcion="Parque Biblioteca España, estación del Metrocable y arte comunitario. Símbolo de transformación urbana con miradores, grafiti y proyectos culturales de base.",
        vocacion="Arte comunitario y transformación urbana",
        municipio="medellin",
    ),
    dict(
        nombre="Santa Elena",
        slug="santa-elena",
        descripcion="Corregimiento sede del Festival de las Flores y la tradición silletera. Veredas con cultura campesina, artesanías y senderismo cultural.",
        vocacion="Tradición silletera y cultura campesina",
        municipio="medellin",
    ),
    dict(
        nombre="San Antonio de Prado",
        slug="san-antonio-de-prado",
        descripcion="Corregimiento con escena cultural propia, festivales locales, grupos de teatro y música comunitaria. Pueblo dentro de la metrópoli.",
        vocacion="Festivales locales y cultura comunitaria",
        municipio="medellin",
    ),
    dict(
        nombre="San Cristóbal",
        slug="san-cristobal",
        descripcion="Corregimiento con tradiciones campesinas, Festival de la Cometa, artesanías y procesos culturales rurales conectados a la ciudad.",
        vocacion="Tradiciones rurales y festivales",
        municipio="medellin",
    ),
    dict(
        nombre="El Doce de Octubre",
        slug="doce-de-octubre",
        descripcion="Barrio popular con Parque Biblioteca, colectivos juveniles, hip-hop y procesos de arte comunitario. Cultura de resistencia y creatividad.",
        vocacion="Hip-hop y arte comunitario",
        municipio="medellin",
    ),

    # ── Valle de Aburrá: municipios ──
    dict(
        nombre="Sabaneta Centro",
        slug="sabaneta-centro",
        descripcion="Municipio más pequeño de Colombia con intensa vida nocturna y cultural. Bares, restaurantes, música en vivo y el Parque Sabaneta como epicentro.",
        vocacion="Vida nocturna y música en vivo",
        municipio="sabaneta",
    ),
    dict(
        nombre="Itagüí - Ditaires",
        slug="itagui-ditaires",
        descripcion="Casa de la Cultura de Itagüí, festival de arte urbano y una escena emergente de colectivos culturales. Grafiti y muralismo en crecimiento.",
        vocacion="Arte urbano y muralismo",
        municipio="itagui",
    ),
    dict(
        nombre="Bello Centro",
        slug="bello-centro",
        descripcion="Ciudad Marco Fidel Suárez con teatro municipal, Casa de la Cultura, escuelas de música y una escena de teatro y danza en crecimiento.",
        vocacion="Teatro, música y danza",
        municipio="bello",
    ),
    dict(
        nombre="Copacabana",
        slug="copacabana",
        descripcion="Municipio con tradiciones religiosas, artesanías, festivales patronales y una escena cultural comunitaria conectada al norte del Valle de Aburrá.",
        vocacion="Tradiciones y cultura comunitaria",
        municipio="copacabana",
    ),
    dict(
        nombre="La Estrella",
        slug="la-estrella",
        descripcion="Municipio con Parque de la Romera, tradición cafetera, festivales locales y una escena cultural en desarrollo con colectivos juveniles.",
        vocacion="Naturaleza y cultura cafetera",
        municipio="la_estrella",
    ),
    dict(
        nombre="Caldas",
        slug="caldas",
        descripcion="Puerta sur del Valle de Aburrá. Tradición alfarera, Festival del Barro, artesanías y cultura campesina con raíces profundas.",
        vocacion="Alfarería y tradiciones campesinas",
        municipio="caldas",
    ),
    dict(
        nombre="Girardota",
        slug="girardota",
        descripcion="Municipio con fuerte tradición religiosa, Señor Caído de Girardota, festivales patronales y una escena artesanal en crecimiento.",
        vocacion="Tradición religiosa y artesanías",
        municipio="girardota",
    ),
    dict(
        nombre="Barbosa",
        slug="barbosa",
        descripcion="Extremo norte del Valle de Aburrá. Cultura campesina, panela y tradiciones agrícolas. Festivales locales y artesanías rurales.",
        vocacion="Cultura campesina y agrícola",
        municipio="barbosa",
    ),
]


def seed():
    inserted = 0
    skipped = 0
    for z in NUEVAS_ZONAS:
        existing = supabase.table("zonas_culturales").select("id").eq("slug", z["slug"]).execute()
        if existing.data:
            print(f"  ⏭  Ya existe: {z['nombre']}")
            skipped += 1
            continue
        supabase.table("zonas_culturales").insert(z).execute()
        print(f"  ✅ Insertada: {z['nombre']}")
        inserted += 1
    print(f"\n🎯 Total: {inserted} zonas nuevas insertadas, {skipped} ya existían")


if __name__ == "__main__":
    seed()
