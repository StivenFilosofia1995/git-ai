from __future__ import annotations

import re
import tempfile
from typing import Optional

import httpx


_TIME_RE = re.compile(
    r"\b(\d{1,2})[:\.h](\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm)?\b"
    r"|\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?|am|pm)\b",
    re.I,
)

_HAS_EVENING_CONTEXT_RE = re.compile(
    r"\b(noche|tarde|show|concierto|funcion|funcion|presentacion|presentacion|en vivo|festival)\b",
    re.I,
)

_OCR_DISABLED = False
_EASYOCR_READER = None
_CACHE: dict[str, Optional[tuple[int, int]]] = {}


def _normalize_hour(hour: int, minute: int, meridian: str, context_text: str) -> Optional[tuple[int, int]]:
    mer = (meridian or "").lower().replace(".", "")
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


def extract_hour_from_image_url(image_url: Optional[str]) -> Optional[tuple[int, int]]:
    if not image_url:
        return None
    if image_url in _CACHE:
        return _CACHE[image_url]

    reader = _get_easyocr_reader()
    if reader is None:
        _CACHE[image_url] = None
        return None

    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(image_url)
            resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as fp:
            fp.write(resp.content)
            fp.flush()
            lines = reader.readtext(fp.name, detail=0, paragraph=True)
        text = "\n".join(str(x) for x in lines)
        parsed = parse_hour_from_text(text)
        _CACHE[image_url] = parsed
        return parsed
    except Exception:
        _CACHE[image_url] = None
        return None
