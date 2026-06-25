"""
playwright_fetcher.py
=====================
Optional JavaScript-rendered page fetcher using Playwright (Chromium headless).
Falls back gracefully to httpx if playwright is not installed.

Use for JS-heavy SPAs where normal httpx fetch gets empty content:
  - Comfenalco, Comfama, Fundación EPM, etc.
"""
from typing import Optional

# Sites that need JavaScript execution to render event content
JS_HEAVY_DOMAINS = [
    "comfenalcoantioquia.com.co",
    "comfama.com",
    "fundacionepm.org",
    "distritosanignacio.com",
    "vivirenelpoblado.com",
    "sistemabibliotecasmedellin.gov.co",
    "bibliotecapiloto.gov.co",
]

# Extra wait selectors per domain to ensure content loads
_WAIT_SELECTORS: dict[str, str] = {
    "comfenalcoantioquia.com.co": "a[href*='evento']",
    "comfama.com": ".card, article",
    "vivirenelpoblado.com": "article, .event",
    "bibliotecapiloto.gov.co": "article, .event-item, .agenda-item, h2, h3",
}


def needs_playwright(url: str) -> bool:
    return any(d in url for d in JS_HEAVY_DOMAINS)


async def fetch_with_playwright(url: str) -> Optional[str]:
    """
    Fetch fully JS-rendered HTML using Playwright Chromium.
    Returns raw HTML string or None if unavailable/error.

    Install requirements:
        pip install playwright
        playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return None  # playwright not installed — silent fallback

    wait_sel = next((v for k, v in _WAIT_SELECTORS.items() if k in url), None)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-gpu", "--disable-extensions"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="es-CO",
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                if wait_sel:
                    try:
                        await page.wait_for_selector(wait_sel, timeout=8_000)
                    except PWTimeout:
                        pass
                else:
                    await page.wait_for_timeout(2_500)
                html = await page.content()
            finally:
                await browser.close()
            return html
    except Exception as e:
        print(f"    ⚠ Playwright error [{url}]: {e}")
        return None
