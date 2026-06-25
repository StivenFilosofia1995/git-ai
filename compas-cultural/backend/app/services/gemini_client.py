"""
gemini_client.py
================
Google Gemini client usando el endpoint compatible con OpenAI.
NO necesita instalar google-generativeai — usa el SDK openai que ya está instalado.

Model: gemini-2.0-flash (free tier: 1500 req/day, 1M tokens/min)
"""
from typing import Optional

from openai import OpenAI

from app.config import settings


def gemini_chat(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Send chat to Gemini 2.0 Flash via OpenAI-compatible endpoint.
    Uses openai SDK (already installed) — no extra packages needed.
    """
    if not settings.gemini_api_key:
        return None

    try:
        client = OpenAI(
            api_key=settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

        groq_messages = [{"role": "system", "content": system_prompt}] + messages

        response = client.chat.completions.create(
            model=settings.gemini_model,
            messages=groq_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content
        return text.strip() if text else None

    except Exception as e:
        print(f"[gemini_client] Error: {e}")
        return None
