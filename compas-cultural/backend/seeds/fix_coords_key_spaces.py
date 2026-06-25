"""
Fix and add GPS coordinates for key cultural spaces in Medellín
that currently have null or incorrect coordinates in the 'lugares' table.

Coordinates verified against official addresses and OSM.
Run from: compas-cultural/backend/
    python seeds/fix_coords_key_spaces.py
"""
import sys
sys.path.insert(0, ".")
from app.database import supabase as sb

# ─── Verified GPS coordinates ───────────────────────────────────────────────
# Format: (name_fragment_to_match, lat, lng, note)
# Matches against nombre ILIKE '%fragment%'
COORDS_BY_SLUG = {
    # ── Biblioteca Pública Piloto ─────────────────────────────────────────
    "biblioteca-publica-piloto": (6.2448, -75.5976, "Cra 64 #50-32, Carlos E. Restrepo"),
    "biblioteca-publica-piloto-para-america-latina": (6.2448, -75.5976, "Sede Central BPP"),

    # ── Parques Biblioteca SBPM ──────────────────────────────────────────
    "parque-biblioteca-santo-domingo": (6.3024, -75.5577, "Cra 32 #106A-28, Santo Domingo Savio"),
    "parque-biblioteca-leon-de-greiff": (6.2605, -75.5519, "Cl 59A #36-30, La Ladera"),
    "parque-biblioteca-tomas-carrasquilla": (6.2723, -75.5975, "Cra 80 #82-60, Robledo"),
    "parque-biblioteca-san-javier": (6.2516, -75.6174, "Cl 42C #95-50, San Javier"),
    "parque-biblioteca-belen": (6.2185, -75.5949, "Cra 76 #18A-19, Belén"),
    "parque-biblioteca-manuel-mejia-vallejo": (6.1943, -75.5961, "Cra 65 #14-115, Guayabal"),
    "parque-biblioteca-fernando-botero": (6.2832, -75.6388, "Cl 62 #131-80, San Cristóbal"),
    "parque-biblioteca-gabriel-garcia-marquez": (6.2973, -75.5978, "Cra 80 #104-04, Doce de Octubre"),
    "parque-biblioteca-nuevo-occidente": (6.2703, -75.6355, "Cra 109A #63B-321, Lusitania"),
    "parque-biblioteca-jose-horacio-betancur": (6.1665, -75.6277, "Cl 50E Sur #75A-94, SAP"),

    # ── Bibliotecas de proximidad / corregimentales ──────────────────────
    "biblioteca-publica-el-limonar": (6.1585, -75.6286, "Cl 57 Sur #61-02, El Limonar SAP"),
    "biblioteca-publica-avila": (6.2368, -75.5540, "Cl 39 #38-21, El Salvador"),
    "biblioteca-publica-el-poblado": (6.2085, -75.5635, "Cl 3B Sur #29B-56, UVA Ilusión Verde"),
    "biblioteca-publica-fernando-gomez-martinez": (6.2803, -75.5967, "Cra 88C #76DD-20, Robledo Aures"),
    "biblioteca-publica-granizal": (6.3101, -75.5491, "Cra 36B #102C-54, Granizal"),
    "biblioteca-publica-popular": (6.3163, -75.5596, "Cra 43 #118-26, Popular No 2"),
    "biblioteca-publica-san-sebastian-de-palmitas": (6.3588, -75.6866, "Corregimiento Palmitas"),
    "biblioteca-publica-centro-occidental": (6.2450, -75.6200, "Cl 39D #112-81, El Salado"),
    "biblioteca-publica-la-floresta": (6.2500, -75.5970, "Cra 86 #46-55, La Floresta"),
    "biblioteca-publica-santa-cruz": (6.3030, -75.5570, "Cra 48 #98A-63, Santa Cruz"),
    "casa-de-la-literatura-san-german": (6.2611, -75.5940, "Cl 63 #75-86, San Germán"),
    "casa-de-la-lectura-infantil": (6.2425, -75.5630, "Cl 51 #45-57, Boston"),
    "centro-de-documentacion-musical": (6.2620, -75.5954, "Cl 65 #84-17, Robledo"),

    # ── UVAs ──────────────────────────────────────────────────────────────
    "uva-nuevo-amanecer": (6.2985, -75.5585, "Cl 107B #23A-138, La Avanzada"),
    "uva-de-la-esperanza": (6.3148, -75.5548, "Cl 96 #34-100, San Pablo"),
    "uva-de-los-suenos": (6.2763, -75.5552, "Cra 28 #69-04, Versalles"),
    "uva-la-libertad": (6.2468, -75.5552, "Cl 57 #17B-50, La Libertad"),
    "uva-de-la-alegria": (6.2753, -75.5610, "Cra 41 #79-66, Santa Inés"),
    "uva-de-la-armonia": (6.2885, -75.5568, "Cra 36 #84-98, Bello Oriente"),
    "uva-de-la-imaginacion": (6.2538, -75.5541, "Cra 40 #61-04, San Miguel"),
    "uva-mirador-de-san-cristobal": (6.2770, -75.6430, "Cra 131 #66-20, San Cristóbal"),
    "uva-los-guayacanes": (6.2628, -75.5962, "Cl 65C #94-04, Cucaracho"),
    "uva-el-encanto": (6.2960, -75.5980, "Cra 76 #104D-01, Santander"),
    "uva-de-la-cordialidad": (6.3010, -75.5582, "Cra 42B #110A-04, Santo Domingo Savio"),
    "uva-ilusión-verde": (6.2085, -75.5637, "Cl 3B Sur #29B-56, El Poblado"),
    "uva-sin-fronteras": (6.2870, -75.5953, "Cra 64 #97A-155, Tricentenario"),
    "uva-huellas-de-vida": (6.2516, -75.6168, "Cl 39C #113A-1, Las Independencias"),
    "uva-sol-de-oriente": (6.2468, -75.5552, "Cl 56F #18A-2, Sol de Oriente"),

    # ── Teatros oficiales ─────────────────────────────────────────────────
    "teatro-metropolitano": (6.2361, -75.5783, "Cl 41 #57-30, La Alpujarra"),
    "teatro-pablo-tobon": (6.2435, -75.5699, "Cra 40 #51-24, Boston"),
    "teatro-lido": (6.2523, -75.5636, "Cra 48 #54-20, Parque Bolívar"),
    "teatro-carlos-vieco": (6.2186, -75.5762, "Cerro Nutibara"),
    "teatro-ateneo": (6.2490, -75.5610, "Cl 47 #42-38, Bomboná"),
    "teatro-matacandelas": (6.2487, -75.5618, "Cl 47 #43-47, Bomboná"),
    "teatro-el-aguila-descalza": (6.2485, -75.5660, "Cra 45D #59-01, Prado"),
    "teatro-el-trueque": (6.2480, -75.5648, "Cra 49 #65-28, Prado"),
    "teatro-casa-del-teatro": (6.2529, -75.5668, "Cl 59 #50A-25, Prado Centro"),
    "teatro-pequeno": (6.2488, -75.5678, "Cra 42 #50A-12, La Candelaria"),
    "teatro-el-tesoro": (6.2113, -75.5690, "El Tesoro PC, El Poblado"),
    "teatro-comfama": (6.2499, -75.5638, "Cl 48 #43-87, San Ignacio"),
    "teatro-universidad-de-medellin": (6.2175, -75.5944, "Cra 87 #30-65, Belén"),
    "teatro-universitario-camilo-torres": (6.2658, -75.5656, "UdeA, Sevilla"),
    "paraninfo-universidad-de-antioquia": (6.2497, -75.5633, "Plazuela San Ignacio"),

    # ── Centros culturales EAFIT, Comfama ────────────────────────────────
    "comfama-aranjuez": (6.2767, -75.5607, "Cra 51B #91-95, Aranjuez"),
    "extension-cultural-eafit": (6.2095, -75.5715, "Cra 49 #7 Sur-50, El Poblado"),
    "mamm": (6.2138, -75.5706, "Cra 44 #19A-100, Ciudad del Río"),
    "museo-de-antioquia": (6.2515, -75.5651, "Cra 52 #52-43, La Candelaria"),
    "itm-fraternidad": (6.2468, -75.5570, "Cl 54A #30-01, Sucre"),
}

# Also fix Piloto entries that have wrong coordinates (6.2625, -75.5794)
WRONG_PILOTO_COORDS = {"lat": 6.2625, "lng": -75.5794}
CORRECT_PILOTO = {"lat": 6.2448, "lng": -75.5976}


def update_by_slug(slug_fragment: str, lat: float, lng: float, note: str) -> int:
    """Update all lugares matching slug fragment. Returns count updated."""
    # First find matching IDs
    r = sb.table("lugares").select("id,nombre,lat,lng,slug").ilike("slug", f"%{slug_fragment}%").execute()
    rows = r.data or []
    if not rows:
        return 0
    updated = 0
    for row in rows:
        # Only update if coords are null or wrong
        if row.get("lat") is not None and row.get("lng") is not None:
            # Skip if already has different (potentially correct) coords
            if abs(row["lat"] - lat) < 0.001 and abs(row["lng"] - lng) < 0.001:
                continue  # Already correct
        sb.table("lugares").update({"lat": lat, "lng": lng}).eq("id", row["id"]).execute()
        print(f"  ✓ Updated: {row['nombre']} → lat={lat}, lng={lng}  ({note})")
        updated += 1
    return updated


def fix_wrong_piloto_coords() -> int:
    """Fix Piloto entries with the wrong coordinates (6.2625, -75.5794)."""
    r = sb.table("lugares").select("id,nombre,lat,lng").ilike("nombre", "%piloto%").execute()
    rows = r.data or []
    updated = 0
    for row in rows:
        if (row.get("lat") and abs(row["lat"] - WRONG_PILOTO_COORDS["lat"]) < 0.001
                and row.get("lng") and abs(row["lng"] - WRONG_PILOTO_COORDS["lng"]) < 0.001):
            sb.table("lugares").update(CORRECT_PILOTO).eq("id", row["id"]).execute()
            print(f"  ✓ Fixed wrong Piloto coords: {row['nombre']} → {CORRECT_PILOTO}")
            updated += 1
    return updated


def main():
    print("=== Fixing coordinates for key cultural spaces ===\n")

    total = 0

    # Fix wrong Piloto coordinates first
    print("── Fixing wrong Piloto coordinates ──")
    total += fix_wrong_piloto_coords()

    # Update all mapped spaces
    print("\n── Updating spaces by slug ──")
    for slug_fragment, (lat, lng, note) in COORDS_BY_SLUG.items():
        n = update_by_slug(slug_fragment, lat, lng, note)
        total += n

    print(f"\n✅ Total records updated: {total}")


if __name__ == "__main__":
    main()
