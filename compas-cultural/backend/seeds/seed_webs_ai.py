"""
seed_webs_ai.py — Usa Groq para inferir sitios web de colectivos/espacios sin sitio_web.

Proceso:
1. Toma lotes de 20 lugares (nombre + instagram_handle)
2. Pregunta a Groq: ¿cuál es el sitio web oficial de cada uno?
3. Valida cada URL (HTTP check)
4. Actualiza sitio_web en Supabase

Uso:
    cd backend
    python seeds/seed_webs_ai.py
    python seeds/seed_webs_ai.py --dry-run
    python seeds/seed_webs_ai.py --batch 50    (cuántos lugares procesar)
"""
import sys, os, re, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import json
import httpx
from app.database import supabase
from app.services.groq_client import groq_chat, MODEL_FAST

BATCH_SIZE = 20  # places per Groq call

SYSTEM_PROMPT = """Eres un experto en cultura urbana de Medellín, Colombia.
Conoces los sitios web oficiales de los espacios culturales, colectivos, festivales y artistas de la ciudad.

Para cada lugar que te dé, responde con su sitio web oficial si lo conoces con CERTEZA.
- Solo incluye URLs que sabes con certeza que existen.
- No inventes URLs. Si no estás seguro, pon null.
- Responde SOLO con JSON válido."""

def infer_websites_with_ai(lugares: list[dict]) -> dict[str, str]:
    """
    Ask Groq for the official website of each lugar.
    Returns {lugar_id: url} for places where a website was found.
    """
    items = []
    for l in lugares:
        items.append({
            "id": l["id"],
            "nombre": l["nombre"],
            "instagram": l.get("instagram_handle", ""),
            "tipo": l.get("tipo", ""),
        })

    prompt = f"""Dado el siguiente listado de espacios/colectivos culturales de Medellín, Colombia,
dime cuál es el sitio web oficial de cada uno. Solo incluye los que conoces con certeza.

Listado:
{json.dumps(items, ensure_ascii=False, indent=2)}

Responde con este JSON exacto:
{{
  "resultados": [
    {{"id": "uuid-del-lugar", "sitio_web": "https://..." o null}},
    ...
  ]
}}

Solo pon sitio_web si estás completamente seguro de que esa URL existe y es el sitio oficial."""

    full_prompt = SYSTEM_PROMPT + "\n\n" + prompt
    try:
        raw = groq_chat(full_prompt, model=MODEL_FAST, max_tokens=2000, temperature=0)
        if not raw:
            return {}
        # Extract JSON
        if "```" in raw:
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw.strip())
        data = json.loads(raw)
        results = {}
        for item in data.get("resultados", []):
            lid = item.get("id")
            web = item.get("sitio_web")
            if lid and web and web not in ("null", "None", ""):
                results[lid] = web
        return results
    except Exception as e:
        print(f"  ⚠ Groq error: {e}")
        return {}


def validate_url(url: str) -> bool:
    """Quick HTTP HEAD check that the URL actually responds."""
    try:
        with httpx.Client(follow_redirects=True, timeout=10) as c:
            resp = c.head(url, headers={"User-Agent": "Mozilla/5.0"})
            return resp.status_code < 400
    except Exception:
        # Try GET as fallback
        try:
            with httpx.Client(follow_redirects=True, timeout=10) as c:
                resp = c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                return resp.status_code < 400
        except Exception:
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=200,
                        help="Total de lugares a procesar (default: 200)")
    parser.add_argument("--tipo", type=str, default="",
                        help="Filtrar por tipo")
    parser.add_argument("--skip-validate", action="store_true",
                        help="Saltar validación HTTP (más rápido)")
    args = parser.parse_args()

    print("🔍 Consultando lugares con Instagram pero sin sitio_web...")
    query = (
        supabase.table("lugares")
        .select("id,nombre,tipo,instagram_handle")
        .not_.is_("instagram_handle", "null")
        .is_("sitio_web", "null")
    )
    if args.tipo:
        query = query.eq("tipo", args.tipo)
    result = query.execute()
    lugares = result.data or []
    lugares = lugares[: args.batch]
    print(f"   → {len(lugares)} lugares a procesar en lotes de {BATCH_SIZE}\n")

    all_found = {}  # {id: url}

    # Process in batches
    for i in range(0, len(lugares), BATCH_SIZE):
        batch = lugares[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(lugares) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"🤖 Lote {batch_num}/{total_batches} ({len(batch)} lugares)...")

        found = infer_websites_with_ai(batch)
        print(f"   Groq encontró {len(found)} websites en este lote")
        all_found.update(found)
        time.sleep(1)  # rate limit

    print(f"\n📋 Total inferidos por Groq: {len(all_found)}")

    # Validate and save
    saved = 0
    invalid = 0

    # Build a lookup dict for names
    lugares_by_id = {l["id"]: l for l in lugares}

    for lid, url in all_found.items():
        nombre = lugares_by_id.get(lid, {}).get("nombre", lid)
        handle = lugares_by_id.get(lid, {}).get("instagram_handle", "")

        if not args.skip_validate:
            ok = validate_url(url)
            if not ok:
                print(f"  ❌ INVÁLIDA: {url}  ({nombre})")
                invalid += 1
                continue

        print(f"  ✅ @{handle:<28s} → {url}")
        saved += 1

        if not args.dry_run:
            try:
                supabase.table("lugares").update({"sitio_web": url}).eq("id", lid).execute()
            except Exception as e:
                print(f"     ❌ Error al guardar: {e}")
                saved -= 1

    print(f"\n{'='*60}")
    print(f"✅ Guardados:  {saved}")
    print(f"❌ Inválidos:  {invalid}")
    print(f"❓ No encontrados: {len(lugares) - len(all_found)}")
    if args.dry_run:
        print("⚠️  DRY-RUN: nada fue escrito en BD")


if __name__ == "__main__":
    main()
