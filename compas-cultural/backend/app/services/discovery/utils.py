# -*- coding: utf-8 -*-
"""
Utilidades HTTP y de extracción para el módulo de descubrimiento.
"""
import random
import re
import asyncio
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .config import BASE_HEADERS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, TIMEOUT, MAX_RETRIES

# ── User-agents rotativos ────────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


async def polite_delay():
    """Espera aleatoria entre requests para no ser bloqueado."""
    await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


async def fetch_url(url: str, params: dict = None) -> httpx.Response | None:
    """Fetch URL con retry, headers rotativos y timeout."""
    headers = {**BASE_HEADERS, "User-Agent": _random_ua()}
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=TIMEOUT, verify=False
            ) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            if attempt == MAX_RETRIES - 1:
                return None
            await asyncio.sleep(2 * (attempt + 1))
    return None


def clean_text(text: str) -> str:
    """Limpia texto HTML."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_platform(url: str) -> str:
    """Detecta la plataforma de una URL de red social."""
    domain = urlparse(url).netloc.lower()
    if "instagram" in domain:
        return "instagram"
    if "facebook" in domain:
        return "facebook"
    if "twitter" in domain or "x.com" in domain:
        return "twitter"
    if "tiktok" in domain:
        return "tiktok"
    return "web"


def handle_from_url(url: str) -> str:
    """Extrae el handle de una URL de red social."""
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if not parts or not parts[0]:
        return ""
    handle = parts[0].lower()
    # Filtrar paths que no son handles
    skip = {"explore", "p", "reel", "stories", "pages", "groups",
            "events", "profile.php", "people", "watch", "photo", "reels"}
    if handle in skip:
        return ""
    return f"@{handle}"


def extract_handles(text: str) -> list[str]:
    """Extrae handles de redes sociales (@username) de texto."""
    raw = re.findall(r"@([A-Za-z0-9_.]{2,30})", text)
    # Filtrar handles comunes que no son reales
    skip = {"gmail", "hotmail", "outlook", "yahoo", "email", "correo", "media"}
    return [h for h in raw if h.lower() not in skip]


def extract_emails(text: str) -> list[str]:
    """Extrae emails de texto."""
    return re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)


def extract_phones(text: str) -> list[str]:
    """Extrae teléfonos colombianos de texto."""
    return re.findall(r"(?:\+57\s?)?(?:3\d{2}[\s\-]?\d{3}[\s\-]?\d{4})", text)


def extract_og_image(soup: BeautifulSoup) -> str | None:
    """Extrae og:image de los meta tags."""
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    tag = soup.find("meta", attrs={"name": "twitter:image"})
    if tag and tag.get("content"):
        return tag["content"]
    return None
