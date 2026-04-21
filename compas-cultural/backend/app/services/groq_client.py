"""
Groq AI client: fast, cheap inference for scraping & event extraction.
Replaces Claude for ALL scraping tasks. Claude stays ONLY for user chat.

Models used:
  - llama-3.1-8b-instant     → text extraction, espacio parsing (cheapest: $0.05/$0.08 per 1M tokens)
  - llama-4-scout-17b-16e    → Vision / flyer analysis (multimodal: $0.11/$0.34 per 1M tokens)
  - llama-3.3-70b-versatile  → complex reasoning fallback ($0.59/$0.79 per 1M tokens)

Groq API is OpenAI-compatible, so we use the openai SDK.
"""
import json
import re
from typing import Optional

from openai import OpenAI

from app.config import settings

# ── Models ──────────────────────────────────────────────────────
MODEL_FAST = "llama-3.1-8b-instant"          # Text extraction, cheap
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"  # Multimodal (images)
MODEL_SMART = "llama-3.3-70b-versatile"      # Complex reasoning


def _get_client() -> Optional[OpenAI]:
    """Get a Groq client (OpenAI-compatible)."""
    if not settings.groq_api_key:
        return None
    return OpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )


def groq_chat(
    prompt: str,
    model: str = MODEL_FAST,
    max_tokens: int = 1500,
    temperature: float = 0,
    json_mode: bool = False,
) -> Optional[str]:
    """
    Send a text prompt to Groq and return the response text.

    Auto-fallback chain:
      - If 70b (MODEL_SMART) hits daily TPD limit  → retry with 8b (MODEL_FAST)
      - If 8b hits per-minute TPM limit             → truncate prompt and retry
      - If request too large (413)                  → truncate to 4000 chars and retry
    """
    client = _get_client()
    if not client:
        return None

    def _call(m: str, p: str) -> Optional[str]:
        kwargs: dict = {
            "model": m,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": p}],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()

    # Build fallback sequence: requested model first, then MODEL_FAST as backup
    models_to_try = [model] if model == MODEL_FAST else [model, MODEL_FAST]

    for attempt_model in models_to_try:
        effective_prompt = prompt
        # Hard limit for 8b: 5800 chars (~1450 tokens) to stay under 6K TPM
        if attempt_model == MODEL_FAST and len(prompt) > 5800:
            effective_prompt = prompt[:5800]
        try:
            return _call(attempt_model, effective_prompt)
        except Exception as e:
            err_str = str(e)
            is_tpd = "tokens per day" in err_str or "TPD" in err_str
            is_tpm = "tokens per minute" in err_str or "TPM" in err_str
            is_too_large = "Request too large" in err_str or "413" in err_str

            if is_tpd and attempt_model != MODEL_FAST:
                # Daily quota exhausted on big model → fall through to 8b
                print(f"  [GROQ] {attempt_model} daily limit hit → fallback to {MODEL_FAST}")
                continue

            if is_tpm or is_too_large:
                # Per-minute or size limit → truncate hard and retry once
                trunc = min(len(effective_prompt), 4000)
                print(f"  [GROQ] {attempt_model} size limit → truncating to {trunc} chars")
                try:
                    return _call(attempt_model, effective_prompt[:trunc])
                except Exception as e2:
                    print(f"  [GROQ] Error ({attempt_model} truncated): {e2}")
                    if attempt_model != MODEL_FAST:
                        continue  # try 8b next
                    return None

            print(f"  [GROQ] Error ({attempt_model}): {e}")
            return None

    return None


def groq_vision(
    prompt: str,
    image_url: str = "",
    image_b64: str = "",
    media_type: str = "image/jpeg",
    model: str = MODEL_VISION,
    max_tokens: int = 1500,
    temperature: float = 0,
    json_mode: bool = False,
) -> Optional[str]:
    """Send an image + text prompt to Groq Vision (Llama 4 Scout).
    Accepts either image_url (URL) or image_b64 (base64 string).
    """
    client = _get_client()
    if not client:
        return None

    content = []

    # Add image
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
        })
    elif image_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": image_url},
        })

    # Add text
    content.append({"type": "text", "text": prompt})

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": content}],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [GROQ Vision] Error: {e}")
        return None


def parse_json_response(raw: str) -> Optional[dict | list]:
    """Parse a JSON response, stripping markdown fences."""
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
