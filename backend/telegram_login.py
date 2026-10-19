"""Conecta tu cuenta de Telegram una sola vez y lista tus chats.

1. Entra a https://my.telegram.org → API development tools → crea una app.
2. Pon en backend/.env: TELEGRAM_API_ID=... y TELEGRAM_API_HASH=...
3. Ejecuta (desde backend/):  .venv\\Scripts\\python.exe telegram_login.py
   Telegram te manda un código a la app; lo escribes aquí (tú, no el bot).
4. Copia los ids de los grupos de señales a TELEGRAM_CHATS en .env (separados por coma)
   y reinicia el bot. La sesión queda en data/telegram.session: no la compartas.
"""

from telethon.sync import TelegramClient

from app.config import settings
from app.signals.telegram import SESSION_PATH


def main() -> None:
    if not (settings.telegram_api_id and settings.telegram_api_hash):
        raise SystemExit("Falta TELEGRAM_API_ID / TELEGRAM_API_HASH en backend/.env")
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TelegramClient(str(SESSION_PATH), settings.telegram_api_id, settings.telegram_api_hash) as client:
        print("\nTus grupos y canales (id  ·  nombre):")
        for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                print(f"{dialog.id:>16}  ·  {dialog.name}")
        print("\nListo. Copia los ids que quieras a TELEGRAM_CHATS en backend/.env y reinicia el bot.")


if __name__ == "__main__":
    main()
