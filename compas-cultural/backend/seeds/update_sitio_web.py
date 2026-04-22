"""
update_sitio_web.py — Busca websites de colectivos/espacios sin sitio_web.

Estrategia (en orden):
1. Meta Graph API → campo `website` del perfil IG (más confiable)
2. Meta Graph API → extraer URL de la `biography`
3. Picuki / Imginn → scraping de bio pública

Uso:
    cd backend
    python seeds/update_sitio_web.py
    python seeds/update_sitio_web.py --dry-run      (solo muestra, no escribe)
    python seeds/update_sitio_web.py --max 50       (limita a 50 lugares)
    python seeds/update_sitio_web.py --tipo colectivo
"""

import sys, os, re, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import httpx
from bs4 import BeautifulSoup
from app.database import supabase
from app.config import settings

# ── URL pattern to extract from bio text ─────────────────────────────────
URL_PATTERN = re.compile(
    r'(https?://[^\s<>"\'()\[\]]+|'
    r'(?:www\.|linktr\.ee/|linkin\.bio/)[^\s<>"\'()\[\]]+)',
    re.I
)

# Domains to SKIP (social networks, not a "website")
SKIP_DOMAINS = {
    "instagram.com", "facebook.com", "twitter.com", "tiktok.com",
    "youtube.com", "youtu.be", "wa.me", "whatsapp.com",
    "maps.google.com", "goo.gl", "bit.ly", "t.co", "threads.net",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}


def clean_handle(raw: str) -> str:
    return raw.lstrip("@").strip().split("/")[0]


def clean_url(raw: str) -> str:
    raw = raw.rstrip(".,;!?)")
    if not raw.startswith("http"):
        raw = "https://" + raw
    return raw


def is_useful_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower().lstrip("www.")
        if any(domain == skip or domain.endswith("." + skip) for skip in SKIP_DOMAINS):
            return False
        return "." in domain and len(domain) > 3
    except Exception:
        return False


def extract_url_from_text(text: str) -> str | None:
    """Extract the first useful URL from any text string."""
    if not text:
        return None
    for raw in URL_PATTERN.findall(text):
        url = clean_url(raw)
        if is_useful_url(url):
            return url
    return None


# ── Strategy 1: Meta Graph API (website field + bio) ─────────────────────

def fetch_via_meta_api(handle: str) -> dict | None:
    """
    Use Meta Business Discovery API to get website + biography fields.
    Returns dict with 'website' and/or 'biography', or None on failure.
    """
    access_token = settings.meta_access_token
    my_ig_id = settings.meta_ig_business_account_id
    if not access_token or not my_ig_id:
        return None

    clean = clean_handle(handle)
    try:
        with httpx.Client(timeout=15) as client:
            # website is a separate field in the Business Discovery API
            fields_param = "business_discovery.fields(username,website,biography)"
            resp = client.get(
                f"https://graph.facebook.com/v21.0/{my_ig_id}",
                params={
                    "fields": fields_param,
                    "access_token": access_token,
                    "username": clean,
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            discovery = data.get("business_discovery", {})
            if not discovery:
                return None
            return {
                "website": discovery.get("website") or "",
                "biography": discovery.get("biography") or "",
            }
    except Exception:
        return None


# ── Strategy 2: Picuki / Imginn public scraping ───────────────────────────

def fetch_via_duckduckgo(nombre: str, handle: str) -> str | None:
    """
    Search DuckDuckGo HTML for the official website of this place.
    Query: '{nombre} sitio web oficial -instagram -facebook -twitter'
    """
    clean = clean_handle(handle)
    queries = [
        f'"{nombre}" Medellín sitio web -instagram.com -facebook.com -twitter.com -tiktok.com',
        f'"{clean}" instagram sitio web oficial Medellín -instagram.com -facebook.com',
    ]
    ddg_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-CO,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    for q in queries:
        try:
            with httpx.Client(follow_redirects=True, timeout=15, headers=ddg_headers) as client:
                resp = client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": q, "kl": "co-es"},
                )
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                # DDG HTML results: anchors with class "result__url"
                for a in soup.find_all("a", class_="result__url"):
                    href = a.get("href", "").strip()
                    if not href:
                        href = a.get_text(strip=True)
                    if not href.startswith("http"):
                        href = "https://" + href
                    if is_useful_url(href):
                        return href
                # Fallback: all result links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and is_useful_url(href):
                        low = href.lower()
                        if "duckduckgo" not in low:
                            return href
        except Exception:
            pass
        time.sleep(1.5)
    return None


def fetch_via_scraper(handle: str) -> str | None:
    """Returns bio text extracted from public Instagram scrapers."""
    clean = clean_handle(handle)
    scrapers = [
        f"https://www.picuki.com/profile/{clean}",
        f"https://imginn.com/{clean}/",
    ]
    for url in scrapers:
        try:
            with httpx.Client(follow_redirects=True, timeout=15, headers=HEADERS) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")

                # Try bio div
                bio_div = soup.find("div", class_=re.compile(r"profile-description|bio|description", re.I))
                if bio_div:
                    txt = bio_div.get_text(separator=" ", strip=True)
                    if txt and len(txt) > 5:
                        return txt

                # Try bio paragraph
                bio_p = soup.find("p", class_=re.compile(r"bio", re.I))
                if bio_p:
                    txt = bio_p.get_text(separator=" ", strip=True)
                    if txt:
                        return txt

                # Fallback: external links in the page
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and is_useful_url(href):
                        low = href.lower()
                        if "picuki" not in low and "imginn" not in low and "instagram" not in low:
                            return f"DIRECT:{href}"
        except Exception:
            pass
        time.sleep(1)
    return None


def find_website(nombre: str, handle: str) -> tuple[str | None, str]:
    """
    Try all strategies to find a website for the given IG handle.
    Returns (url_or_None, source_label).
    """
    # 1. Meta API: explicit website field (only works for Business accounts in our app)
    meta = fetch_via_meta_api(handle)
    if meta:
        if meta["website"] and is_useful_url(meta["website"]):
            return clean_url(meta["website"]), "meta_website"
        # 2. Meta API: URL in biography
        bio_url = extract_url_from_text(meta["biography"])
        if bio_url:
            return bio_url, "meta_bio"

    # 3. Public Instagram scraper (Picuki/Imginn)
    bio_text = fetch_via_scraper(handle)
    if bio_text:
        if bio_text.startswith("DIRECT:"):
            return bio_text[7:], "scraper_link"
        url = extract_url_from_text(bio_text)
        if url:
            return url, "scraper_bio"

    # 4. DuckDuckGo search
    ddg_url = fetch_via_duckduckgo(nombre, handle)
    if ddg_url:
        return ddg_url, "duckduckgo"

    return None, "not_found"


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra, no escribe en BD")
    parser.add_argument("--max", type=int, default=0, help="Limitar a N lugares (0 = todos)")
    parser.add_argument("--tipo", type=str, default="", help="Filtrar por tipo (colectivo, espacio, etc.)")
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

    if args.max:
        lugares = lugares[: args.max]

    print(f"   → {len(lugares)} lugares a procesar\n")

    found, not_found = [], []

    for i, lugar in enumerate(lugares, 1):
        nombre = lugar["nombre"]
        handle = lugar["instagram_handle"]
        lid = lugar["id"]
        tipo = lugar.get("tipo", "?")

        print(f"[{i:3d}/{len(lugares)}] {nombre} (@{handle}) [{tipo}]")

        website, source = find_website(nombre, handle)

        if not website:
            print(f"         ✗ sin URL")
            not_found.append(nombre)
        else:
            print(f"         ✅ {website}  ({source})")
            found.append({"nombre": nombre, "id": lid, "website": website, "handle": handle})
            if not args.dry_run:
                try:
                    supabase.table("lugares").update({"sitio_web": website}).eq("id", lid).execute()
                    print(f"         💾 guardado")
                except Exception as e:
                    print(f"         ❌ error al guardar: {e}")

        time.sleep(0.3)

    # ── Resumen ───────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"✅ ENCONTRADOS ({len(found)}):")
    for f in found:
        print(f"   @{f['handle']:<28s} {f['website']}")

    print(f"\n❌ SIN URL ({len(not_found)}):")
    for n in not_found:
        print(f"   • {n}")

    if args.dry_run:
        print("\n⚠️  DRY-RUN: nada fue escrito en la BD")


if __name__ == "__main__":
    main()

