from __future__ import annotations

import io
import ipaddress
import re
import socket
from typing import Iterable, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - optional fallback
    Image = None
    ImageOps = None


router = APIRouter()

_ALLOWED_KINDS = {"thumb", "card", "detail"}
_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
_USER_AGENT = "CulturaEtereaMediaProxy/1.0"


def _is_http_url(value: Optional[str]) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_private_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return True
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
    except ValueError:
        pass

    try:
        addrs = socket.getaddrinfo(host, None)
    except Exception:
        return True

    for entry in addrs:
        raw_ip = entry[4][0]
        try:
            ip = ipaddress.ip_address(raw_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return True
        except ValueError:
            return True
    return False


def _is_safe_public_url(value: Optional[str]) -> bool:
    if not _is_http_url(value):
        return False
    parsed = urlparse(value or "")
    return not _is_private_host(parsed.hostname or "")


_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)
_TWITTER_IMAGE_RE = re.compile(
    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)["\']',
    re.IGNORECASE,
)
_TWITTER_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+name=["\']twitter:image["\']',
    re.IGNORECASE,
)


async def _extract_og_image(source_url: str) -> Optional[str]:
    """Fetch page HTML and extract og:image or twitter:image URL."""
    if not _is_safe_public_url(source_url):
        return None
    # Skip known media domains — fetching their HTML won't give og:image for the post
    hostname = (urlparse(source_url).hostname or "").lower()
    if any(h in hostname for h in ("instagram.com", "fb.com", "facebook.com", "tiktok.com")):
        return None
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CulturaEtereaBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = await client.get(source_url)
        if resp.status_code != 200:
            return None
        html = resp.text[:80_000]  # only need the head
        for pattern in (_OG_IMAGE_RE, _OG_IMAGE_RE2, _TWITTER_IMAGE_RE, _TWITTER_IMAGE_RE2):
            m = pattern.search(html)
            if m:
                candidate = m.group(1)
                if _is_safe_public_url(candidate):
                    return candidate
    except Exception:
        pass
    return None


async def _fetch_image_bytes(candidates: Iterable[str]) -> tuple[bytes, str, str]:
    timeout = httpx.Timeout(12.0, connect=6.0)
    headers = {"User-Agent": _USER_AGENT, "Accept": "image/*,*/*;q=0.8"}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for candidate in candidates:
            try:
                response = await client.get(candidate)
            except Exception:
                continue

            if response.status_code != 200:
                continue

            body = response.content
            if not body or len(body) > _MAX_DOWNLOAD_BYTES:
                continue

            content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()

            if content_type.startswith("image/"):
                return body, content_type, candidate

            # Some CDNs send wrong content-type; sniff image if Pillow is available.
            if Image is not None:
                try:
                    with Image.open(io.BytesIO(body)) as img:
                        img.verify()
                    return body, "image/jpeg", candidate
                except Exception:
                    continue

    raise HTTPException(status_code=404, detail="No fue posible obtener una imagen valida")


def _normalize_image(body: bytes, kind: str) -> tuple[bytes, str]:
    if Image is None or ImageOps is None:
        return body, "image/jpeg"

    max_sizes = {
        "thumb": (320, 320),
        "card": (1280, 960),
        "detail": (1920, 1920),
    }
    target = max_sizes.get(kind, max_sizes["card"])

    try:
        with Image.open(io.BytesIO(body)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")

            image.thumbnail(target, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            image.save(output, format="WEBP", quality=82, method=6)
            return output.getvalue(), "image/webp"
    except Exception:
        return body, "image/jpeg"


@router.get("/event-image")
async def get_event_image(
    src: Optional[str] = Query(default=None),
    source_url: Optional[str] = Query(default=None),
    kind: str = Query(default="card"),
):
    """Fetch and normalize remote event image to a frontend-safe output.

    Priority chain:
      1. Direct image URL (src)
      2. og:image / twitter:image extracted from source_url HTML
    """
    if kind not in _ALLOWED_KINDS:
        raise HTTPException(status_code=400, detail="kind invalido")

    candidates: list[str] = []

    # 1. Direct image URL
    if _is_safe_public_url(src):
        candidates.append(src or "")

    # 2. og:image / twitter:image from source page
    if _is_safe_public_url(source_url):
        og_url = await _extract_og_image(source_url or "")
        if og_url:
            candidates.append(og_url)

    if not candidates:
        raise HTTPException(status_code=404, detail="No hay fuente de imagen valida")

    raw_bytes, content_type, used_source = await _fetch_image_bytes(candidates)
    image_bytes, normalized_type = _normalize_image(raw_bytes, kind)

    return Response(
        content=image_bytes,
        media_type=normalized_type or content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Media-Source": used_source,
        },
    )
