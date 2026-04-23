"""Local LLM client via Ollama (no external API keys)."""

from typing import Optional
import httpx
from openai import OpenAI
from app.config import settings


def _get_client() -> Optional[OpenAI]:
    try:
        return OpenAI(api_key="ollama", base_url=settings.ollama_base_url)
    except Exception as e:
        print(f"[ollama_client] init failed: {e}")
        return None


def ollama_chat(
    system_prompt: str,
    messages: list,
    max_tokens: int,
    temperature: float,
) -> Optional[str]:
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model=settings.ollama_model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[ollama_client] chat failed: {e}")
        return None


def ollama_health() -> dict:
    """Connectivity check against native Ollama API (/api/tags)."""
    base = (settings.ollama_base_url or "").rstrip("/")
    native = base[:-3] if base.endswith("/v1") else base
    tags_url = f"{native}/api/tags"
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(tags_url)
            r.raise_for_status()
            payload = r.json() if r.content else {}
        models = [m.get("name") for m in payload.get("models", []) if m.get("name")]
        return {
            "ok": True,
            "tags_url": tags_url,
            "models": models,
            "model_configured": settings.ollama_model,
            "model_present": settings.ollama_model in models,
        }
    except Exception as exc:
        return {
            "ok": False,
            "tags_url": tags_url,
            "error": str(exc),
            "model_configured": settings.ollama_model,
        }
