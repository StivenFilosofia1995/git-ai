import asyncio
from fastapi import APIRouter, Request, HTTPException
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat_cultural(request: ChatRequest, req: Request):
    # Identify user by IP (X-Forwarded-For behind proxy) for rate limiting
    user_id = (
        req.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (req.client.host if req.client else "anonymous")
    )
    try:
        # Ejecutar en thread pool para no bloquear el event loop de FastAPI
        # (anthropic.Anthropic es síncrono y puede tardar varios segundos)
        return await asyncio.to_thread(chat_service.chat, request, user_id)
    except Exception as e:
        print(f"[ERROR] Chat failed for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="No pudimos procesar tu pregunta. Intenta de nuevo en unos momentos."
        )