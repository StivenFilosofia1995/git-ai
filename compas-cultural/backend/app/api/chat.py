import traceback
from fastapi import APIRouter, Request
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service
from app.limiter import rate_limit

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat_cultural(body: ChatRequest, request: Request):
    user_id = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "anonymous")
    )
    try:
        return chat_service.chat(body, user_id)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] Chat failed for {user_id}: {e}\n{tb}")
        return ChatResponse(
            respuesta=f"[DEBUG] Error: {type(e).__name__}: {e}",
            fuentes=[],
        )


@router.get("/test")
async def chat_test():
    """Test endpoint — verifica que Groq funciona."""
    try:
        from app.config import settings
        result = {"groq_key": bool(settings.groq_api_key)}
        from app.services.chat_service import _chat_via_groq
        r = _chat_via_groq("Di solo: OK", [{"role": "user", "content": "test"}])
        result["groq_response"] = r
        return result
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}