"""
Script para obtener META_ACCESS_TOKEN (long-lived) y META_IG_BUSINESS_ACCOUNT_ID.

USO:
    python get_meta_credentials.py <SHORT_LIVED_TOKEN> <APP_ID> <APP_SECRET>

Donde:
- SHORT_LIVED_TOKEN: el token que copiaste del Graph API Explorer
- APP_ID: ID de tu app (está en el dashboard de developers.facebook.com)
- APP_SECRET: Secreto de la app (developers.facebook.com → Configuración → Básica)
"""
import sys
import httpx

BASE = "https://graph.facebook.com/v19.0"


def get_long_lived_token(short_token: str, app_id: str, app_secret: str) -> str:
    resp = httpx.get(f"{BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    data = resp.json()
    if "error" in data:
        print(f"❌ Error obteniendo long-lived token: {data['error']['message']}")
        sys.exit(1)
    token = data["access_token"]
    expires = data.get("expires_in", "desconocido")
    print(f"✅ Long-lived token obtenido (expira en {expires} segundos ≈ 60 días)")
    return token


def get_pages(token: str) -> list:
    resp = httpx.get(f"{BASE}/me/accounts", params={"access_token": token})
    data = resp.json()
    if "error" in data:
        print(f"❌ Error obteniendo páginas: {data['error']['message']}")
        sys.exit(1)
    return data.get("data", [])


def get_ig_business_account(page_id: str, page_token: str) -> str | None:
    resp = httpx.get(f"{BASE}/{page_id}", params={
        "fields": "instagram_business_account",
        "access_token": page_token,
    })
    data = resp.json()
    ig = data.get("instagram_business_account", {})
    return ig.get("id")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    short_token = sys.argv[1]
    app_id = sys.argv[2]
    app_secret = sys.argv[3]

    print("\n🔑 Paso 1: Obteniendo long-lived token...")
    long_token = get_long_lived_token(short_token, app_id, app_secret)

    print("\n📄 Paso 2: Obteniendo tus Facebook Pages...")
    pages = get_pages(long_token)

    if not pages:
        print("❌ No se encontraron Facebook Pages asociadas a este token.")
        print("   Asegurate de que la app tenga permiso 'pages_show_list' y de seleccionar la Page en el Explorer.")
        sys.exit(1)

    print(f"   Se encontraron {len(pages)} página(s):\n")

    target_page = None
    target_ig_id = None
    target_page_token = None

    for page in pages:
        page_id = page["id"]
        page_name = page["name"]
        page_token = page.get("access_token", long_token)

        ig_id = get_ig_business_account(page_id, page_token)

        status = f"✅ Instagram ID: {ig_id}" if ig_id else "⚠️  Sin cuenta Instagram Business conectada"
        print(f"   📄 {page_name} (ID: {page_id}) — {status}")

        if ig_id and not target_ig_id:
            target_page = page_name
            target_ig_id = ig_id
            target_page_token = page_token

    if not target_ig_id:
        print("\n❌ Ninguna página tiene una cuenta Instagram Business conectada.")
        print("   Pasos para conectar:")
        print("   1. Ve a tu Facebook Page → Configuración → Plataformas vinculadas")
        print("   2. Conecta tu cuenta de Instagram (debe ser Business o Creator)")
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ CREDENCIALES PARA TU .env Y RAILWAY:")
    print("="*60)
    print(f"\nMETA_ACCESS_TOKEN={target_page_token}")
    print(f"META_IG_BUSINESS_ACCOUNT_ID={target_ig_id}")
    print("\n(Página utilizada:", target_page, ")")
    print("\n⚠️  El Page Access Token dura ~60 días.")
    print("   Para un token permanente, necesitás una app en producción de Meta.")
    print("="*60)


if __name__ == "__main__":
    main()
