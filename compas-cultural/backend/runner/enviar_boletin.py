"""
Envía el boletín semanal a los usuarios REGISTRADOS desde tu PC (Gmail SMTP).

Por qué desde el PC: Railway bloquea el SMTP en planes que no son Pro, y Resend sin
dominio verificado solo entrega al dueño de la cuenta. Tu red sí puede usar Gmail.

Uso:
  python -m runner.enviar_boletin --prueba tu@correo.com   (solo a ti, no marca nada)
  python -m runner.enviar_boletin                          (a todos los pendientes de esta semana)

Requiere en compas-cultural/backend/.env:
  SUPABASE_URL, SUPABASE_KEY (service role), SMTP_USER, SMTP_PASSWORD (contraseña de
  aplicación de Gmail: myaccount.google.com/apppasswords), SMTP_FROM_NAME (opcional).
Cada destinatario queda marcado por semana: nunca recibe dos veces el mismo boletín
(ni desde el PC ni desde el servidor).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except Exception:
    pass

LIMITE_GMAIL_DIA = 450  # Gmail permite ~500/día; se deja margen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", help="Enviar solo a este correo (no marca a nadie como enviado)")
    ap.add_argument("--si", action="store_true", help="No pedir confirmación")
    args = ap.parse_args()

    from app.config import settings
    if not (settings.smtp_user and settings.smtp_password):
        sys.exit("❌ Falta SMTP_USER / SMTP_PASSWORD en compas-cultural/backend/.env")
    # En el PC se envía por Gmail aunque haya RESEND_API_KEY con remitente de prueba
    if (settings.smtp_from_email or "").lower().endswith("@resend.dev"):
        settings.smtp_from_email = settings.smtp_user
    from app.services import email_service as es

    if args.prueba:
        r = {"email": args.prueba.strip().lower(), "nombre": args.prueba.split("@")[0], "municipio": None,
             "barrio": None, "categoria": None, "context_label": es.VALLE_LABEL}
        original = es._mark_digest_sent
        es._mark_digest_sent = lambda *_a, **_k: None
        try:
            print("Resultado:", es.enviar_digest_a(r, "prueba-" + es._week_start_iso()))
        finally:
            es._mark_digest_sent = original
        return

    semana = es._week_start_iso()
    destinatarios = es.cargar_destinatarios()
    pendientes = [d for d in destinatarios
                  if not es._digest_already_sent(semana, d["email"]) and not es.is_email_unsubscribed(d["email"])]
    print(f"Semana {semana}: {len(destinatarios)} registrados, {len(pendientes)} pendientes.")
    print(f"Remitente: {settings.smtp_from_name} <{settings.smtp_user}> (Gmail)")
    if not pendientes:
        print("Nada que enviar.")
        return
    tope = min(len(pendientes), LIMITE_GMAIL_DIA)
    if not args.si:
        ok = input(f"¿Enviar el boletín a {tope} personas? Escribe SI para continuar: ").strip().upper()
        if ok != "SI":
            print("Cancelado.")
            return
    enviados = fallidos = sin_eventos = 0
    for i, r in enumerate(pendientes[:tope], 1):
        res = es.enviar_digest_a(r, semana)
        enviados += res == "sent"
        fallidos += res == "failed"
        sin_eventos += res == "sin_eventos"
        print(f"  [{i}/{tope}] {res:11} {r['email']}")
        if fallidos >= 5 and enviados == 0:
            print("❌ 5 fallos sin ningún envío: revisa SMTP_USER/SMTP_PASSWORD (contraseña de aplicación).")
            break
        time.sleep(1.2)  # ritmo amable con Gmail
    print(f"\n✅ Enviados {enviados} · fallidos {fallidos} · sin eventos {sin_eventos}")
    es._log_boletin({"sent": enviados, "failed": fallidos, "pendientes": len(pendientes) - enviados,
                     "remitente": "PC (Gmail SMTP)", "week_start": semana, "destinatarios": len(destinatarios)})


if __name__ == "__main__":
    main()
