import asyncio
import traceback
from fastapi import APIRouter, Request
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service
from app.limiter import rate_limit

router = APIRouter()


@router.post("/", response_model=ChatResponse)
@rate_limit("10/minute")
async def chat_cultural(request: ChatRequest, req: Request):
    user_id = (
        req.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (req.client.host if req.client else "anonymous")
    )
    try:
        return await asyncio.to_thread(chat_service.chat, request, user_id)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] Chat failed for {user_id}: {e}\n{tb}")
        # Return error details in response so we can see what's failing
        return ChatResponse(
            respuesta=f"[DEBUG] Error: {type(e).__name__}: {e}",
            fuentes=[],
        )