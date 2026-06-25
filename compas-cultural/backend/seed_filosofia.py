"""Seed filosofía/alternative culture colectivos into the database."""
from app.database import supabase

filosofia_colectivos = [
    {
        "nombre": "Filosofía en el Parque - Medellín",
        "slug": "filosofia-en-el-parque-medellin",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "poesia", "editorial"],
        "descripcion": "Colectivo de filosofía callejera. Llevamos la filosofía a los parques y plazas públicas de Medellín. Diálogos abiertos, lecturas filosóficas y debates libres.",
        "descripcion_corta": "Filosofía callejera en los parques de Medellín",
        "municipio": "medellin",
        "barrio": "Centro",
        "instagram_handle": "filosofiaenelparque",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Café Filosófico Medellín",
        "slug": "cafe-filosofico-medellin",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "editorial", "poesia"],
        "descripcion": "Espacio de encuentro filosófico en cafés de Medellín. Reuniones semanales para discutir pensamiento crítico, existencialismo y filosofía contemporánea.",
        "descripcion_corta": "Tertulias filosóficas semanales en cafés de Medellín",
        "municipio": "medellin",
        "barrio": "Laureles",
        "instagram_handle": "cafefilosoficomedellin",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Pensamiento Libre Valle de Aburrá",
        "slug": "pensamiento-libre-valle-aburra",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "poesia", "casa_cultura"],
        "descripcion": "Colectivo de pensamiento crítico y filosofía alternativa. Talleres de filosofía para jóvenes, clubes de lectura filosófica y charlas abiertas.",
        "descripcion_corta": "Pensamiento crítico y filosofía alternativa para el Valle de Aburrá",
        "municipio": "medellin",
        "barrio": "Belén",
        "instagram_handle": "pensamientolibrevalleaburra",
        "nivel_actividad": "moderado",
    },
    {
        "nombre": "La Tertulia Filosófica",
        "slug": "la-tertulia-filosofica",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "editorial", "libreria"],
        "descripcion": "Grupo de lectura y discusión filosófica. Exploramos a Nietzsche, Deleuze, los estoicos y el pensamiento decolonial. Reuniones quincenales.",
        "descripcion_corta": "Grupo de lectura y discusión filosófica quincenal",
        "municipio": "medellin",
        "barrio": "El Poblado",
        "instagram_handle": "latertuliafilosofica",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Filosofía Urbana Medellín",
        "slug": "filosofia-urbana-medellin",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "hip_hop", "poesia"],
        "descripcion": "Fusión de filosofía con cultura urbana. Filosofía del hip-hop, pensamiento underground y cátedras callejeras en comunas y barrios populares.",
        "descripcion_corta": "Filosofía underground desde la cultura urbana de Medellín",
        "municipio": "medellin",
        "barrio": "San Javier",
        "instagram_handle": "filosofiaurbanamedellin",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Escuela Nómada de Filosofía",
        "slug": "escuela-nomada-filosofia",
        "tipo": "colectivo",
        "categoria_principal": "filosofia",
        "categorias": ["filosofia", "casa_cultura", "editorial"],
        "descripcion": "Escuela itinerante de filosofía. Llevamos talleres filosóficos a bibliotecas, casas de cultura y espacios comunitarios del Valle de Aburrá.",
        "descripcion_corta": "Escuela itinerante de filosofía para el Valle de Aburrá",
        "municipio": "envigado",
        "barrio": "Centro",
        "instagram_handle": "escuelanomadafilosofia",
        "nivel_actividad": "moderado",
    },
]

for col in filosofia_colectivos:
    existing = supabase.table("lugares").select("id").eq("slug", col["slug"]).execute()
    if existing.data:
        print(f"  Skip: {col['nombre']}")
        continue
    supabase.table("lugares").insert(col).execute()
    print(f"  OK: {col['nombre']}")

print("\nDone!")
