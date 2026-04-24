from __future__ import annotations

import os
import re
import tempfile
from typing import Optional

import httpx

from app.database import supabase


_TIME_RE = re.compile(
    r"\b(\d{1,2})\s*[:\.h]\s*(\d{2})\s*((?:a|p)\.?\s*m\.?|am|pm|a|p)?\b"
    r"|\b(\d{1,2})\s*((?:a|p)\.?\s*m\.?|am|pm|a|p)\b",
    re.I,
)

_HAS_EVENING_CONTEXT_RE = re.compile(
    r"\b(noche|tarde|show|concierto|funcion|presentacion|en vivo|festival)\b",
    re.I,
)

_OCR_DISABLED = False
_EASYOCR_READER = None
_CACHE: dict[str, Optional[tuple[int, int]]] = {}
_TEXT_CACHE: dict[str, Optional[str]] = {}


def _normalize_hour(hour: int, minute: int, meridian: str, context_text: str) -> Optional[tuple[int, int]]:
    mer = re.sub(r"\s+|\.", "", (meridian or "").lower())
    h = hour
    if mer in ("pm", "p") and h < 12:
        h += 12
    elif mer in ("am", "a") and h == 12:
        h = 0
    elif not mer and 1 <= h <= 11:
        if _HAS_EVENING_CONTEXT_RE.search(context_text or "") and h <= 11:
            h += 12
        else:
            return None
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None
    return h, minute


def parse_hour_from_text(text: str) -> Optional[tuple[int, int]]:
    if not text:
        return None
    match = _TIME_RE.search(text)
    if not match:
        return None
    groups = match.groups()
    if groups[0] and groups[1]:
        hour = int(groups[0])
        minute = int(groups[1])
        meridian = groups[2] or ""
    elif groups[3] and groups[4]:
        hour = int(groups[3])
        minute = 0
        meridian = groups[4] or ""
    else:
        return None
    return _normalize_hour(hour, minute, meridian, text)


def _get_easyocr_reader():
    global _OCR_DISABLED, _EASYOCR_READER
    if _OCR_DISABLED:
        return None
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER
    try:
        import easyocr  # type: ignore
        _EASYOCR_READER = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
        return _EASYOCR_READER
    except Exception:
        _OCR_DISABLED = True
        return None


def _ocr_backends() -> list[str]:
    """Ordered OCR backend list from env (default: easyocr,tesseract)."""
    raw = os.getenv("OCR_BACKENDS", "easyocr,tesseract")
    return [b.strip().lower() for b in raw.split(",") if b.strip()]


def _preprocess_for_ocr(image_path: str) -> str:
    """Best-effort preprocessing to improve OCR on IG flyers."""
    try:
        import cv2  # type: ignore

        img = cv2.imread(image_path)
        if img is None:
            return image_path
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        proc = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            2,
        )
        out_path = f"{image_path}.proc.png"
        cv2.imwrite(out_path, proc)
        return out_path
    except Exception:
        return image_path


def _extract_text_easyocr(image_path: str) -> Optional[str]:
    reader = _get_easyocr_reader()
    if reader is None:
        return None
    try:
        lines = reader.readtext(image_path, detail=0, paragraph=True)
        text = "\n".join(str(x) for x in lines).strip()
        return text or None
    except Exception:
        return None


def _extract_text_tesseract(image_path: str) -> Optional[str]:
    """Optional fallback OCR backend (requires tesseract binary installed)."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        text = pytesseract.image_to_string(
            Image.open(image_path),
            lang="spa+eng",
            config="--oem 3 --psm 6",
        )
        text = (text or "").strip()
        return text or None
    except Exception:
        return None


def _persist_ocr_run(
    image_url: str,
    backend: str,
    status: str,
    raw_text: Optional[str],
    parsed_hm: Optional[tuple[int, int]] = None,
) -> None:
    """Best-effort OCR audit logging into Supabase.

    This allows quality monitoring and future reprocessing of problematic flyers.
    """
    try:
        if parsed_hm:
            confidence_time = 0.75
        elif raw_text:
            confidence_time = 0.15
        else:
            confidence_time = 0.0

        extracted_hour = parsed_hm[0] if parsed_hm else None
        extracted_minute = parsed_hm[1] if parsed_hm else None

        payload = {
            "image_url": image_url,
            "backend": backend,
            "status": status,
            "raw_text": raw_text,
            "extracted_time_text": None,
            "extracted_hour": extracted_hour,
            "extracted_minute": extracted_minute,
            "confidence_time": confidence_time,
            "confidence_date": None,
            "timezone": "America/Bogota",
        }
        supabase.table("event_ocr_runs").insert(payload).execute()
    except Exception:
        # Never block scraping if audit logging fails.
        pass


def extract_text_from_image_url(image_url: Optional[str]) -> Optional[str]:
    """Extract raw OCR text from an image URL.

    Backends:
      - easyocr (PyTorch)
      - tesseract (optional local install)
    """
    if not image_url:
        return None
    if image_url in _TEXT_CACHE:
        return _TEXT_CACHE[image_url]

    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(image_url)
            resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as fp:
            fp.write(resp.content)
            fp.flush()
            processed = _preprocess_for_ocr(fp.name)

            text: Optional[str] = None
            used_backend = "none"
            for backend in _ocr_backends():
                used_backend = backend
                if backend == "easyocr":
                    text = _extract_text_easyocr(processed)
                elif backend == "tesseract":
                    text = _extract_text_tesseract(processed)
                if text:
                    break

            _TEXT_CACHE[image_url] = text
            _persist_ocr_run(
                image_url=image_url,
                backend=used_backend,
                status="ok" if text else "empty",
                raw_text=text,
                parsed_hm=parse_hour_from_text(text) if text else None,
            )
            return text
    except Exception:
        _TEXT_CACHE[image_url] = None
        _persist_ocr_run(
            image_url=image_url,
            backend="none",
            status="error",
            raw_text=None,
            parsed_hm=None,
        )
        return None


def extract_hour_from_image_url(image_url: Optional[str]) -> Optional[tuple[int, int]]:
    if not image_url:
        return None
    if image_url in _CACHE:
        return _CACHE[image_url]

    text = extract_text_from_image_url(image_url)
    if not text:
        _CACHE[image_url] = None
        return None
    parsed = parse_hour_from_text(text)
    _CACHE[image_url] = parsed
    return parsed
