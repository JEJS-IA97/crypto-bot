"""CLI del informe diario por correo (spec 002, RF-3, RF-4, RF-5).

Lo ejecuta el workflow `daily-report.yml` de GitHub Actions a las 08:00 UTC
(igual que puede lanzarlo el propietario a mano o desde local):

    python send_daily_report.py [--date YYYY-MM-DD]

Crea el esquema si falta (idempotente), construye el informe con
`report_service` y lo envía con `email_service`. La configuración de
correo sale de las variables de entorno (RF-7): sin `REPORT_TO`,
`SMTP_USER` o `SMTP_PASS` termina con `SystemExit` y mensaje claro
(fail-closed, RF-4) sin imprimir ningún valor. `DATABASE_URL` apunta a
Postgres (Neon) en Actions y a SQLite en local (RF-2).

El informe se lee directamente de la base de datos, así que se envía
aunque el bot esté detenido o Render suspenda el servicio (RF-5).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from app import database
from app.config import settings
from app.database import Base
from app.models import utc_now
from app.services.email_service import send_email
from app.services.report_service import build_daily_report

REPORT_HOUR_UTC = 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Envía el informe diario de crypto-bot por correo.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Día UTC del informe (YYYY-MM-DD); por defecto hoy.",
    )
    return parser


def _report_moment(date_text: str | None) -> datetime:
    if date_text is None:
        return utc_now()
    try:
        day = date.fromisoformat(date_text)
    except ValueError:
        raise SystemExit(
            f"Fecha inválida: {date_text!r}; usa YYYY-MM-DD."
        ) from None
    return datetime(day.year, day.month, day.day, REPORT_HOUR_UTC)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    moment = _report_moment(args.date)

    if not settings.report_to.strip():
        raise SystemExit(
            "Falta el destinatario (REPORT_TO): informe no enviado."
        )
    if not settings.smtp_user.strip():
        raise SystemExit(
            "Falta el usuario SMTP (SMTP_USER): informe no enviado."
        )
    if not settings.smtp_pass:
        raise SystemExit(
            "Falta la contraseña SMTP (SMTP_PASS): informe no enviado."
        )

    Base.metadata.create_all(bind=database.engine)

    db = database.SessionLocal()
    try:
        body = build_daily_report(db, now=moment)
    finally:
        db.close()

    send_email(
        subject=(
            f"Informe diario — crypto-bot — "
            f"{moment.strftime('%Y-%m-%d')} (UTC)"
        ),
        body=body,
        to=settings.report_to,
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_pass,
    )
    print("Informe diario enviado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
