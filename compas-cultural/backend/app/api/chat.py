import traceback
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service
from app.limiter import rate_limit
import json

router = APIRouter()


@router.post("/")
async def chat_cultural(body: ChatRequest, request: Request):
    user_id = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "anonymous")
    )
    try:
        result = chat_service.chat(body, user_id)
        return JSONResponse(
            content=json.loads(result.model_dump_json()),
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        print(f"[ERROR] Chat failed: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            content={
                "respuesta": (
                    "Perdón, tuve un problema técnico momentáneo. "
                    "¿Me repetís tu mensaje? También podés decirme zona, categoría o si buscás algo para hoy."
                ),
                "fuentes": [],
            },
            media_type="application/json; charset=utf-8",
        )


@router.get("/test")
async def chat_test():
    """Test endpoint — verifica motor de chat activo (incluye Ollama)."""
    try:
        from app.config import settings
        result = {
            "chat_engine": settings.chat_engine,
            "groq_key": bool(settings.groq_api_key),
            "gemini_key": bool(settings.gemini_api_key),
            "anthropic_key": bool(settings.anthropic_api_key),
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
        }
        from app.services.chat_service import _chat_via_groq, _chat_via_ollama
        from app.services.ollama_client import ollama_health

        result["ollama_health"] = ollama_health()

        if (settings.chat_engine or "").lower() == "ollama":
            r = _chat_via_ollama("Di solo: OK", [{"role": "user", "content": "test"}])
            result["ollama_response"] = r
        else:
            r = _chat_via_groq("Di solo: OK", [{"role": "user", "content": "test"}])
            result["groq_response"] = r
        return result
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}