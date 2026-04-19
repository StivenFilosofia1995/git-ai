import asyncio
from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat_cultural(request: ChatRequest):
    # Ejecutar en thread pool para no bloquear el event loop de FastAPI
    # (anthropic.Anthropic es síncrono y puede tardar varios segundos)
    return await asyncio.to_thread(chat_service.chat, request)