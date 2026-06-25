# -*- coding: utf-8 -*-
"""
Supabase Storage — upload de imágenes para eventos admin.

Bucket: eventos-media  (debe existir y ser público en Supabase dashboard)
Path:   eventos/{slug}/{timestamp_ms}.webp
"""
from __future__ import annotations

import io
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

BUCKET = "eventos-media"
MAX_DIMENSION = 1280   # px
WEBP_QUALITY = 85
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _ensure_bucket() -> None:
    """Create the bucket if it doesn't exist yet (idempotent)."""
    try:
        from app.database import supabase
        buckets = supabase.storage.list_buckets()
        names = {b.name for b in (buckets or [])}
        if BUCKET not in names:
            supabase.storage.create_bucket(BUCKET, options={"public": True})
            log.info("Created Supabase Storage bucket: %s", BUCKET)
    except Exception as exc:
        log.warning("_ensure_bucket error (non-fatal): %s", exc)


def _process_image(file_bytes: bytes) -> bytes:
    """EXIF-rotate, resize to max 1280×1280, convert to WEBP."""
    from PIL import Image, ImageOps
    import io as _io

    img = Image.open(_io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # fix phone rotation

    # Convert palette/RGBA to RGB for WEBP
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize keeping aspect ratio
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    buf = _io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=4)
    return buf.getvalue()


def upload_event_image(file_bytes: bytes, original_filename: str, slug: str) -> str:
    """
    Process and upload an image to Supabase Storage.
    Returns the public URL of the uploaded file.
    Raises ValueError for invalid input; RuntimeError for upload failures.
    """
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise ValueError(f"Archivo demasiado grande (máx {MAX_SIZE_BYTES // (1024*1024)} MB)")

    # Validate it's an image
    try:
        processed = _process_image(file_bytes)
    except Exception as exc:
        raise ValueError(f"No se pudo procesar la imagen: {exc}") from exc

    _ensure_bucket()

    ts = int(time.time() * 1000)
    safe_slug = (slug or "evento")[:50].replace("/", "-")
    path = f"eventos/{safe_slug}/{ts}.webp"

    try:
        from app.database import supabase
        supabase.storage.from_(BUCKET).upload(
            path,
            processed,
            file_options={"content-type": "image/webp", "cache-control": "86400"},
        )
        url: str = supabase.storage.from_(BUCKET).get_public_url(path)
        log.info("Uploaded event image: %s (%d bytes)", path, len(processed))
        return url
    except Exception as exc:
        raise RuntimeError(f"Error subiendo imagen a Storage: {exc}") from exc


def delete_event_image(url: str) -> None:
    """Remove an image from Storage given its public URL (best-effort)."""
    try:
        from app.database import supabase
        # Extract path after bucket name
        marker = f"/{BUCKET}/"
        idx = url.find(marker)
        if idx == -1:
            return
        path = url[idx + len(marker):]
        supabase.storage.from_(BUCKET).remove([path])
    except Exception as exc:
        log.debug("delete_event_image error (non-fatal): %s", exc)
