from fastapi import APIRouter, BackgroundTasks
import logging
from pydantic import BaseModel, EmailStr
from app.services.email_service import send_welcome_email
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class WelcomeEmailRequest(BaseModel):
    email: EmailStr
    nombre: str | None = None


@router.post("/welcome-email")
async def enviar_email_bienvenida(req: WelcomeEmailRequest):
    # Send synchronously so we can report success/failure
    logger.info("Welcome email requested for %s (nombre=%s)", req.email, req.nombre)
    logger.info(
        "Email config: smtp_host=%s, smtp_port=%s, smtp_user=%s, smtp_password_set=%s, resend_key_set=%s",
        settings.smtp_host, settings.smtp_port, settings.smtp_user,
        bool(settings.smtp_password), bool(settings.resend_api_key),
    )
    ok = send_welcome_email(req.email, req.nombre)
    if ok:
        return {"ok": True, "mensaje": "Email de bienvenida enviado"}
    return {"ok": False, "mensaje": "No se pudo enviar el email. Revisa configuración SMTP."}


@router.get("/email-status")
async def email_status():
    """Check if email is properly configured (no secrets exposed)."""
    return {
        "smtp_configured": bool(settings.smtp_password and settings.smtp_user),
        "resend_configured": bool(settings.resend_api_key),
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user_set": bool(settings.smtp_user),
        "smtp_password_set": bool(settings.smtp_password),
        "smtp_from_email": settings.smtp_from_email,
        "frontend_url": settings.frontend_url,
    }
