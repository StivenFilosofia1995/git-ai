"""Verifica la API de produccion."""
import sys
import requests
sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://culturaeterea.up.railway.app"

# Health check
r0 = requests.get(f"{BASE}/health", timeout=10)
print(f"Health: {r0.status_code} | {r0.text[:60]}")

# Eventos de hoy
r1 = requests.get(f"{BASE}/api/v1/eventos", params={"fecha_inicio": "2026-04-30", "limit": 5}, timeout=15)
print(f"\nAPI /eventos hoy: {r1.status_code}")
if r1.status_code == 200:
    data = r1.json()
    if isinstance(data, list):
        print(f"Total retornados: {len(data)}")
        for e in data[:3]:
            print(f"  {e.get('fecha_inicio','')[:10]} | {e.get('titulo','')[:50]}")
    elif isinstance(data, dict):
        items = data.get("items", data.get("data", data.get("eventos", [])))
        total = data.get("total", data.get("count", len(items)))
        print(f"Total: {total} | retornados: {len(items)}")
        for e in items[:3]:
            print(f"  {e.get('fecha_inicio','')[:10]} | {e.get('titulo','')[:50]}")
    print("\nRaw keys:", list(data.keys()) if isinstance(data, dict) else "list")
else:
    print(r1.text[:200])
