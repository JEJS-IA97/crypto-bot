"""Reinicio sin José: si aparece data/restart.flag, el bot lanza reiniciar_bot.bat fuera de su
propio árbol de procesos (vía WMI, para que detener_bot.bat no lo mate) y borra la bandera.
Así Claude puede reiniciar escribiendo ese archivo desde la carpeta del proyecto."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

FLAG = Path("data/restart.flag")
SCRIPT = Path(__file__).resolve().parents[3] / "reiniciar_bot.bat"


def launch_restart() -> bool:
    if sys.platform != "win32" or not SCRIPT.exists():
        logger.warning("restart: not on Windows or %s missing", SCRIPT)
        return False
    cmd = f'cmd.exe /c ""{SCRIPT}""'
    ps = ("Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
          f"-Arguments @{{CommandLine='{cmd}'}} | Out-Null")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=30)
    return True


def check_once() -> bool:
    if not FLAG.exists():
        return False
    reason = FLAG.read_text(encoding="utf-8", errors="replace").strip()[:200]
    FLAG.unlink(missing_ok=True)
    logger.warning("restart: requested (%s)", reason or "sin motivo")
    return launch_restart()


async def restart_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(check_once)
        except Exception:  # noqa: BLE001
            logger.warning("restart: check failed", exc_info=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=20)
        except TimeoutError:
            pass
