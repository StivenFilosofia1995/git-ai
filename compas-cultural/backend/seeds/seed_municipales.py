"""
Seed: Agrega fuentes culturales municipales al DB.
Secretarías de Cultura, Alcaldías, y otras fuentes de agenda cultural
para que el auto-scraper las recorra y extraiga eventos.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import supabase

FUENTES_MUNICIPALES = [
    # ── Bello ────────────────────────────────────────────
    {
        "nombre": "Secretaría de Cultura de Bello",
        "slug": "secretaria-cultura-bello",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "danza", "teatro", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "bello",
        "barrio": "Centro",
        "direccion": "Cra 50 No. 51 00 - Edificio Gaspar de Rodas, Bello",
        "descripcion_corta": "Secretaría de Cultura y agenda cultural del municipio de Bello.",
        "descripcion": "La Secretaría de Cultura de Bello gestiona la programación cultural, festivales, talleres y eventos artísticos del segundo municipio más poblado del Valle de Aburrá.",
        "instagram_handle": "alcaldiadebello",
        "sitio_web": "https://www.bello.gov.co/tema/noticias",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.3383,
        "lng": -75.5556,
    },
    {
        "nombre": "Casa de la Cultura de Bello",
        "slug": "casa-cultura-bello",
        "tipo": "espacio_fisico",
        "categorias": ["casa_cultura", "teatro", "danza", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "bello",
        "barrio": "Centro",
        "direccion": "Cra 50 No. 50-38, Bello",
        "descripcion_corta": "Principal espacio cultural y artístico del municipio de Bello.",
        "descripcion": "La Casa de la Cultura de Bello es el epicentro de la vida cultural del municipio, albergando talleres de formación artística, presentaciones teatrales, exposiciones y eventos culturales comunitarios.",
        "instagram_handle": "casadelaculturabello",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.3378,
        "lng": -75.5553,
    },
    # ── Envigado ─────────────────────────────────────────
    {
        "nombre": "Secretaría de Cultura de Envigado",
        "slug": "secretaria-cultura-envigado",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "danza", "teatro", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "envigado",
        "barrio": "Centro",
        "direccion": "Carrera 43 Nº 38 Sur 35, Envigado",
        "descripcion_corta": "Secretaría de Cultura y agenda cultural del municipio de Envigado.",
        "descripcion": "La Secretaría de Cultura de Envigado impulsa el talento cultural local con convocatorias, programación artística, festivales y circulación nacional e internacional de artistas envigadeños.",
        "instagram_handle": "alcaldiadeenvigado",
        "sitio_web": "https://www.envigado.gov.co/tema/noticias",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1710,
        "lng": -75.5830,
    },
    {
        "nombre": "Casa de la Cultura Miguel Uribe Restrepo",
        "slug": "casa-cultura-envigado",
        "tipo": "espacio_fisico",
        "categorias": ["casa_cultura", "teatro", "galeria", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "envigado",
        "barrio": "Centro",
        "direccion": "Cra 43 #38 Sur-51, Envigado",
        "descripcion_corta": "Principal centro cultural de Envigado con programación artística permanente.",
        "descripcion": "La Casa de la Cultura Miguel Uribe Restrepo es el espacio cultural más importante de Envigado. Alberga salas de exposición, auditorio, sala de ensayos y talleres de formación artística.",
        "instagram_handle": "casaculturamur",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1705,
        "lng": -75.5835,
    },
    # ── Itagüí ──────────────────────────────────────────
    {
        "nombre": "Secretaría de Cultura de Itagüí",
        "slug": "secretaria-cultura-itagui",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "danza", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "itagui",
        "barrio": "Centro",
        "direccion": "CAMI Carrera 51 51-55, Itagüí",
        "descripcion_corta": "Secretaría de Cultura y agenda cultural del municipio de Itagüí.",
        "descripcion": "La Secretaría de Cultura de Itagüí gestiona festivales, eventos artísticos y programación cultural para el municipio, incluyendo el Festival de Música Andina Colombiana y la Feria del Libro de Itagüí.",
        "instagram_handle": "alcaldiadeitagui",
        "sitio_web": "https://www.itagui.gov.co/",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1849,
        "lng": -75.5994,
    },
    {
        "nombre": "Casa de la Cultura de Itagüí",
        "slug": "casa-cultura-itagui",
        "tipo": "espacio_fisico",
        "categorias": ["casa_cultura", "teatro", "danza", "galeria"],
        "categoria_principal": "casa_cultura",
        "municipio": "itagui",
        "barrio": "Centro",
        "direccion": "Cra 52 #51-45, Itagüí",
        "descripcion_corta": "Centro cultural principal de Itagüí con formación artística y eventos.",
        "descripcion": "La Casa de la Cultura de Itagüí es el corazón cultural del municipio, ofreciendo talleres de formación en artes visuales, música, danza y teatro, además de eventos y exposiciones regulares.",
        "instagram_handle": "casaculturaitagui",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1845,
        "lng": -75.5989,
    },
    # ── Sabaneta ─────────────────────────────────────────
    {
        "nombre": "Alcaldía de Sabaneta - Agenda Cultural",
        "slug": "alcaldia-sabaneta-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "sabaneta",
        "barrio": "Centro",
        "direccion": "Carrera 46 # 75 Sur 36, Sabaneta",
        "descripcion_corta": "Agenda de eventos y actividades culturales del municipio de Sabaneta.",
        "descripcion": "La Alcaldía de Sabaneta gestiona la agenda cultural del municipio, incluyendo las tradicionales Fiestas del Plátano, eventos comunitarios, festivales y actividades culturales durante todo el año.",
        "instagram_handle": "alcaldia_sabaneta",
        "sitio_web": "https://sabaneta.gov.co/eventos",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1517,
        "lng": -75.6167,
    },
    {
        "nombre": "Casa de la Cultura de Sabaneta",
        "slug": "casa-cultura-sabaneta",
        "tipo": "espacio_fisico",
        "categorias": ["casa_cultura", "teatro", "musica_en_vivo", "danza"],
        "categoria_principal": "casa_cultura",
        "municipio": "sabaneta",
        "barrio": "Centro",
        "direccion": "Calle 75 Sur #43-45, Sabaneta",
        "descripcion_corta": "Espacio cultural comunitario del municipio de Sabaneta.",
        "descripcion": "La Casa de la Cultura de Sabaneta ofrece formación artística, eventos culturales, talleres y actividades comunitarias para los habitantes del municipio.",
        "instagram_handle": "casaculturasabaneta",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1520,
        "lng": -75.6165,
    },
    # ── La Estrella ──────────────────────────────────────
    {
        "nombre": "Alcaldía de La Estrella - Cultura",
        "slug": "alcaldia-la-estrella-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "la_estrella",
        "barrio": "Centro",
        "direccion": "Calle 83 Sur #58-44, La Estrella",
        "descripcion_corta": "Agenda cultural del municipio de La Estrella.",
        "descripcion": "Programación cultural y eventos del municipio de La Estrella en el sur del Valle de Aburrá.",
        "instagram_handle": "alcaldiadelaestrella",
        "sitio_web": "https://www.laestrella.gov.co/",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.1570,
        "lng": -75.6300,
    },
    # ── Copacabana ───────────────────────────────────────
    {
        "nombre": "Alcaldía de Copacabana - Cultura",
        "slug": "alcaldia-copacabana-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "copacabana",
        "barrio": "Centro",
        "direccion": "Carrera 50 #50-15, Copacabana",
        "descripcion_corta": "Agenda cultural del municipio de Copacabana.",
        "descripcion": "Programación cultural y eventos del municipio de Copacabana en el norte del Valle de Aburrá.",
        "instagram_handle": "alcaldiadecopacabana",
        "sitio_web": "https://www.copacabana.gov.co/",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.3490,
        "lng": -75.5065,
    },
    # ── Caldas ───────────────────────────────────────────
    {
        "nombre": "Alcaldía de Caldas - Cultura",
        "slug": "alcaldia-caldas-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "caldas",
        "barrio": "Centro",
        "direccion": "Calle 129 Sur #51-20, Caldas",
        "descripcion_corta": "Agenda cultural del municipio de Caldas.",
        "descripcion": "Programación cultural y eventos del municipio de Caldas en el extremo sur del Valle de Aburrá.",
        "instagram_handle": "alcaldiadecaldas",
        "sitio_web": "https://www.caldas.gov.co/",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.0890,
        "lng": -75.6340,
    },
    # ── Girardota ────────────────────────────────────────
    {
        "nombre": "Alcaldía de Girardota - Cultura",
        "slug": "alcaldia-girardota-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "girardota",
        "barrio": "Centro",
        "direccion": "Carrera 15 #7-08, Girardota",
        "descripcion_corta": "Agenda cultural del municipio de Girardota.",
        "descripcion": "Programación cultural y eventos del municipio de Girardota en el norte del Valle de Aburrá.",
        "instagram_handle": "alcaldiadegirardota",
        "sitio_web": "https://www.girardota.gov.co/",
        "nivel_actividad": "activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.3755,
        "lng": -75.4540,
    },
    # ── Barbosa ──────────────────────────────────────────
    {
        "nombre": "Alcaldía de Barbosa - Cultura",
        "slug": "alcaldia-barbosa-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "musica_en_vivo"],
        "categoria_principal": "casa_cultura",
        "municipio": "barbosa",
        "barrio": "Centro",
        "direccion": "Calle 16 #15-32, Barbosa",
        "descripcion_corta": "Agenda cultural del municipio de Barbosa.",
        "descripcion": "Programación cultural y eventos del municipio de Barbosa, el municipio más al norte del Valle de Aburrá.",
        "instagram_handle": "alcaldiadebarbosa",
        "sitio_web": "https://www.barbosa.gov.co/",
        "nivel_actividad": "moderado",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.4390,
        "lng": -75.3318,
    },
    # ── Fuentes regionales / Comfama ─────────────────────
    {
        "nombre": "Comfama Cultura",
        "slug": "comfama-cultura",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "teatro", "musica_en_vivo", "festival", "cine", "danza"],
        "categoria_principal": "centro_cultural",
        "municipio": "medellin",
        "barrio": "Centro",
        "direccion": "Carrera 45 # 49A-16, Medellín",
        "descripcion_corta": "Comfama ofrece la mayor programación cultural del Valle de Aburrá.",
        "descripcion": "Comfama es la caja de compensación familiar más grande de Antioquia, con una oferta cultural que incluye teatro, cine, festivales, talleres, bibliotecas, y programación artística en múltiples sedes del Valle de Aburrá.",
        "instagram_handle": "comfamacultura",
        "sitio_web": "https://www.comfama.com/agenda/",
        "nivel_actividad": "muy_activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.2486,
        "lng": -75.5674,
    },
    {
        "nombre": "Secretaría de Cultura Ciudadana de Medellín",
        "slug": "secretaria-cultura-medellin",
        "tipo": "programa_institucional",
        "categorias": ["casa_cultura", "festival", "danza", "teatro", "musica_en_vivo", "galeria"],
        "categoria_principal": "casa_cultura",
        "municipio": "medellin",
        "barrio": "La Candelaria",
        "direccion": "Calle 41 #55-80 Piso 5, Medellín",
        "descripcion_corta": "Secretaría de Cultura Ciudadana de Medellín — agenda cultural oficial.",
        "descripcion": "La Secretaría de Cultura Ciudadana de Medellín gestiona la oferta cultural pública de la ciudad, incluyendo festivales, convocatorias, espacios culturales y programación artística en todas las comunas.",
        "instagram_handle": "culturamedell",
        "sitio_web": "https://medellincultura.gov.co/",
        "nivel_actividad": "muy_activo",
        "es_institucional": True,
        "fuente_datos": "seed_municipales",
        "lat": 6.2520,
        "lng": -75.5690,
    },
]


def main():
    print("🏛️  Sembrando fuentes culturales municipales...")
    insertados = 0
    duplicados = 0

    for fuente in FUENTES_MUNICIPALES:
        slug = fuente["slug"]
        existing = supabase.table("lugares").select("id,slug").eq("slug", slug).execute()
        if existing.data:
            print(f"  ⏭️  Ya existe: {fuente['nombre']}")
            duplicados += 1
            continue

        # Build row without lat/lng (they need to be in coordenadas format or separate columns)
        row = {k: v for k, v in fuente.items() if k not in ("lat", "lng")}
        # Add lat/lng as separate fields (matching the DB view/columns)
        if "lat" in fuente and "lng" in fuente:
            row["lat"] = fuente["lat"]
            row["lng"] = fuente["lng"]

        try:
            resp = supabase.table("lugares").insert(row).execute()
            if resp.data:
                print(f"  ✅ Insertado: {fuente['nombre']}")
                insertados += 1
            else:
                print(f"  ❌ Error insertando: {fuente['nombre']}")
        except Exception as e:
            # If lat/lng columns don't exist, try without them
            print(f"  ⚠️  Error con lat/lng, reintentando sin coordenadas: {e}")
            row.pop("lat", None)
            row.pop("lng", None)
            try:
                resp = supabase.table("lugares").insert(row).execute()
                if resp.data:
                    print(f"  ✅ Insertado (sin coords): {fuente['nombre']}")
                    insertados += 1
                else:
                    print(f"  ❌ Error: {fuente['nombre']}")
            except Exception as e2:
                print(f"  ❌ Error definitivo: {fuente['nombre']} — {e2}")

    print(f"\n✅ Completado: {insertados} insertados, {duplicados} ya existían")


if __name__ == "__main__":
    main()
