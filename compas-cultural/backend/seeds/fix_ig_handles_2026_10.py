"""
Corrige instagram_handle inexistentes o equivocados en `lugares` (auditoría oct-2026).

Cada handle viejo no aparecía en ningún índice web; el nuevo es la cuenta oficial
del mismo lugar, encontrada buscando por su nombre. Solo se incluyen coincidencias
claras; los dudosos se dejan intactos.

Uso:
    cd backend
    python seeds/fix_ig_handles_2026_10.py            # dry-run
    python seeds/fix_ig_handles_2026_10.py --apply
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import supabase

HANDLE_FIXES = {
    "4elementosskuela": "4eskuela",
    "agroarte_colombia": "agroartecolombia",
    "altavozfest": "festivalaltavozmed",
    "babordemedellin": "bppiloto",
    "bpp_medellin": "bppiloto",
    "bibliotecapiloto": "bppiloto",
    "barnabyjonesbar_": "barnaby_jonesbar",
    "biblioteca_itagui": "bibliotecadiegoechavarria",
    "bellocultural": "culturadebello",
    "culturabello": "culturadebello",
    "blue_medellin": "bluemedellin",
    "cafe.vallejo": "cafevallejo",
    "caldascultural": "caldascultura",
    "cultura.caldas": "caldascultura",
    "cafe_cliche": "cafeclichebistro",
    "casaculturaloscolores": "cdccolores",
    "casaculturaavila": "cdcavila",
    "casaculturamanrique": "casadeculturamanrique",
    "casa_otraparte": "otraparte",
    "otraparte_medellin": "otraparte",
    "otraparte_of": "otraparte",
    "casateatroelpoblado": "casateatroep",
    "casaculturapoblado": "cdcelpoblado",
    "casadelalunamed": "casadelalunamedellin",
    "casadelteatromed": "casadelteatro",
    "casadelacultura_envigado": "secretariadeculturadeenvigado",
    "culturenvigado": "secretariadeculturadeenvigado",
    "corporacionregion": "corpregion",
    "culturasabaneta": "cultura_barquerena",
    "corporacionculturalnuestragente": "nuestragente",
    "nuestragente_medellin": "nuestragente",
    "cumbiaunderground": "cumbiaunder",
    "culturaantioquia": "palacio_de_la_cultura",
    "disonanciagraficacolectiva": "la_disonancia",
    "elateneomedellin": "ateneomedellin",
    "el_mamm": "elmamm",
    "mamm.medellin": "elmamm",
    "mamabordemedellin": "elmamm",
    "elmontacargas": "el_montacargas",
    "elnidocc": "elnidocultural",
    "eleslabon_prendido": "eleslabonprendido",
    "exlibris_cafeb": "cafexlibris",
    "esquinatomada": "ulisescafelibreria",
    "eticketablanca": "_eticketablanca_",
    "faunobarcultural": "faunocafecultural",
    "ferialibromde": "fiestalibro",
    "fiabordecultura": "fiestalibro",
    "fiestadellibro": "fiestalibro",
    "festivalpoesiamed": "festivalpoesiamedellin",
    "festivaldetangomedellin": "festivaltangomedellin",
    "filosofiaudea": "filosofia_udea",
    "filarmed_oficial": "filarmed",
    "hiphopkolacho": "casakolacho",
    "hora25teatro": "teatrolahora25",
    "hiphopmed": "casahiphopmed",
    "lacavernadebaco_bar": "cavernadebaco",
    "lapolillateatro": "lapolillamed",
    "metalsinfronterasmde": "metalsinfronteras",
    "miradasmedellin": "miradas.medellin",
    "oficinacentralsuenos": "teatro.oficinacentral",
    "palinurolibreriacafe": "libreriapalinuro",
    "parabordeexplora": "parqueexplora",
    "pequenoteatro_med": "pequeno_teatrom",
    "teatroelpequeno": "pequeno_teatrom",
    "platohedro_mde": "platohedro",
    "redhiphopco": "redhiphopcolombia",
    "redbibliotecasmedellin": "bibliotecasmed",
    "silabaeditoresmde": "silaba.editores",
    "silabaeditores": "silaba.editores",
    "sankofadanzaafro": "sankofadanzafro",
    "semillasonora": "semilla.sonora_",
    "sonbata": "sonbatac13",
    "teatropopularmed": "teatrotpm",
    "teatroteococ": "teatrotecoc",
    "teatrolamosca": "la.mosca.teatro",
    "zirumateatro": "corporacionziruma",
    "tejidomujeresartistas": "remart_medellin",
    "rionegrocultureviva": "redculrionegrovivo",
    "pubrockmedellin": "pubrock.medellin",
    "teatrovictoria": "teatrovictoria.mde",
}


def _norm(raw):
    return (raw or "").strip().lstrip("@").split("?")[0].strip("/").lower()


def fix_handles(apply: bool, verbose: bool = True) -> dict:
    """Idempotente: solo toca filas cuyo handle sigue siendo uno de los viejos."""
    rows = []
    offset = 0
    while True:
        page = (
            supabase.table("lugares").select("id,nombre,instagram_handle")
            .not_.is_("instagram_handle", "null")
            .range(offset, offset + 999).execute().data or []
        )
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000

    cambios = [(r, HANDLE_FIXES[_norm(r["instagram_handle"])]) for r in rows
               if _norm(r["instagram_handle"]) in HANDLE_FIXES]
    if verbose:
        for r, new in cambios:
            print(f"  {r['nombre'][:45]:<45} @{_norm(r['instagram_handle'])} → @{new}")
        print(f"{len(cambios)} handles a corregir.")
    if apply:
        for r, new in cambios:
            supabase.table("lugares").update({"instagram_handle": new}).eq("id", r["id"]).execute()
        if cambios:
            print(f"✓ IG handles corregidos: {len(cambios)}")
    return {"corregidos": len(cambios) if apply else 0, "pendientes": len(cambios)}


if __name__ == "__main__":
    fix_handles(apply="--apply" in sys.argv)
