import smtplib
import logging
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

logger = logging.getLogger(__name__)


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
    # Try Resend first (simpler setup, no SMTP needed)
    if settings.resend_api_key:
        return _send_via_resend(to_email, user_name)

    # Fall back to SMTP
    if not settings.smtp_password:
        logger.warning(
            "Email not configured. Set RESEND_API_KEY (recommended) or "
            "SMTP_PASSWORD + SMTP_USER + SMTP_FROM_EMAIL to enable welcome emails."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Bienvenido a Cultura ETÉREA — Medellín"
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email

    text_part = MIMEText(
        f"¡Bienvenido a Cultura ETÉREA!\n\n"
        f"Tu registro fue exitoso. Ahora eres parte de la red cultural del Valle de Aburrá.\n\n"
        f"Explora: {settings.frontend_url}/explorar\n",
        "plain",
        "utf-8",
    )
    html_part = MIMEText(_build_welcome_html(to_email, user_name), "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        logger.info(
            "Attempting SMTP connection: host=%s, port=%s, user=%s, from=%s, to=%s",
            settings.smtp_host, settings.smtp_port, settings.smtp_user,
            settings.smtp_from_email, to_email,
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Welcome email sent to %s via SMTP", to_email)
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


def _send_via_resend(to_email: str, user_name: str | None = None) -> bool:
    """Send welcome email using Resend HTTP API (https://resend.com)."""
    try:
        from_addr = settings.smtp_from_email or "noreply@culturaeterea.com"
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{settings.smtp_from_name} <{from_addr}>",
                "to": [to_email],
                "subject": "Bienvenido a Cultura ETÉREA — Medellín",
                "html": _build_welcome_html(to_email, user_name),
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("Welcome email sent to %s via Resend", to_email)
            return True
        logger.error("Resend API error (%s): %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Failed to send email to %s via Resend: %s", to_email, e)
        return False


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
