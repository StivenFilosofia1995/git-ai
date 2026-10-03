from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Annotated

router = APIRouter()


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_email(email: str = Query(...), token: str = Query(...)):
    """Procesaa el link de baja de emails. Devuelve página HTML de confirmación."""
    from app.services.email_service import _unsub_token, mark_email_unsubscribed, is_email_unsubscribed
    # Validate token to prevent arbitrary unsubscribes
    if token != _unsub_token(email):
        return HTMLResponse(
            content=_unsub_page("Token inválido", "El enlace de baja no es válido o ya expiró.", error=True),
            status_code=400,
        )
    if is_email_unsubscribed(email):
        return HTMLResponse(content=_unsub_page("Ya dado de baja", f"{email} ya no recibe emails de ETÉREA."))
    mark_email_unsubscribed(email)
    return HTMLResponse(content=_unsub_page("Listo", f"Te diste de baja exitosamente. {email} no recibirá más emails de Cultura ETÉREA."))


def _unsub_page(title: str, message: str, error: bool = False) -> str:
    color = "#DC2626" if error else "#16a34a"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Cultura ETÉREA</title>
</head>
<body style="margin:0;padding:40px 16px;background:#f5f5f5;font-family:'Helvetica Neue',Arial,sans-serif;text-align:center;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border:2px solid #0a0a0a;padding:48px 32px;">
    <p style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#999;margin:0 0 24px;">CULTURA ETÉREA</p>
    <h1 style="font-size:28px;font-weight:900;text-transform:uppercase;letter-spacing:1px;color:{color};margin:0 0 16px;">{title}</h1>
    <p style="font-size:14px;color:#444;line-height:1.6;margin:0 0 32px;">{message}</p>
    <a href="https://culturaetereamed.com" style="display:inline-block;background:#0a0a0a;color:#fff;text-decoration:none;padding:12px 28px;font-family:'Courier New',monospace;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">IR A LA AGENDA →</a>
  </div>
</body>
</html>"""


@router.post("/blast-now")
def trigger_blast_now(api_key: Annotated[str, Query()] = ""):
    """Sends one email to the next unsent user in the blast campaign."""
    from app.config import settings
    from app.security import require_admin_key
    require_admin_key(api_key)
    from app.services.email_service import send_blast_campaign_tick
    stats = send_blast_campaign_tick()
    return stats


@router.post("/blast-all")
def trigger_blast_all(api_key: Annotated[str, Query()] = ""):
    """Sends to ALL pending users in one call. Returns total sent/skipped/failed."""
    from app.config import settings
    from app.security import require_admin_key
    require_admin_key(api_key)
    from app.services.email_service import send_blast_all
    stats = send_blast_all()
    return stats


@router.get("/estado")
def estado_boletin(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Estado del boletín semanal: remitente, destinatarios y enviados esta semana (admin)."""
    from app.security import require_admin_key
    require_admin_key(x_api_key)
    from app.services.email_service import (
        cargar_destinatarios, remitente_listo, _digest_already_sent, _week_start_iso, is_email_unsubscribed,
    )
    listo, motivo = remitente_listo()
    semana = _week_start_iso()
    dest = cargar_destinatarios()
    enviados = sum(1 for r in dest if _digest_already_sent(semana, r["email"]))
    bajas = sum(1 for r in dest if is_email_unsubscribed(r["email"]))
    return {"remitente_listo": listo, "remitente": motivo, "semana": semana,
            "destinatarios": len(dest), "enviados_esta_semana": enviados, "dados_de_baja": bajas}


@router.post("/prueba")
def enviar_prueba(
    para: str = Query(..., description="Correo que recibirá la vista previa"),
    campana: str = Query("semanal", pattern="^(semanal|finde)$"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Envía el boletín de esta semana a un solo correo (sin marcarlo como enviado)."""
    from app.security import require_admin_key
    require_admin_key(x_api_key)
    from app.services import email_service as es
    listo, motivo = es.remitente_listo()
    r = {"email": para.strip().lower(), "nombre": para.split("@")[0], "municipio": None,
         "barrio": None, "categoria": None, "context_label": es.VALLE_LABEL}
    original = es._mark_digest_sent
    es._mark_digest_sent = lambda *_a, **_k: None  # la prueba no consume el envío real
    try:
        semana = "prueba-" + es._week_start_iso()
        resultado = es.enviar_digest_a(r, semana, campana)
    finally:
        es._mark_digest_sent = original
    return {"resultado": resultado, "campana": campana, "remitente_listo": listo, "remitente": motivo,
            "ultimo_error": dict(es.ULTIMO_ERROR)}


@router.get("/blast-status")
def get_blast_status(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Returns cursor position and recipient count for the blast campaign (admin)."""
    from app.security import require_admin_key
    require_admin_key(x_api_key)
    from app.services.email_service import (
        _load_auth_users, _load_profile_recipients, _load_place_recipients,
        _append_recipient, _kv_get,
    )
    BLAST_KEY = "blast:2026-05b"
    cursor = _kv_get(f"cursor:{BLAST_KEY}") or "0"

    recipients: list[dict] = []
    seen: set[str] = set()
    for r in _load_auth_users(500):
        _append_recipient(recipients, seen, r)
    for r in _load_profile_recipients(300):
        _append_recipient(recipients, seen, r)
    for r in _load_place_recipients(200):
        _append_recipient(recipients, seen, r)

    return {
        "blast_key": BLAST_KEY,
        "cursor": int(cursor),
        "total_recipients": len(recipients),
    }
