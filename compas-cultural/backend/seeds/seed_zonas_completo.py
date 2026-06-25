"""
Seed completo de TODAS las zonas y barrios del Valle de Aburrá.
10 municipios con sus comunas/corregimientos y barrios principales.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from supabase import create_client
import re

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zvxaaofqtbyichsllonc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def slugify(text):
    text = text.lower().strip()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:250]


# Estructura: (nombre_zona, municipio, vocación, barrios_principales)
ZONAS = [
    # ══════════════════════════════════════════════
    # MEDELLÍN — 16 comunas + 5 corregimientos
    # ══════════════════════════════════════════════
    ("Popular (Comuna 1)", "medellin", "Hip-hop, arte comunitario, bibliotecas", "Santo Domingo Savio, Granizal, Popular, Moscú, Villa Guadalupe, San Pablo, Aldea Pablo VI, La Esperanza, Carpinelo"),
    ("Santa Cruz (Comuna 2)", "medellin", "Teatro comunitario, cultura barrial", "Santa Cruz, La Rosa, Moscú No. 2, Villa del Socorro, Villa Niza, Andalucía, La Francia, Pablo VI"),
    ("Manrique (Comuna 3)", "medellin", "Arte urbano, muralismo, cultura popular", "Manrique Central, La Salle, Las Granjas, Campo Valdés, El Raizal, El Pomar, Versalles"),
    ("Aranjuez (Comuna 4)", "medellin", "Hip-hop, batallas de freestyle, arte urbano", "Aranjuez, Berlín, San Isidro, Palermo, Bermejal, Moravia, Sevilla, San Pedro, Manrique Central No. 2, Campo Valdés No. 2, Las Esmeraldas, Miranda"),
    ("Castilla (Comuna 5)", "medellin", "Música, cultura barrial", "Castilla, Alfonso López, Francisco Antonio Zea, Belalcázar, Girardot, Tricentenario, Caribe, Toscana, Las Brisas, Boyacá"),
    ("Doce de Octubre (Comuna 6)", "medellin", "Rap, arte urbano, cultura juvenil", "Doce de Octubre, Santander, Pedregal, La Esperanza, San Martín de Porres, Kennedy, Picacho, Mirador del Doce, Progreso, El Triunfo"),
    ("Robledo (Comuna 7)", "medellin", "Universidad, arte, música", "Robledo, Aures, Bello Horizonte, Villa Flora, Palenque, San Germán, López de Mesa, El Diamante, Cucaracho, Facultad de Minas"),
    ("Villa Hermosa (Comuna 8)", "medellin", "Teatro, música, arte comunitario", "Villa Hermosa, La Mansión, San Antonio, Enciso, Sucre, El Pinal, Trece de Noviembre, La Libertad, Villa Tina, San Miguel, Batallón Girardot, Llanaditas"),
    ("Buenos Aires (Comuna 9)", "medellin", "Arte alternativo, centros culturales", "Buenos Aires, Miraflores, Cataluña, La Milagrosa, Loreto, Barrio de Jesús, Bombona, Los Cerros, Alejandro Echavarría, Juan Pablo II"),
    ("La Candelaria (Centro, Comuna 10)", "medellin", "Epicentro cultural: museos, teatros, galerías, patrimonio", "La Candelaria, Villanueva, San Benito, Guayaquil, Corazón de Jesús, Calle Nueva, Perpetuo Socorro, San Diego, Boston, Los Ángeles, Prado, Jesús Nazareno, Estación Villa, La Alpujarra, Colón"),
    ("Laureles-Estadio (Comuna 11)", "medellin", "Gastronomía, música en vivo, teatros", "Laureles, Estadio, Los Conquistadores, San Joaquín, Bolivariana, Velódromo, Florida Nueva, Naranjal, Suramericana, Carlos E. Restrepo, Cuarta Brigada"),
    ("La América (Comuna 12)", "medellin", "Bibliotecas, cultura vecinal", "La América, La Floresta, Santa Lucía, Simón Bolívar, Santa Mónica, Calasanz, Ferrini, Los Pinos, Cristóbal"),
    ("San Javier (Comuna 13)", "medellin", "Grafiti, hip-hop, turismo cultural, Comuna 13 como referente mundial", "San Javier, Veinte de Julio, El Socorro, La Independencia, Nuevos Conquistadores, El Salado, Eduardo Santos, Antonio Nariño, Las Independencias, La Quiebra, Metropolitano"),
    ("El Poblado (Comuna 14)", "medellin", "Galerías, cafés, coworking cultural, vida nocturna", "El Poblado, Manila, Astorga, Patio Bonito, La Aguacatala, El Diamante, El Castillo, Los Balsos, San Lucas, El Tesoro, Los Naranjos, La Visitación, Provenza, Lleras"),
    ("Guayabal (Comuna 15)", "medellin", "Industrial cultural, espacios emergentes", "Guayabal, Trinidad, Santa Fe, Cristo Rey, Campo Amor, Noel, La Colina"),
    ("Belén (Comuna 16)", "medellin", "Parques, cultura familiar, bibliotecas", "Belén, La Palma, Las Violetas, Rosales, Altavista, Fátima, La Nubia, Rodeo Alto, San Bernardo, Las Playas, Diego Echavarría, La Gloria, La Mota, El Rincón, Los Alpes, Granada, AltaVista"),
    ("San Sebastián de Palmitas (Corregimiento)", "medellin", "Ruralidad, ecoturismo, cultura campesina", "Palmitas Centro, La Volcana, La Aldea, La Suiza, Urquitá"),
    ("San Cristóbal (Corregimiento)", "medellin", "Cultura afro, hip-hop, música", "San Cristóbal, Pajarito, La Loma, El Llano, El Carmelo, Travesías"),
    ("Altavista (Corregimiento)", "medellin", "Arte comunitario, naturaleza", "Altavista Central, El Jardín, Aguas Frías, San José del Manzanillo"),
    ("San Antonio de Prado (Corregimiento)", "medellin", "Cultura vecinal, crecimiento urbano", "San Antonio de Prado Centro, El Limonar, La Florida, Pradito"),
    ("Santa Elena (Corregimiento)", "medellin", "Silleteros, cultura campesina, ecoturismo", "Santa Elena Centro, El Plan, Piedras Blancas, Media Luna, Mazo, El Cerro"),

    # ══════════════════════════════════════════════
    # BELLO
    # ══════════════════════════════════════════════
    ("Bello Centro", "bello", "Cultura municipal, eventos institucionales", "Centro, Niquía, París, Suárez, Zamora, Pérez, Espíritu Santo, Panamericano, La Madera, El Rosario"),
    ("Bello Norte", "bello", "Crecimiento urbano, cultura emergente", "Niquia, Ciudadela del Norte, Trapiche, Hato Viejo, La Camila, Tierra Adentro"),

    # ══════════════════════════════════════════════
    # ENVIGADO
    # ══════════════════════════════════════════════
    ("Envigado Centro", "envigado", "Otraparte, filosofía, café cultural", "Centro, Alcalá, La Paz, Obrero, La Magnolia, Mesa, Villagrande"),
    ("Envigado Sur", "envigado", "Zona residencial, cultura vecinal", "Zuñiga, El Dorado, El Portal, La Mina, El Esmeraldal, Loma del Escobero, San José, El Trianón"),

    # ══════════════════════════════════════════════
    # ITAGÜÍ
    # ══════════════════════════════════════════════
    ("Itagüí Centro", "itagui", "Casa de la Cultura, eventos municipales", "Centro, Santa María, San Pío, Bariloche, Asturias, La Independencia, Los Naranjos, Artex, San Fernando"),
    ("Itagüí Sur", "itagui", "Zona industrial, cultura emergente", "Ditaires, La Finca, Los Gómez, El Ajizal, Suramerica, Villa Paula, Suramérica"),

    # ══════════════════════════════════════════════
    # SABANETA
    # ══════════════════════════════════════════════
    ("Sabaneta", "sabaneta", "Municipio más pequeño de Colombia, gastronomía y cultura local", "Centro, Las Casitas, Calle Larga, Restrepo Naranjo, María Auxiliadora, San Rafael, Playas Placer, Entreamigos, Mayorca, Pan de Azúcar, La Doctora, Tres Esquinas"),

    # ══════════════════════════════════════════════
    # LA ESTRELLA
    # ══════════════════════════════════════════════
    ("La Estrella", "la_estrella", "Cultura municipal, eventos al aire libre", "Centro, Pueblo Viejo, La Tablacita, San Isidro, La Tablaza, Ancón Sur, La Ferrería, Sagrado Corazón, La Inmaculada"),

    # ══════════════════════════════════════════════
    # CALDAS
    # ══════════════════════════════════════════════
    ("Caldas", "caldas", "Puerta sur del Valle de Aburrá, tradición", "Centro, La Quiebra, La Raya, La Chuscala, La Corrala, Sinifaná, La Valeria, Primavera"),

    # ══════════════════════════════════════════════
    # COPACABANA
    # ══════════════════════════════════════════════
    ("Copacabana", "copacabana", "Cultura vecinal, tradición religiosa", "Centro, Machado, El Cabuyal, La Misericordia, Yarumito, San Juan, Fátima, La Pedrera"),

    # ══════════════════════════════════════════════
    # GIRARDOTA
    # ══════════════════════════════════════════════
    ("Girardota", "girardota", "Religiosidad popular, turismo cultural", "Centro, El Totumo, El Hatillo, San Andrés, Manga Arriba, San Diego, Juan XXIII, El Palmar"),

    # ══════════════════════════════════════════════
    # BARBOSA
    # ══════════════════════════════════════════════
    ("Barbosa", "barbosa", "Norte del Valle de Aburrá, ruralidad y tradición", "Centro, El Hatillo, Yarumito, Popalito, Nechí, Corrientes, La Playa"),
]


def seed():
    existentes = sb.table("zonas_culturales").select("slug").execute()
    slugs_existentes = {r["slug"] for r in existentes.data}

    nuevos = 0
    dup = 0

    for nombre, municipio, vocacion, barrios in ZONAS:
        sl = slugify(nombre)
        if sl in slugs_existentes:
            dup += 1
            continue

        row = {
            "nombre": nombre,
            "slug": sl,
            "municipio": municipio,
            "vocacion": vocacion,
            "descripcion": f"Barrios: {barrios}",
        }

        try:
            sb.table("zonas_culturales").insert(row).execute()
            nuevos += 1
            print(f"  ✓ {nombre} ({municipio})")
        except Exception as e:
            print(f"  ✗ {nombre}: {e}")

    print(f"\nSeed zonas completado: {nuevos} nuevas, {dup} ya existían")


if __name__ == "__main__":
    if not SUPABASE_KEY:
        print("Set SUPABASE_KEY")
        sys.exit(1)
    seed()
