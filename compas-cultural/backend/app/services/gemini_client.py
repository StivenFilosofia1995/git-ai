"""
gemini_client.py
================
Google Gemini client for ETÉREA's user-facing chat.

Model: gemini-2.0-flash (free tier: 1500 req/day, 1M tokens/min)
Used ONLY for chat — scraping uses Groq + code-first extractors.

Fallback chain:
  Gemini 2.0 Flash → Groq 70b → Groq 8b → respuesta_fallback local
"""
from typing import Optional

from app.config import settings


def gemini_chat(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Send a chat conversation to Gemini 2.0 Flash.

    Args:
        system_prompt: System instructions (ETÉREA persona + cultural context)
        messages: List of {"role": "user"|"assistant", "content": "..."}
        max_tokens: Max tokens in response
        temperature: 0.0–1.0

    Returns:
        Response text or None if unavailable/error.
    """
    if not settings.gemini_api_key:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )

        # Convert OpenAI-style messages to Gemini history format
        # Gemini uses "user"/"model" roles (not "assistant")
        history = []
        for msg in messages[:-1]:  # all but last
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})

        # Last message is the current user turn
        last_msg = messages[-1]["content"] if messages else ""

        chat_session = model.start_chat(history=history)
        response = chat_session.send_message(last_msg)
        return response.text.strip()

    except Exception as e:
        print(f"[gemini_client] Error: {e}")
        return None
