from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr
from app.services.email_service import send_welcome_email

router = APIRouter()


class WelcomeEmailRequest(BaseModel):
    email: EmailStr
    nombre: str | None = None


@router.post("/welcome-email")
async def enviar_email_bienvenida(req: WelcomeEmailRequest, bg: BackgroundTasks):
    bg.add_task(send_welcome_email, req.email, req.nombre)
    return {"ok": True, "mensaje": "Email de bienvenida en cola de envío"}
