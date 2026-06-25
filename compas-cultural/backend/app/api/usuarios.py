"""
API /usuarios
Registro y gestión de usuarios finales de la plataforma.

Flujo de registro:
  1. POST /usuarios/registro → crea usuario en Supabase Auth + perfil inicial
  2. Supabase envía email de confirmación (si está habilitado en el proyecto)
  3. POST /usuarios/login  → retorna JWT de Supabase Auth
  4. El JWT se usa en Authorization: Bearer <jwt> para endpoints autenticados

El JWT es emitido por Supabase Auth y verificado por el backend en perfil.py.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import logging
import re

from app.config import settings
from app.database import supabase
from app.limiter import rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN = 8


# ─── Schemas ───────────────────────────────────────────────────────────────

class RegistroUsuarioRequest(BaseModel):
    email: EmailStr
    password: str
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    municipio: str = "medellin"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < _MIN_PASSWORD_LEN:
            raise ValueError(f"La contraseña debe tener al menos {_MIN_PASSWORD_LEN} caracteres")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not re.search(r"[0-9]", v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegistroUsuarioResponse(BaseModel):
    ok: bool
    mensaje: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    requiere_confirmacion: bool = False


class LoginResponse(BaseModel):
    ok: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    expires_in: Optional[int] = None
    mensaje: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.post(
    "/registro",
    response_model=RegistroUsuarioResponse,
    status_code=201,
    summary="Registrar nuevo usuario",
    description=(
        "Crea una cuenta de usuario en la plataforma. "
        "Supabase envía un email de confirmación si está habilitado. "
        "El usuario puede hacer login inmediatamente (en proyectos sin confirmación obligatoria)."
    ),
)
@rate_limit("5/hour")
async def registrar_usuario(body: RegistroUsuarioRequest, request: Request):
    """Registra un nuevo usuario en Supabase Auth y crea perfil básico."""
    try:
        # Sign up via Supabase Auth
        auth_resp = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {
                    "nombre": body.nombre or "",
                    "apellido": body.apellido or "",
                    "municipio": body.municipio,
                }
            }
        })
    except Exception as exc:
        msg = str(exc).lower()
        if "already registered" in msg or "already exists" in msg or "duplicate" in msg:
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
        logger.error("Supabase sign_up error: %s", exc)
        raise HTTPException(status_code=500, detail="Error al crear el usuario. Intenta más tarde.")

    user = getattr(auth_resp, "user", None)
    if not user:
        # If supabase returns no user but no exception, likely duplicate
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    user_id = str(user.id)

    # Create profile record
    try:
        nombre = body.nombre or body.email.split("@")[0]
        apellido = body.apellido or ""
        supabase.table("perfiles").upsert(
            {
                "user_id": user_id,
                "nombre": nombre,
                "apellido": apellido,
                "email": body.email,
                "municipio": body.municipio,
                "preferencias": [],
            },
            on_conflict="user_id",
        ).execute()
    except Exception as exc:
        logger.warning("No se pudo crear perfil para usuario %s: %s", user_id, exc)

    # Send welcome email (best-effort)
    try:
        from app.services.email_service import send_welcome_email
        send_welcome_email(body.email, body.nombre)
    except Exception:
        pass

    session = getattr(auth_resp, "session", None)
    email_confirmed = getattr(user, "email_confirmed_at", None)
    requiere_confirmacion = session is None and not email_confirmed

    return RegistroUsuarioResponse(
        ok=True,
        user_id=user_id,
        email=body.email,
        requiere_confirmacion=requiere_confirmacion,
        mensaje=(
            "¡Revisa tu email para confirmar tu cuenta antes de hacer login!"
            if requiere_confirmacion
            else "¡Cuenta creada! Ya puedes explorar la agenda cultural."
        ),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Iniciar sesión",
    description="Inicia sesión con email y contraseña. Retorna access_token JWT de Supabase.",
)
@rate_limit("10/hour")
async def login_usuario(body: LoginRequest, request: Request):
    """Login con email y contraseña. Retorna JWT para usar en endpoints protegidos."""
    try:
        auth_resp = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as exc:
        msg = str(exc).lower()
        if "invalid login" in msg or "invalid credentials" in msg or "email not confirmed" in msg:
            raise HTTPException(
                status_code=401,
                detail="Email o contraseña incorrectos. Si es tu primer acceso, confirma tu email."
            )
        logger.error("Supabase sign_in error: %s", exc)
        raise HTTPException(status_code=500, detail="Error al iniciar sesión. Intenta más tarde.")

    session = getattr(auth_resp, "session", None)
    user = getattr(auth_resp, "user", None)

    if not session or not session.access_token:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    return LoginResponse(
        ok=True,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=str(user.id) if user else None,
        email=str(user.email) if user else None,
        expires_in=session.expires_in,
        mensaje="Login exitoso",
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Refrescar token",
    description="Usa el refresh_token para obtener un nuevo access_token sin volver a hacer login.",
)
@rate_limit("30/hour")
async def refresh_token(body: RefreshRequest, request: Request):
    """Refresca el JWT usando el refresh_token."""
    try:
        auth_resp = supabase.auth.refresh_session(body.refresh_token)
    except Exception as exc:
        logger.error("Supabase refresh error: %s", exc)
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

    session = getattr(auth_resp, "session", None)
    user = getattr(auth_resp, "user", None)

    if not session or not session.access_token:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

    return LoginResponse(
        ok=True,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=str(user.id) if user else None,
        email=str(user.email) if user else None,
        expires_in=session.expires_in,
        mensaje="Token refrescado",
    )


@router.post(
    "/logout",
    summary="Cerrar sesión",
)
async def logout_usuario(request: Request):
    """Invalida la sesión actual. El cliente debe eliminar el token local."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    return {"ok": True, "mensaje": "Sesión cerrada"}


@router.post(
    "/recuperar-password",
    summary="Solicitar recuperación de contraseña",
)
@rate_limit("3/hour")
async def recuperar_password(body: dict, request: Request):
    """Envía email de recuperación de contraseña via Supabase Auth."""
    email = (body.get("email") or "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Email inválido")
    try:
        supabase.auth.reset_password_email(
            email,
            options={"redirect_to": f"{settings.frontend_url}/reset-password"},
        )
    except Exception as exc:
        logger.error("Supabase reset_password error: %s", exc)
        # Don't reveal if the email exists
    return {
        "ok": True,
        "mensaje": "Si el email está registrado, recibirás un enlace para restablecer tu contraseña.",
    }
