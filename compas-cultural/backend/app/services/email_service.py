import smtplib
import logging
import httpx
import hashlib
from datetime import datetime, timedelta
from html import escape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from app.database import supabase
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
CO_TZ = ZoneInfo("America/Bogota")
VALLE_LABEL = "Valle de Aburrá"


def _build_welcome_html(user_email: str, user_name: str | None = None) -> str:
    nombre = user_name or user_email.split("@")[0]
    frontend_url = settings.frontend_url.rstrip("/")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bienvenido a Cultura ETÉREA</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border:1px solid #e5e5e5;">

  <!-- Header -->
  <tr>
    <td style="background-color:#0a0a0a;padding:32px 40px;text-align:center;">
      <h1 style="margin:0;font-family:'Courier New',monospace;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:2px;">
        CULTURA ETÉREA
      </h1>
      <p style="margin:4px 0 0;font-family:'Courier New',monospace;font-size:11px;color:#999;letter-spacing:1px;">
        MEDELLÍN · VALLE DE ABURRÁ
      </p>
    </td>
  </tr>

  <!-- Dot divider -->
  <tr>
    <td style="padding:0 40px;">
      <div style="border-top:2px dotted #e5e5e5;margin:0;"></div>
    </td>
  </tr>

  <!-- Body -->
  <tr>
    <td style="padding:40px;">
      <h2 style="margin:0 0 16px;font-family:'Courier New',monospace;font-size:18px;font-weight:700;color:#0a0a0a;text-transform:uppercase;letter-spacing:1px;">
        ¡Bienvenido, {nombre}!
      </h2>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#333;">
        Tu registro en <strong>Cultura ETÉREA</strong> fue exitoso. Ahora eres parte de la red
        que mapea y conecta la escena cultural independiente del Valle de Aburrá.
      </p>

      <!-- Feature boxes -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
        <tr>
          <td width="33%" style="padding:0 8px 0 0;vertical-align:top;">
            <div style="border:1px solid #e5e5e5;padding:16px;text-align:center;">
              <div style="font-size:24px;margin-bottom:8px;">◉</div>
              <div style="font-family:'Courier New',monospace;font-size:10px;font-weight:700;letter-spacing:1px;color:#0a0a0a;text-transform:uppercase;">MAPA</div>
              <p style="font-size:11px;color:#666;margin:4px 0 0;line-height:1.4;">96+ espacios culturales geolocalizados</p>
            </div>
          </td>
          <td width="33%" style="padding:0 4px;vertical-align:top;">
            <div style="border:1px solid #e5e5e5;padding:16px;text-align:center;">
              <div style="font-size:24px;margin-bottom:8px;">▣</div>
              <div style="font-family:'Courier New',monospace;font-size:10px;font-weight:700;letter-spacing:1px;color:#0a0a0a;text-transform:uppercase;">AGENDA</div>
              <p style="font-size:11px;color:#666;margin:4px 0 0;line-height:1.4;">Eventos de teatro, jazz, hip hop y más</p>
            </div>
          </td>
          <td width="33%" style="padding:0 0 0 8px;vertical-align:top;">
            <div style="border:1px solid #e5e5e5;padding:16px;text-align:center;">
              <div style="font-size:24px;margin-bottom:8px;">◈</div>
              <div style="font-family:'Courier New',monospace;font-size:10px;font-weight:700;letter-spacing:1px;color:#0a0a0a;text-transform:uppercase;">CHAT IA</div>
              <p style="font-size:11px;color:#666;margin:4px 0 0;line-height:1.4;">Asistente cultural con inteligencia artificial</p>
            </div>
          </td>
        </tr>
      </table>

      <!-- CTA -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:32px 0 24px;">
        <tr>
          <td align="center">
            <a href="{frontend_url}/explorar"
               style="display:inline-block;background-color:#0a0a0a;color:#ffffff;font-family:'Courier New',monospace;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;text-decoration:none;padding:14px 32px;border:none;">
              EXPLORAR AHORA →
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:0;font-size:13px;line-height:1.6;color:#999;">
        Si no creaste esta cuenta, puedes ignorar este correo.
      </p>
    </td>
  </tr>

  <!-- Dot divider -->
  <tr>
    <td style="padding:0 40px;">
      <div style="border-top:2px dotted #e5e5e5;margin:0;"></div>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="padding:24px 40px;text-align:center;">
      <p style="margin:0;font-family:'Courier New',monospace;font-size:10px;color:#999;letter-spacing:1px;">
        CULTURA ETÉREA · MEDELLÍN · VALLE DE ABURRÁ
      </p>
      <p style="margin:8px 0 0;font-size:11px;color:#bbb;">
        Teatro · Hip Hop · Jazz · Galerías · Electrónica · Poesía · Danza
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_welcome_email(to_email: str, user_name: str | None = None) -> bool:
  text = (
    "¡Bienvenido a Cultura ETÉREA!\n\n"
    "Tu registro fue exitoso. Ahora eres parte de la red cultural del Valle de Aburrá.\n\n"
    f"Explora: {settings.frontend_url}/explorar\n"
  )
  return _send_email(
    to_email=to_email,
    subject="Bienvenido a Cultura ETÉREA — Medellín",
    html=_build_welcome_html(to_email, user_name),
    text=text,
  )


def _deliver_via_smtp(to_email: str, subject: str, html: str, text: str) -> bool:
  if not settings.smtp_password:
    logger.warning(
      "Email not configured. Set RESEND_API_KEY (recommended) or "
      "SMTP_PASSWORD + SMTP_USER + SMTP_FROM_EMAIL to enable emails."
    )
    return False

  from_email = settings.smtp_from_email or settings.smtp_user
  msg = MIMEMultipart("alternative")
  msg["Subject"] = subject
  msg["From"] = f"{settings.smtp_from_name} <{from_email}>"
  msg["To"] = to_email
  msg.attach(MIMEText(text, "plain", "utf-8"))
  msg.attach(MIMEText(html, "html", "utf-8"))

  try:
    logger.info(
      "Attempting SMTP connection: host=%s, port=%s, user=%s, from=%s, to=%s",
      settings.smtp_host, settings.smtp_port, settings.smtp_user,
      from_email, to_email,
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
      server.starttls()
      server.login(settings.smtp_user, settings.smtp_password)
      server.send_message(msg)
    logger.info("Email sent to %s via SMTP", to_email)
    return True
  except smtplib.SMTPAuthenticationError as e:
    logger.error("SMTP auth failed for %s: %s (check App Password)", settings.smtp_user, e)
    return False
  except smtplib.SMTPConnectError as e:
    logger.error("SMTP connection failed to %s:%s: %s", settings.smtp_host, settings.smtp_port, e)
    return False
  except Exception as e:
    logger.error("Failed to send email to %s via SMTP: %s (%s)", to_email, type(e).__name__, e)
    return False


def _send_email(to_email: str, subject: str, html: str, text: str) -> bool:
  if settings.resend_api_key:
    return _send_via_resend(to_email, subject, html)
  return _deliver_via_smtp(to_email, subject, html, text)


def _send_via_resend(to_email: str, subject: str, html: str) -> bool:
    """Send email using Resend HTTP API (https://resend.com)."""
    try:
        from_addr = settings.smtp_from_email or settings.smtp_user or "noreply@culturaeterea.com"
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{settings.smtp_from_name} <{from_addr}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("Email sent to %s via Resend", to_email)
            return True
        logger.error("Resend API error (%s): %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Failed to send email to %s via Resend: %s", to_email, e)
        return False


def _build_weekly_digest_html(nombre: str, context_label: str, eventos: list[dict]) -> str:
    frontend_url = settings.frontend_url.rstrip("/")
    cards = []
    for evento in eventos:
        fecha = escape(str(evento.get("fecha_inicio") or "")[:10])
        titulo = escape(evento.get("titulo") or "Evento cultural")
        categoria = escape((evento.get("categoria_principal") or "cultural").replace("_", " "))
        lugar = escape(evento.get("nombre_lugar") or evento.get("barrio") or evento.get("municipio") or VALLE_LABEL)
        slug = escape(evento.get("slug") or "")
        cards.append(
            f"""
            <tr>
              <td style="padding:16px;border:1px solid #e5e5e5;vertical-align:top;">
                <div style="font-family:'Courier New',monospace;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#666;margin-bottom:8px;">{categoria}</div>
                <div style="font-size:17px;font-weight:700;color:#0a0a0a;line-height:1.3;margin-bottom:8px;">{titulo}</div>
                <div style="font-family:'Courier New',monospace;font-size:11px;color:#444;margin-bottom:4px;">{fecha}</div>
                <div style="font-family:'Courier New',monospace;font-size:11px;color:#444;margin-bottom:12px;">{lugar}</div>
                <a href=\"{frontend_url}/evento/{slug}\" style="display:inline-block;background:#0a0a0a;color:#fff;text-decoration:none;padding:10px 16px;font-family:'Courier New',monospace;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">Ver tarjeta</a>
              </td>
            </tr>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Agenda semanal</title></head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;padding:40px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border:1px solid #e5e5e5;">
  <tr>
    <td style="background-color:#0a0a0a;padding:32px 40px;text-align:center;">
      <h1 style="margin:0;font-family:'Courier New',monospace;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:2px;">CULTURA ETÉREA</h1>
      <p style="margin:6px 0 0;font-family:'Courier New',monospace;font-size:11px;color:#999;letter-spacing:1px;">AGENDA SEMANAL · {escape(context_label.upper())}</p>
    </td>
  </tr>
  <tr>
    <td style="padding:32px 40px;">
      <h2 style="margin:0 0 12px;font-family:'Courier New',monospace;font-size:18px;font-weight:700;color:#0a0a0a;text-transform:uppercase;letter-spacing:1px;">Hola, {escape(nombre)}</h2>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#333;">Estos son algunos eventos de la próxima semana que ETÉREA encontró para <strong>{escape(context_label)}</strong>.</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.6;color:#333;">Entra a la app para descubrir más espacios, mapa cultural y agenda completa en tiempo real.</p>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        {''.join(cards)}
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;">
        <tr><td align="center"><a href=\"{frontend_url}/agenda\" style="display:inline-block;background:#0a0a0a;color:#fff;text-decoration:none;padding:14px 28px;font-family:'Courier New',monospace;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Abrir agenda completa</a></td></tr>
      </table>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _build_weekly_digest_text(nombre: str, context_label: str, eventos: list[dict]) -> str:
    lines = [
        f"Hola, {nombre}.",
        "",
        f"Estos son algunos eventos de la próxima semana para {context_label}:",
        "",
    ]
    for evento in eventos:
        lines.append(
            f"- {evento.get('titulo', 'Evento')} | {str(evento.get('fecha_inicio') or '')[:10]} | "
          f"{evento.get('nombre_lugar') or evento.get('barrio') or evento.get('municipio') or VALLE_LABEL}"
        )
    lines.extend([
      "",
      "Entra a la app y mira toda la agenda cultural en vivo:",
      f"Agenda completa: {settings.frontend_url.rstrip('/')}/agenda",
    ])
    return "\n".join(lines)


def _week_start_iso(now: datetime | None = None) -> str:
    base = now or datetime.now(CO_TZ)
    monday = base.date() - timedelta(days=base.weekday())
    return monday.isoformat()


def _kv_get(key: str) -> str | None:
    try:
        resp = supabase.table("config_kv").select("value").eq("key", key).single().execute()
        data = resp.data or {}
        value = data.get("value")
        return str(value) if value is not None else None
    except Exception:
        return None


def _kv_upsert(key: str, value: str) -> None:
    try:
        supabase.table("config_kv").upsert(
            {
                "key": key,
                "value": value,
                "updated_at": datetime.now(CO_TZ).isoformat(),
            },
            on_conflict="key",
        ).execute()
    except Exception:
        # Nunca bloquea el envio por fallo de estado.
        logger.warning("Could not persist digest state for key=%s", key)


def _digest_marker_key(week_start_iso: str, email: str) -> str:
    email_hash = hashlib.sha1(email.encode("utf-8")).hexdigest()[:20]
    return f"weekly_digest_sent:{week_start_iso}:{email_hash}"


def _digest_already_sent(week_start_iso: str, email: str) -> bool:
    return _kv_get(_digest_marker_key(week_start_iso, email)) == "1"


def _mark_digest_sent(week_start_iso: str, email: str) -> None:
    _kv_upsert(_digest_marker_key(week_start_iso, email), "1")


def _digest_cursor_key(week_start_iso: str) -> str:
    return f"weekly_digest_cursor:{week_start_iso}"


def _get_digest_cursor(week_start_iso: str) -> int:
    raw = _kv_get(_digest_cursor_key(week_start_iso))
    try:
        return max(int(raw or "0"), 0)
    except Exception:
        return 0


def _set_digest_cursor(week_start_iso: str, idx: int) -> None:
    _kv_upsert(_digest_cursor_key(week_start_iso), str(max(idx, 0)))


def _fetch_weekly_events(municipio: str | None, categoria: str | None = None, limit: int = 8) -> list[dict]:
    hoy = datetime.now(CO_TZ).date().isoformat()
    en_7d = (datetime.now(CO_TZ).date() + timedelta(days=7)).isoformat()
    query = (
        supabase.table("eventos")
        .select("titulo,slug,fecha_inicio,categoria_principal,nombre_lugar,barrio,municipio")
        .gte("fecha_inicio", hoy)
        .lte("fecha_inicio", en_7d)
        .order("fecha_inicio")
        .limit(limit)
    )
    if municipio:
        query = query.ilike("municipio", f"%{municipio}%")
    if categoria and categoria != "otro":
        query = query.eq("categoria_principal", categoria)

    data = query.execute().data or []
    if not data and categoria and municipio:
        data = (
            supabase.table("eventos")
            .select("titulo,slug,fecha_inicio,categoria_principal,nombre_lugar,barrio,municipio")
            .gte("fecha_inicio", hoy)
            .lte("fecha_inicio", en_7d)
            .order("fecha_inicio")
            .limit(limit)
            .ilike("municipio", f"%{municipio}%")
            .execute()
            .data or []
        )
    return data


def _append_recipient(recipients: list[dict], seen: set[str], recipient: dict) -> None:
    email = (recipient.get("email") or "").strip().lower()
    if not email or email in seen:
        return
    seen.add(email)
    recipients.append({**recipient, "email": email})


def _load_profile_recipients(limit: int) -> list[dict]:
    try:
        perfiles = (
            supabase.table("perfiles_usuario")
            .select("email,nombre,municipio,preferencias")
            .not_.is_("email", "null")
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []

    recipients = []
    for perfil in perfiles:
        preferencias = perfil.get("preferencias") or []
        categoria = preferencias[0] if isinstance(preferencias, list) and preferencias else None
        recipients.append({
            "email": perfil.get("email"),
            "nombre": perfil.get("nombre") or str(perfil.get("email") or "usuario").split("@")[0],
            "municipio": perfil.get("municipio") or "medellin",
            "categoria": categoria,
            "context_label": perfil.get("municipio") or VALLE_LABEL,
        })
    return recipients


def _load_place_recipients(limit: int) -> list[dict]:
    try:
        lugares = (
            supabase.table("lugares")
            .select("email,nombre,municipio,categoria_principal,tipo,nivel_actividad")
            .not_.is_("email", "null")
            .neq("nivel_actividad", "cerrado")
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception:
        return []

    return [
        {
            "email": lugar.get("email"),
            "nombre": lugar.get("nombre") or str(lugar.get("email") or "espacio").split("@")[0],
            "municipio": lugar.get("municipio") or "medellin",
            "categoria": lugar.get("categoria_principal"),
            "context_label": lugar.get("nombre") or lugar.get("municipio") or VALLE_LABEL,
        }
        for lugar in lugares
    ]


def send_weekly_digest_campaign(limit: int = 200, dry_run: bool = False) -> dict:
    recipients: list[dict] = []
    seen: set[str] = set()

    for recipient in _load_profile_recipients(limit):
        _append_recipient(recipients, seen, recipient)

    for recipient in _load_place_recipients(limit):
        _append_recipient(recipients, seen, recipient)

    recipients = sorted(recipients[:limit], key=lambda r: r.get("email", ""))
    stats = {
      "recipients": len(recipients),
      "sent": 0,
      "skipped": 0,
      "failed": 0,
      "tick_limit": 1,
      "target_email": None,
      "week_start": _week_start_iso(),
    }

    if not recipients:
      return stats

    week_start = stats["week_start"]
    start_idx = _get_digest_cursor(week_start)

    for offset in range(len(recipients)):
      idx = (start_idx + offset) % len(recipients)
      recipient = recipients[idx]
      email = recipient.get("email") or ""
      if not email or _digest_already_sent(week_start, email):
        stats["skipped"] += 1
        continue

      eventos = _fetch_weekly_events(recipient.get("municipio"), recipient.get("categoria"))
      if not eventos:
        eventos = _fetch_weekly_events(None, None, limit=6)
      if not eventos:
        stats["skipped"] += 1
        _set_digest_cursor(week_start, (idx + 1) % len(recipients))
        return stats

      stats["target_email"] = email
      if dry_run:
        stats["sent"] = 1
        return stats

      subject = f"Tu semana cultural en {recipient.get('municipio') or 'el Valle de Aburrá'}"
      html = _build_weekly_digest_html(recipient["nombre"], recipient["context_label"], eventos)
      text = _build_weekly_digest_text(recipient["nombre"], recipient["context_label"], eventos)
      if _send_email(email, subject, html, text):
        _mark_digest_sent(week_start, email)
        stats["sent"] = 1
      else:
        stats["failed"] = 1

      _set_digest_cursor(week_start, (idx + 1) % len(recipients))
      return stats

    stats["skipped"] = len(recipients)
    return stats


# ─── Scraper alert emails ──────────────────────────────────────────────────────

def send_scraper_alert(job_name: str, error: str, consecutive_failures: int) -> bool:
    """
    Envía alerta por email cuando un job del scheduler falla repetidamente.
    Usa Resend si está configurado, si no SMTP. Si ninguno, retorna False silenciosamente.
    """
    alert_email = settings.smtp_from_email or settings.smtp_user
    if not alert_email:
        return False  # Sin email configurado, no hay a quién alertar

    subject = f"[CULTURA ETÉREA] Alerta: {job_name} falló {consecutive_failures}x"
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="font-family:monospace;background:#f5f5f5;padding:40px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:2px solid #000;padding:32px;">
  <h1 style="font-size:16px;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px;">
    ⚠ ALERTA DE SCRAPER
  </h1>
  <p style="font-size:11px;color:#666;margin-bottom:24px;letter-spacing:1px;">CULTURA ETÉREA · SISTEMA DE MONITOREO</p>

  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="border-bottom:1px solid #e5e5e5;">
      <td style="padding:8px 0;color:#666;width:40%;">Job</td>
      <td style="padding:8px 0;font-weight:bold;">{job_name}</td>
    </tr>
    <tr style="border-bottom:1px solid #e5e5e5;">
      <td style="padding:8px 0;color:#666;">Fallos consecutivos</td>
      <td style="padding:8px 0;font-weight:bold;color:#cc0000;">{consecutive_failures}</td>
    </tr>
    <tr style="border-bottom:1px solid #e5e5e5;">
      <td style="padding:8px 0;color:#666;">Último error</td>
      <td style="padding:8px 0;font-family:monospace;font-size:11px;word-break:break-all;">{error[:300]}</td>
    </tr>
    <tr>
      <td style="padding:8px 0;color:#666;">Hora (UTC)</td>
      <td style="padding:8px 0;">{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</td>
    </tr>
  </table>

  <div style="margin-top:24px;padding:16px;background:#fff3f3;border:1px solid #ffcccc;">
    <p style="margin:0;font-size:12px;color:#cc0000;">
      El job <strong>{job_name}</strong> ha fallado {consecutive_failures} veces consecutivas.
      Revisa los logs en Railway o en <code>/health/status</code>.
    </p>
  </div>
</div>
</body>
</html>"""

    try:
        if settings.resend_api_key:
            from_addr = alert_email
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"Cultura ETÉREA Alerta <{from_addr}>",
                    "to": [alert_email],
                    "subject": subject,
                    "html": html,
                },
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logger.info("Scraper alert sent for %s (failures=%d)", job_name, consecutive_failures)
                return True
            logger.error("Resend alert error (%s): %s", resp.status_code, resp.text)
            return False

        elif settings.smtp_user and settings.smtp_password:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email or settings.smtp_user}>"
            msg["To"] = alert_email
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(msg["From"], [alert_email], msg.as_string())
            return True

    except Exception as e:
        logger.error("Failed to send scraper alert: %s", e)

    return False
