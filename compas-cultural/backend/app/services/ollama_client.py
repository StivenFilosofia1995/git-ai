"""Local LLM client via Ollama (no external API keys)."""

from typing import Optional
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
