"""Envío del informe diario por Gmail SMTP (spec 002 RF-3/RF-4/RF-7;
spec 004 RF-1: parte HTML en `multipart/alternative`).

Solo stdlib: `smtplib` + `email.message.EmailMessage` con STARTTLS (puerto
587 por defecto). El envío es fail-closed: sin destinatario, usuario o
contraseña se rechaza antes de abrir conexión (RF-4) y la contraseña nunca
se interpola en mensajes de error ni se loguea (RF-7 / constitución #13:
los mensajes van en español).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

SMTP_TIMEOUT_SECONDS = 10


class EmailSendError(RuntimeError):
    """Fallo de conexión o autenticación SMTP, sin credenciales en el texto."""


def send_email(
    *,
    subject: str,
    body: str,
    to: str,
    host: str,
    port: int,
    user: str,
    password: str,
    html: str | None = None,
) -> None:
    """Envía un correo (texto plano; con `html` añade la parte HTML como
    `multipart/alternative`, spec 004 RF-1). Lanza `ValueError` si falta la
    configuración mínima y `EmailSendError` si falla la conexión o login."""
    if not to.strip():
        raise ValueError(
            "Falta el destinatario (REPORT_TO): envío rechazado."
        )
    if not user.strip():
        raise ValueError(
            "Falta el usuario SMTP (SMTP_USER): envío rechazado."
        )
    if not password:
        raise ValueError(
            "Falta la contraseña SMTP (SMTP_PASS): envío rechazado."
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = to
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(
            f"No se pudo enviar el correo vía {host}:{port}: {exc}"
        ) from exc
