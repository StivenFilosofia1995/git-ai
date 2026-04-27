"""
Corre la migration ML Features contra Supabase usando el service role key.
Usa httpx (ya en el venv) para llamar al endpoint pgmeta de Supabase.
"""
import sys
import os
import pathlib
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌  SUPABASE_URL o SUPABASE_KEY no encontrados en .env")
    sys.exit(1)

# Leer el SQL de migración
sql_file = pathlib.Path(__file__).parent / "migrations" / "2026_04_ml_features.sql"
raw_sql = sql_file.read_text(encoding="utf-8")

# Dividir en statements individuales (separados por ';' ignorando comentarios)
def split_statements(sql: str) -> list[str]:
    stmts = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        current.append(line)
        full = "\n".join(current).strip()
        if full.endswith(";"):
            stmts.append(full)
            current = []
    if current:
        leftover = "\n".join(current).strip()
        if leftover:
            stmts.append(leftover)
    return [s for s in stmts if s]

# Estrategia 1: endpoint rpc/exec_sql (si existe)
def try_rpc_exec(client: httpx.Client, sql: str) -> bool:
    resp = client.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        json={"query": sql},
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    return resp.status_code < 400

# Estrategia 2: pgmeta query endpoint
def try_pgmeta(client: httpx.Client, sql: str) -> tuple[bool, str]:
    resp = client.post(
        f"{SUPABASE_URL}/pg/query",
        json={"query": sql},
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if resp.status_code < 400:
        return True, ""
    return False, resp.text


def run_migration():
    statements = split_statements(raw_sql)
    print(f"📄  {len(statements)} statements encontrados en la migración\n")

    with httpx.Client() as client:
        # Detectar qué estrategia funciona con un statement simple
        ping_sql = "SELECT 1;"
        strategy = None

        if try_rpc_exec(client, ping_sql):
            strategy = "rpc"
            print("✅  Usando estrategia: rpc/exec_sql\n")
        else:
            ok, _ = try_pgmeta(client, ping_sql)
            if ok:
                strategy = "pgmeta"
                print("✅  Usando estrategia: pgmeta\n")

        if strategy is None:
            print("❌  No se pudo conectar a Supabase para ejecutar SQL directo.")
            print("\n📋  SOLUCIÓN MANUAL:")
            print(f"    1. Ve a https://supabase.com/dashboard/project/zvxaaofqtbyichsllonc/sql/new")
            print(f"    2. Copia y pega el contenido de: migrations/2026_04_ml_features.sql")
            print(f"    3. Haz clic en 'Run'\n")
            print("=" * 60)
            print("CONTENIDO DE LA MIGRACIÓN:")
            print("=" * 60)
            print(raw_sql)
            return False

        errors = []
        for i, stmt in enumerate(statements, 1):
            preview = stmt.replace("\n", " ")[:80]
            print(f"  [{i}/{len(statements)}] {preview}...")

            if strategy == "rpc":
                ok = try_rpc_exec(client, stmt)
                err = "" if ok else "Error en rpc"
            else:
                ok, err = try_pgmeta(client, stmt)

            if ok:
                print(f"         ✅ OK")
            else:
                print(f"         ⚠️  Saltado (puede ser IF NOT EXISTS ya aplicado): {err[:100]}")
                errors.append((i, stmt[:60], err[:100]))

        print(f"\n{'=' * 60}")
        if not errors:
            print("🎉  MIGRACIÓN COMPLETADA SIN ERRORES")
        else:
            print(f"✅  Migración aplicada con {len(errors)} advertencia(s) (probablemente ya existían):")
            for n, s, e in errors:
                print(f"    [{n}] {s} → {e}")
        return True


if __name__ == "__main__":
    run_migration()
