import smtplib
import logging
import httpx
import hashlib
import hmac
import time
from urllib.parse import quote as _url_quote
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

CAT_COLORS_EMAIL: dict[str, str] = {
    "teatro": "#DC2626",
    "hip_hop": "#F59E0B",
    "jazz": "#7C3AED",
    "galeria": "#EC4899",
    "arte_contemporaneo": "#EC4899",
    "libreria": "#10B981",
    "casa_cultura": "#3B82F6",
    "electronica": "#06B6D4",
    "danza": "#F97316",
    "musica_en_vivo": "#06B6D4",
    "batalla_freestyle": "#F59E0B",
    "poesia": "#8B5CF6",
    "festival": "#F97316",
    "cine": "#6B7280",
    "fotografia": "#7C3AED",
    "muralismo": "#F59E0B",
    "filosofia": "#1E40AF",
    "taller": "#059669",
    "circo": "#F97316",
    "rock": "#374151",
    "punk": "#374151",
}


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


# ─── Event data fetching ───────────────────────────────────────────────────────

def _fetch_today_events(municipio: str | None = None, limit: int = 3) -> list[dict]:
    hoy = datetime.now(CO_TZ).date().isoformat()
    manana = (datetime.now(CO_TZ).date() + timedelta(days=1)).isoformat()
    query = (
        supabase.table("eventos")
        .select("titulo,slug,fecha_inicio,hora_confirmada,categoria_principal,nombre_lugar,barrio,municipio,imagen_url,es_gratuito")
        .gte("fecha_inicio", hoy)
        .lt("fecha_inicio", manana)
        .order("fecha_inicio")
        .limit(limit)
    )
    if municipio:
        query = query.ilike("municipio", f"%{municipio}%")
    data = query.execute().data or []
    if not data and municipio:
        data = (
            supabase.table("eventos")
            .select("titulo,slug,fecha_inicio,hora_confirmada,categoria_principal,nombre_lugar,barrio,municipio,imagen_url,es_gratuito")
            .gte("fecha_inicio", hoy)
            .lt("fecha_inicio", manana)
            .order("fecha_inicio")
            .limit(limit)
            .execute()
            .data or []
        )
    return data


def _fetch_weekly_events(
    municipio: str | None,
    categoria: str | None = None,
    limit: int = 8,
    barrio: str | None = None,
) -> list[dict]:
    hoy = datetime.now(CO_TZ).date().isoformat()
    en_7d = (datetime.now(CO_TZ).date() + timedelta(days=7)).isoformat()
    query = (
        supabase.table("eventos")
        .select("titulo,slug,fecha_inicio,hora_confirmada,categoria_principal,nombre_lugar,barrio,municipio,imagen_url")
        .gte("fecha_inicio", hoy)
        .lte("fecha_inicio", en_7d)
        .order("fecha_inicio")
        .limit(limit)
    )
    if barrio:
        query = query.ilike("barrio", f"%{barrio}%")
    if municipio and not barrio:
        query = query.ilike("municipio", f"%{municipio}%")
    if categoria and categoria != "otro":
        query = query.eq("categoria_principal", categoria)

    data = query.execute().data or []
    if not data and categoria and municipio:
        data = (
            supabase.table("eventos")
            .select("titulo,slug,fecha_inicio,hora_confirmada,categoria_principal,nombre_lugar,barrio,municipio,imagen_url")
            .gte("fecha_inicio", hoy)
            .lte("fecha_inicio", en_7d)
            .order("fecha_inicio")
            .limit(limit)
            .ilike("municipio", f"%{municipio}%")
            .execute()
            .data or []
        )
    return data


# ─── Email HTML builders ───────────────────────────────────────────────────────

def _build_event_card_large(evento: dict, frontend_url: str) -> str:
    titulo = escape(evento.get("titulo") or "Evento cultural")
    cat_raw = evento.get("categoria_principal") or "otro"
    categoria = cat_raw.replace("_", " ").upper()
    accent = CAT_COLORS_EMAIL.get(cat_raw, "#555555")
    fecha_raw = str(evento.get("fecha_inicio") or "")
    fecha = fecha_raw[:10]
    hora = ""
    if evento.get("hora_confirmada") and len(fecha_raw) > 10:
        hora = fecha_raw[11:16]
    lugar = escape(
        evento.get("nombre_lugar") or evento.get("barrio") or evento.get("municipio") or VALLE_LABEL
    )
    slug = evento.get("slug") or ""
    imagen_url = evento.get("imagen_url") or ""
    precio = "GRATIS" if evento.get("es_gratuito") else ""

    image_block = (
        f'<img src="{imagen_url}" width="536" style="display:block;width:100%;max-height:240px;border:0;outline:none;object-fit:cover;" alt="{titulo}">'
        if imagen_url
        else f'<div style="height:60px;background-color:{accent}33;"></div>'
    )
    hora_str = f" · {hora}" if hora else ""
    precio_str = f'<span style="background-color:{accent};color:#fff;font-size:8px;font-weight:700;letter-spacing:2px;padding:2px 8px;margin-left:8px;">GRATIS</span>' if precio else ""

    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;border:1px solid #1e1e1e;border-top:3px solid {accent};background-color:#111111;">
  <tr><td style="padding:0;line-height:0;">{image_block}</td></tr>
  <tr><td style="padding:16px;">
    <div style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{accent};margin-bottom:8px;">{categoria}{precio_str}</div>
    <div style="font-size:16px;font-weight:700;color:#ffffff;line-height:1.3;margin-bottom:8px;">{titulo}</div>
    <div style="font-family:'Courier New',Courier,monospace;font-size:10px;color:#666666;margin-bottom:4px;">{fecha}{hora_str}</div>
    <div style="font-family:'Courier New',Courier,monospace;font-size:10px;color:#666666;margin-bottom:14px;">{lugar}</div>
    <a href="{frontend_url}/agenda/{slug}" style="display:inline-block;background-color:{accent};color:#ffffff;text-decoration:none;padding:8px 18px;font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">VER →</a>
  </td></tr>
</table>"""


def _build_event_row_compact(left: dict | None, right: dict | None, frontend_url: str) -> str:
    def _cell(evento: dict | None) -> str:
        if not evento:
            return '<td width="49%" style="padding:0;"></td>'
        titulo = escape(evento.get("titulo") or "Evento")
        cat_raw = evento.get("categoria_principal") or "otro"
        accent = CAT_COLORS_EMAIL.get(cat_raw, "#555555")
        categoria = cat_raw.replace("_", " ").upper()
        fecha_raw = str(evento.get("fecha_inicio") or "")
        fecha = fecha_raw[:10]
        hora = ""
        if evento.get("hora_confirmada") and len(fecha_raw) > 10:
            hora = fecha_raw[11:16]
        lugar = escape(evento.get("nombre_lugar") or evento.get("barrio") or evento.get("municipio") or "")
        slug = evento.get("slug") or ""
        imagen_url = evento.get("imagen_url") or ""
        img = (
            f'<img src="{imagen_url}" width="100%" style="display:block;max-height:120px;object-fit:cover;border:0;" alt="{titulo}">'
            if imagen_url
            else f'<div style="height:40px;background:{accent}22;"></div>'
        )
        hora_str = f" {hora}" if hora else ""
        return f"""<td width="49%" style="vertical-align:top;padding:0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #1e1e1e;border-top:2px solid {accent};background:#111111;">
    <tr><td style="padding:0;line-height:0;">{img}</td></tr>
    <tr><td style="padding:10px;">
      <div style="font-family:'Courier New',monospace;font-size:8px;font-weight:700;color:{accent};letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">{categoria}</div>
      <div style="font-size:12px;font-weight:700;color:#ffffff;line-height:1.3;margin-bottom:6px;">{titulo}</div>
      <div style="font-family:'Courier New',monospace;font-size:9px;color:#666;margin-bottom:2px;">{fecha}{hora_str}</div>
      <div style="font-family:'Courier New',monospace;font-size:9px;color:#555;margin-bottom:10px;">{lugar}</div>
      <a href="{frontend_url}/agenda/{slug}" style="display:inline-block;background:{accent};color:#fff;text-decoration:none;padding:5px 12px;font-family:'Courier New',monospace;font-size:8px;font-weight:700;letter-spacing:1px;">VER →</a>
    </td></tr>
  </table>
</td>"""

    spacer = '<td width="2%" style="padding:0;"></td>'
    return f"""<tr style="vertical-align:top;">
  {_cell(left)}
  {spacer}
  {_cell(right)}
</tr>
<tr><td colspan="3" style="height:12px;padding:0;"></td></tr>"""


def _build_weekly_digest_html(
    nombre: str,
    context_label: str,
    eventos_semana: list[dict],
    eventos_hoy: list[dict] | None = None,
    unsubscribe_url: str = "",
    municipio: str | None = None,
    preferencias: list[str] | None = None,
) -> str:
    frontend_url = settings.frontend_url.rstrip("/")
    now_co = datetime.now(CO_TZ)
    fecha_label = now_co.strftime("%d de %B").lstrip("0").upper()
    context_upper = escape(context_label.upper())

    # HOY section — up to 3 large cards
    hoy_cards = ""
    if eventos_hoy:
        for ev in eventos_hoy[:3]:
            hoy_cards += _build_event_card_large(ev, frontend_url)

    # SEMANA section — pairs of compact cards
    semana_rows = ""
    semana_evs = eventos_semana[:6]
    for i in range(0, len(semana_evs), 2):
        left = semana_evs[i]
        right = semana_evs[i + 1] if i + 1 < len(semana_evs) else None
        semana_rows += _build_event_row_compact(left, right, frontend_url)

    # CERCA DE TI section — events from user's municipio (if different from general)
    cerca_section = ""
    if municipio and municipio.lower() not in ("", "medellin"):
        cerca_evs = _fetch_weekly_events(municipio, limit=4)
        if cerca_evs:
            rows_cerca = ""
            for i in range(0, len(cerca_evs[:4]), 2):
                l = cerca_evs[i]
                r_ev = cerca_evs[i + 1] if i + 1 < len(cerca_evs) else None
                rows_cerca += _build_event_row_compact(l, r_ev, frontend_url)
            muni_label = escape(municipio.replace("_", " ").title())
            cerca_section = f"""
  <tr>
    <td style="padding:8px 32px 8px;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:3px;color:#ffffff;text-transform:uppercase;border-bottom:1px solid #1a1a1a;padding-bottom:10px;margin-bottom:16px;">
        📍 CERCA DE TI · {muni_label}
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">{rows_cerca}</table>
    </td>
  </tr>"""

    # PARA TI section — events matching the user's category preferences
    para_ti_section = ""
    if preferencias:
        pref_evs: list[dict] = []
        seen_slugs: set[str] = {ev.get("slug", "") for ev in eventos_semana}
        for cat in preferencias[:3]:
            cat_evs = _fetch_weekly_events(None, cat, limit=2)
            for ev in cat_evs:
                s = ev.get("slug", "")
                if s not in seen_slugs:
                    pref_evs.append(ev)
                    seen_slugs.add(s)
        if pref_evs:
            rows_pref = ""
            for i in range(0, min(len(pref_evs), 4), 2):
                l = pref_evs[i]
                r_ev = pref_evs[i + 1] if i + 1 < len(pref_evs) else None
                rows_pref += _build_event_row_compact(l, r_ev, frontend_url)
            cats_label = escape(" · ".join(p.replace("_", " ").title() for p in preferencias[:3]))
            para_ti_section = f"""
  <tr>
    <td style="padding:8px 32px 8px;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:3px;color:#ffffff;text-transform:uppercase;border-bottom:1px solid #1a1a1a;padding-bottom:10px;margin-bottom:16px;">
        ⭐ PARA TI · {cats_label}
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">{rows_pref}</table>
    </td>
  </tr>"""

    no_eventos_msg = "" if (hoy_cards or semana_rows) else """
<tr><td style="padding:24px;text-align:center;">
  <p style="color:#666;font-family:'Courier New',monospace;font-size:12px;letter-spacing:1px;">
    AÚN NO HAY EVENTOS CARGADOS PARA ESTA SEMANA.<br>
    LA AGENDA SE ACTUALIZA TODOS LOS DÍAS.
  </p>
</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agenda Cultural — ETÉREA</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0a0a;padding:32px 0;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="background-color:#0a0a0a;max-width:580px;">

  <!-- Header -->
  <tr>
    <td style="background-color:#000000;padding:28px 32px;text-align:center;border-bottom:1px solid #1a1a1a;">
      <h1 style="margin:0;font-family:'Courier New',Courier,monospace;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:4px;text-transform:uppercase;">
        CULTURA ETÉREA
      </h1>
      <p style="margin:6px 0 0;font-family:'Courier New',Courier,monospace;font-size:10px;color:#444444;letter-spacing:3px;text-transform:uppercase;">
        MEDELLÍN · {context_upper}
      </p>
    </td>
  </tr>

  <!-- Date bar -->
  <tr>
    <td style="background-color:#111111;padding:10px 32px;border-bottom:1px solid #1a1a1a;">
      <p style="margin:0;font-family:'Courier New',Courier,monospace;font-size:9px;color:#555555;letter-spacing:2px;text-transform:uppercase;">
        AGENDA · {fecha_label} · SELECCIÓN CULTURAL
      </p>
    </td>
  </tr>

  <!-- Greeting -->
  <tr>
    <td style="padding:24px 32px 8px;">
      <p style="margin:0;font-family:'Courier New',Courier,monospace;font-size:13px;color:#999999;letter-spacing:1px;">
        HOLA, <span style="color:#ffffff;font-weight:700;">{escape(nombre).upper()}</span>
      </p>
      <p style="margin:8px 0 0;font-size:14px;color:#666666;line-height:1.6;">
        Tu radar cultural del Valle de Aburrá. Estos son los eventos que ETÉREA encontró para ti esta semana.
      </p>
    </td>
  </tr>

  <!-- HOY section -->
  {'<tr><td style="padding:24px 32px 8px;"><div style="font-family:Courier New,Courier,monospace;font-size:9px;font-weight:700;letter-spacing:3px;color:#ffffff;text-transform:uppercase;border-bottom:1px solid #1a1a1a;padding-bottom:10px;margin-bottom:16px;">◆ HOY EN EL VALLE</div>' + hoy_cards + '</td></tr>' if hoy_cards else ''}

  <!-- ESTA SEMANA section -->
  <tr>
    <td style="padding:{'8px' if hoy_cards else '24px'} 32px 8px;">
      <div style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:3px;color:#ffffff;text-transform:uppercase;border-bottom:1px solid #1a1a1a;padding-bottom:10px;margin-bottom:16px;">
        ◆ ESTA SEMANA
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {semana_rows}
        {no_eventos_msg}
      </table>
    </td>
  </tr>

  {cerca_section}
  {para_ti_section}

  <!-- CTA -->
  <tr>
    <td style="padding:24px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center">
            <a href="{frontend_url}/agenda"
               style="display:inline-block;background-color:#ffffff;color:#000000;text-decoration:none;padding:14px 36px;font-family:'Courier New',Courier,monospace;font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;">
              VER AGENDA COMPLETA →
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Invite box -->
  <tr>
    <td style="padding:0 32px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#111111;border:1px solid #1e1e1e;border-left:3px solid #ffffff;">
        <tr>
          <td style="padding:20px 24px;">
            <div style="font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:2px;color:#ffffff;text-transform:uppercase;margin-bottom:8px;">
              INVITA A TU COMUNIDAD
            </div>
            <p style="margin:0 0 14px;font-size:13px;color:#888888;line-height:1.6;">
              ¿Conoces artistas, colectivos o espacios que deberían estar en ETÉREA? Comparte la plataforma y hagamos crecer la escena cultural independiente.
            </p>
            <a href="{frontend_url}"
               style="display:inline-block;background-color:transparent;color:#ffffff;text-decoration:none;border:1px solid #333333;padding:8px 20px;font-family:'Courier New',Courier,monospace;font-size:9px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">
              COMPARTIR ETÉREA →
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="padding:20px 32px;border-top:1px solid #1a1a1a;text-align:center;">
      <p style="margin:0;font-family:'Courier New',Courier,monospace;font-size:9px;color:#333333;letter-spacing:2px;text-transform:uppercase;">
        CULTURA ETÉREA · MEDELLÍN · COLOMBIA
      </p>
      <p style="margin:8px 0 0;font-size:10px;color:#333333;">
        Teatro · Hip Hop · Jazz · Galerías · Electrónica · Poesía · Danza · Muralismo
      </p>
      <p style="margin:10px 0 0;font-size:10px;color:#2a2a2a;">
        <a href="{frontend_url}/perfil" style="color:#444444;text-decoration:underline;">Gestionar preferencias</a>
        &nbsp;·&nbsp;
        <a href="{unsubscribe_url}" style="color:#444444;text-decoration:underline;">Darse de baja</a>
      </p>
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
        f"Tu agenda cultural esta semana en {context_label}:",
        "",
    ]
    for evento in eventos:
        lines.append(
            f"- {evento.get('titulo', 'Evento')} | {str(evento.get('fecha_inicio') or '')[:10]} | "
            f"{evento.get('nombre_lugar') or evento.get('barrio') or evento.get('municipio') or VALLE_LABEL}"
        )
    lines.extend([
        "",
        "Ver agenda completa en:",
        f"{settings.frontend_url.rstrip('/')}/agenda",
        "",
        "¿Conoces artistas o espacios culturales? Invítalos a ETÉREA.",
    ])
    return "\n".join(lines)


# ─── Recipient loaders ─────────────────────────────────────────────────────────

def _load_auth_users(limit: int = 2000) -> list[dict]:
    try:
        result = []
        page = 1
        per_page = 100
        while True:
            users = supabase.auth.admin.list_users(page=page, per_page=per_page)
            batch = list(users or [])
            for user in batch:
                email = getattr(user, "email", None) or ""
                email = email.strip().lower()
                if not email:
                    continue
                confirmed = (
                    getattr(user, "email_confirmed_at", None)
                    or getattr(user, "confirmed_at", None)
                )
                if not confirmed:
                    continue
                meta = getattr(user, "user_metadata", None) or {}
                if not isinstance(meta, dict):
                    meta = {}
                nombre = (
                    meta.get("full_name") or meta.get("name")
                    or meta.get("nombre") or email.split("@")[0]
                )
                result.append({
                    "email": email,
                    "nombre": str(nombre),
                    "municipio": str(meta.get("municipio") or "medellin"),
                    "barrio": meta.get("barrio"),
                    "categoria": meta.get("categoria_favorita"),
                    "context_label": str(meta.get("municipio") or VALLE_LABEL),
                })
            if len(batch) < per_page:
                break
            page += 1
            if len(result) >= limit:
                break
        logger.info("Loaded %d auth users across %d pages", len(result), page)
        return result[:limit]
    except Exception as e:
        logger.warning("Could not load auth users: %s", e)
        return []


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
            "barrio": None,
            "categoria": categoria,
            "context_label": perfil.get("municipio") or VALLE_LABEL,
        })
    return recipients


def _load_place_recipients(limit: int) -> list[dict]:
    try:
        lugares = (
            supabase.table("lugares")
            .select("email,nombre,municipio,barrio,categoria_principal,tipo,nivel_actividad")
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
            "barrio": lugar.get("barrio"),
            "categoria": lugar.get("categoria_principal"),
            "context_label": lugar.get("barrio") or lugar.get("municipio") or VALLE_LABEL,
        }
        for lugar in lugares
    ]


# ─── kv helpers ───────────────────────────────────────────────────────────────

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
        logger.warning("Could not persist digest state for key=%s", key)


def _unsub_token(email: str) -> str:
    secret = (settings.scraper_api_key or "eterea-unsub-2026").encode()
    return hmac.new(secret, email.lower().strip().encode(), hashlib.sha256).hexdigest()[:40]


def is_email_unsubscribed(email: str) -> bool:
    key = f"unsub:{hashlib.sha1(email.lower().strip().encode()).hexdigest()[:20]}"
    return _kv_get(key) == "1"


def mark_email_unsubscribed(email: str) -> None:
    key = f"unsub:{hashlib.sha1(email.lower().strip().encode()).hexdigest()[:20]}"
    _kv_upsert(key, "1")


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


def _get_profile_for_email(email: str) -> dict:
    """Fetch user profile (municipio, preferencias) from perfiles table by email."""
    try:
        resp = (
            supabase.table("perfiles_usuario")
            .select("municipio,preferencias")
            .eq("email", email.strip().lower())
            .maybe_single()
            .execute()
        )
        return resp.data or {}
    except Exception:
        return {}


# ─── Weekly digest campaign (Monday drip) ─────────────────────────────────────

def send_weekly_digest_campaign(limit: int = 200, dry_run: bool = False) -> dict:
    recipients: list[dict] = []
    seen: set[str] = set()

    for r in _load_auth_users(500):
        _append_recipient(recipients, seen, r)
    for r in _load_profile_recipients(limit):
        _append_recipient(recipients, seen, r)
    for r in _load_place_recipients(limit):
        _append_recipient(recipients, seen, r)

    recipients = sorted(recipients, key=lambda r: r.get("email", ""))
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
    now_co = datetime.now(CO_TZ)
    if now_co.weekday() != 0 and not dry_run:
        stats["skipped"] = len(recipients)
        stats["reason"] = "Not Monday — digest only sends on Mondays"
        return stats

    start_idx = _get_digest_cursor(week_start)

    for offset in range(len(recipients)):
        idx = (start_idx + offset) % len(recipients)
        r = recipients[idx]
        email = r.get("email") or ""
        if not email or _digest_already_sent(week_start, email) or is_email_unsubscribed(email):
            stats["skipped"] += 1
            continue

        eventos_hoy = _fetch_today_events(r.get("municipio"), limit=3)
        eventos_semana = _fetch_weekly_events(r.get("municipio"), r.get("categoria"), barrio=r.get("barrio"))
        if not eventos_semana:
            eventos_semana = _fetch_weekly_events(None, None, limit=6)

        if not eventos_semana:
            stats["skipped"] += 1
            _set_digest_cursor(week_start, (idx + 1) % len(recipients))
            return stats

        stats["target_email"] = email
        if dry_run:
            stats["sent"] = 1
            return stats

        context_label = r.get("context_label") or VALLE_LABEL
        unsub_url = f"{settings.frontend_url.rstrip('/')}/api/v1/email/unsubscribe?email={_url_quote(email)}&token={_unsub_token(email)}"
        profile = _get_profile_for_email(email)
        user_muni = profile.get("municipio") or r.get("municipio")
        user_prefs = profile.get("preferencias") or []
        html = _build_weekly_digest_html(
            r["nombre"], context_label, eventos_semana, eventos_hoy,
            unsubscribe_url=unsub_url, municipio=user_muni, preferencias=user_prefs or None,
        )
        text = _build_weekly_digest_text(r["nombre"], context_label, eventos_semana)
        subject = f"Tu agenda cultural esta semana — ETÉREA"

        if _send_email(email, subject, html, text):
            _mark_digest_sent(week_start, email)
            stats["sent"] = 1
        else:
            stats["failed"] = 1

        _set_digest_cursor(week_start, (idx + 1) % len(recipients))
        return stats

    stats["skipped"] = len(recipients)
    return stats


# ─── Blast campaign (immediate test — any day) ────────────────────────────────

def send_blast_campaign_tick() -> dict:
    BLAST_KEY = "blast:2026-05c"  # bumped to restart blast

    recipients: list[dict] = []
    seen: set[str] = set()
    for r in _load_auth_users(500):
        _append_recipient(recipients, seen, r)
    for r in _load_profile_recipients(300):
        _append_recipient(recipients, seen, r)
    for r in _load_place_recipients(200):
        _append_recipient(recipients, seen, r)

    recipients.sort(key=lambda r: r.get("email", ""))
    stats = {
        "recipients": len(recipients),
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "target_email": None,
        "blast_key": BLAST_KEY,
    }

    if not recipients:
        return stats

    raw_cursor = _kv_get(f"cursor:{BLAST_KEY}")
    start_idx = max(int(raw_cursor or "0"), 0)

    for offset in range(len(recipients)):
        idx = (start_idx + offset) % len(recipients)
        r = recipients[idx]
        email = (r.get("email") or "").strip().lower()
        if not email:
            stats["skipped"] += 1
            continue

        ehash = hashlib.sha1(email.encode()).hexdigest()[:20]
        sent_key = f"sent:{BLAST_KEY}:{ehash}"
        if _kv_get(sent_key) == "1" or is_email_unsubscribed(email):
            stats["skipped"] += 1
            continue

        eventos_hoy = _fetch_today_events(r.get("municipio"), limit=3)
        eventos_semana = _fetch_weekly_events(r.get("municipio"), r.get("categoria"), limit=8, barrio=r.get("barrio"))
        if not eventos_semana:
            eventos_semana = _fetch_weekly_events(None, None, limit=6)

        context_label = r.get("context_label") or VALLE_LABEL
        stats["target_email"] = email
        unsub_url = f"{settings.frontend_url.rstrip('/')}/api/v1/email/unsubscribe?email={_url_quote(email)}&token={_unsub_token(email)}"
        profile = _get_profile_for_email(email)
        user_muni = profile.get("municipio") or r.get("municipio")
        user_prefs = profile.get("preferencias") or []
        html = _build_weekly_digest_html(
            r["nombre"], context_label, eventos_semana, eventos_hoy,
            unsubscribe_url=unsub_url, municipio=user_muni, preferencias=user_prefs or None,
        )
        text = _build_weekly_digest_text(r["nombre"], context_label, eventos_semana)

        if _send_email(email, "Tu agenda cultural esta semana — ETÉREA", html, text):
            _kv_upsert(sent_key, "1")
            stats["sent"] = 1
        else:
            stats["failed"] = 1

        _kv_upsert(f"cursor:{BLAST_KEY}", str((idx + 1) % len(recipients)))
        return stats

    stats["skipped"] = len(recipients)
    return stats


# ─── Blast ALL (send to every pending recipient in one call) ──────────────────

def send_blast_all() -> dict:
    """Send to every unsent recipient in one HTTP call. Use for test blasts."""
    BLAST_KEY = "blast:2026-05"

    recipients: list[dict] = []
    seen: set[str] = set()
    for r in _load_auth_users(500):
        _append_recipient(recipients, seen, r)
    for r in _load_profile_recipients(300):
        _append_recipient(recipients, seen, r)
    for r in _load_place_recipients(200):
        _append_recipient(recipients, seen, r)

    recipients.sort(key=lambda r: r.get("email", ""))
    stats = {
        "recipients": len(recipients),
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "blast_key": BLAST_KEY,
        "emails_sent": [],
    }

    for r in recipients:
        email = (r.get("email") or "").strip().lower()
        if not email:
            stats["skipped"] += 1
            continue

        ehash = hashlib.sha1(email.encode()).hexdigest()[:20]
        sent_key = f"sent:{BLAST_KEY}:{ehash}"
        if _kv_get(sent_key) == "1" or is_email_unsubscribed(email):
            stats["skipped"] += 1
            continue

        eventos_hoy = _fetch_today_events(r.get("municipio"), limit=3)
        eventos_semana = _fetch_weekly_events(r.get("municipio"), r.get("categoria"), limit=8, barrio=r.get("barrio"))
        if not eventos_semana:
            eventos_semana = _fetch_weekly_events(None, None, limit=6)

        context_label = r.get("context_label") or VALLE_LABEL
        unsub_url = f"{settings.frontend_url.rstrip('/')}/api/v1/email/unsubscribe?email={_url_quote(email)}&token={_unsub_token(email)}"
        html = _build_weekly_digest_html(r["nombre"], context_label, eventos_semana, eventos_hoy, unsubscribe_url=unsub_url)
        text = _build_weekly_digest_text(r["nombre"], context_label, eventos_semana)

        if _send_email(email, "Tu agenda cultural esta semana — ETÉREA", html, text):
            _kv_upsert(sent_key, "1")
            stats["sent"] += 1
            stats["emails_sent"].append(email)
            logger.info("Blast sent to %s", email)
        else:
            stats["failed"] += 1
            logger.warning("Blast failed for %s", email)

        time.sleep(8)  # 8s between sends — avoids Gmail rate limits (~7/min)

    return stats


# ─── Scraper alert emails ──────────────────────────────────────────────────────

def send_scraper_alert(job_name: str, error: str, consecutive_failures: int) -> bool:
    alert_email = settings.smtp_from_email or settings.smtp_user
    if not alert_email:
        return False

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
