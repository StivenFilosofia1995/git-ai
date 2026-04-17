from fastapi import APIRouter
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def chat_cultural(request: ChatRequest):
    return chat_service.chat(request)