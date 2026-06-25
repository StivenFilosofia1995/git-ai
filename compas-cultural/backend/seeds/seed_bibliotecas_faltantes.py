"""
Seed: Bibliotecas y espacios faltantes de la Red de Bibliotecas Públicas de Medellín.

Estas 17 sedes aparecen en el scraper de bibliotecasmedellin.gov.co pero no están
en la tabla `lugares`. Se insertan con upsert por slug.

Uso:
    python seeds/seed_bibliotecas_faltantes.py
    python seeds/seed_bibliotecas_faltantes.py --dry-run
"""
import sys, os, uuid, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

from app.database import supabase

LUGARES = [
    # ── Bibliotecas públicas de barrio ─────────────────────────────────────
    {
        "nombre": "Biblioteca Pública Altavista",
        "slug": "biblioteca-publica-altavista",
        "barrio": "Altavista",
        "comuna": "Corregimiento Altavista",
        "direccion": "Corregimiento Altavista, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Centro Occidental",
        "slug": "biblioteca-publica-centro-occidental",
        "barrio": "La América",
        "comuna": "La América",
        "direccion": "Barrio La América, Medellín",
    },
    {
        "nombre": "Biblioteca Pública El Limonar",
        "slug": "biblioteca-publica-el-limonar",
        "barrio": "El Limonar",
        "comuna": "Guayabal",
        "direccion": "Barrio El Limonar, Medellín",
    },
    {
        "nombre": "Biblioteca Pública El Poblado",
        "slug": "biblioteca-publica-el-poblado",
        "barrio": "El Poblado",
        "comuna": "El Poblado",
        "direccion": "Barrio El Poblado, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Fernando Gómez Martínez, Robledo",
        "slug": "biblioteca-publica-fernando-gomez-martinez-robledo",
        "barrio": "Robledo",
        "comuna": "Robledo",
        "direccion": "Barrio Robledo, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Granizal",
        "slug": "biblioteca-publica-granizal",
        "barrio": "Granizal",
        "comuna": "Popular",
        "direccion": "Barrio Granizal, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Popular n.° 2",
        "slug": "biblioteca-publica-popular-2",
        "barrio": "Popular",
        "comuna": "Popular",
        "direccion": "Barrio Popular, Medellín",
    },
    {
        "nombre": "Biblioteca Pública San Sebastián de Palmitas",
        "slug": "biblioteca-publica-san-sebastian-de-palmitas",
        "barrio": "San Sebastián de Palmitas",
        "comuna": "Corregimiento San Sebastián de Palmitas",
        "direccion": "Corregimiento San Sebastián de Palmitas, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Santa Cruz",
        "slug": "biblioteca-publica-santa-cruz",
        "barrio": "Santa Cruz",
        "comuna": "Santa Cruz",
        "direccion": "Barrio Santa Cruz, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Santa Elena",
        "slug": "biblioteca-publica-santa-elena",
        "barrio": "Santa Elena",
        "comuna": "Corregimiento Santa Elena",
        "direccion": "Corregimiento Santa Elena, Medellín",
    },
    {
        "nombre": "Biblioteca Pública Ávila, María Agudelo Mejía",
        "slug": "biblioteca-publica-avila-maria-agudelo-mejia",
        "barrio": "Ávila",
        "comuna": "Manrique",
        "direccion": "Barrio Ávila, Medellín",
    },
    # ── Documentación / programas ──────────────────────────────────────────
    {
        "nombre": "Centro de Documentación Buen Comienzo",
        "slug": "centro-documentacion-buen-comienzo",
        "barrio": "Centro",
        "comuna": "La Candelaria",
        "direccion": "Medellín",
        "tipo_override": "programa_institucional",
    },
    # ── Parque Biblioteca ──────────────────────────────────────────────────
    {
        "nombre": "Parque Biblioteca José Horacio Betancur, San Antonio de Prado",
        "slug": "parque-biblioteca-jose-horacio-betancur-san-antonio-de-prado",
        "barrio": "San Antonio de Prado",
        "comuna": "Corregimiento San Antonio de Prado",
        "direccion": "Corregimiento San Antonio de Prado, Medellín",
    },
    # ── Parque al Barrio / UVAs ────────────────────────────────────────────
    {
        "nombre": "UVA Nuevo Amanecer",
        "slug": "uva-nuevo-amanecer",
        "barrio": "Nuevo Amanecer",
        "comuna": "San Javier",
        "direccion": "Barrio Nuevo Amanecer, San Javier, Medellín",
        "categoria_override": "uva",
        "tipo_override": "espacio_fisico",
    },
    {
        "nombre": "Bibliometro Medellín",
        "slug": "bibliometro-medellin",
        "barrio": "Centro",
        "comuna": "La Candelaria",
        "direccion": "Estaciones Metro, Medellín",
        "tipo_override": "programa_institucional",
    },
    {
        "nombre": "Institución Maestro Guillermo Vélez Vélez",
        "slug": "institucion-guillermo-velez-velez",
        "barrio": "Manrique",
        "comuna": "Manrique",
        "direccion": "Medellín",
        "tipo_override": "espacio_fisico",
        "categoria_override": "casa_cultura",
    },
    {
        "nombre": "UVA de la Cordialidad",
        "slug": "uva-de-la-cordialidad",
        "barrio": "La Cordialidad",
        "comuna": "Manrique",
        "direccion": "Medellín",
        "categoria_override": "uva",
        "tipo_override": "espacio_fisico",
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("SEED: Bibliotecas faltantes de la Red de Bibliotecas MDE")
    print(f"Dry-run: {args.dry_run}")
    print("=" * 60)

    ok = 0
    errors = 0

    for spec in LUGARES:
        tipo = spec.pop("tipo_override", "espacio_fisico")
        categoria = spec.pop("categoria_override", "biblioteca")

        row = {
            "id": str(uuid.uuid4()),
            "nombre": spec["nombre"],
            "slug": spec["slug"],
            "tipo": tipo,
            "categoria_principal": categoria,
            "categorias": [categoria],
            "municipio": "medellin",
            "barrio": spec.get("barrio") or "",
            "comuna": spec.get("comuna") or "",
            "direccion": spec.get("direccion") or "",
            "es_institucional": True,
            "nivel_actividad": "activo",
            "fuente_datos": "bibliotecas_mde_seed",
            "descripcion_corta": f"Sede de la Red de Bibliotecas Públicas de Medellín.",
        }

        if args.dry_run:
            print(f"  DRY: {row['slug']} | {row['nombre'][:60]}")
            ok += 1
            continue

        try:
            supabase.table("lugares").upsert(row, on_conflict="slug").execute()
            print(f"  OK : {row['slug']}")
            ok += 1
        except Exception as e:
            print(f"  ERR: {row['slug']} → {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"RESUMEN: {ok} OK, {errors} errores")
    print("=" * 60)
    print()
    if not args.dry_run and ok > 0:
        print("Ahora vuelve a correr el scraper para mapear los eventos:")
        print("  python seeds/scrape_bibliotecas_mde.py --pages 5")


if __name__ == "__main__":
    main()
