@echo off
rem Arranca el bot en 2a plana (sin ventana) sobre Neon y log en backend\logs.
rem Idempotente: si el puerto 8000 ya esta escuchado, no hace nada.
setlocal
cd /d "%~dp0backend"
if not exist logs mkdir logs

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
    echo El bot ya esta corriendo en el puerto 8000.
    exit /b 0
)

powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath '%CD%\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory '%CD%' -RedirectStandardOutput '%CD%\logs\bot.out.log' -RedirectStandardError '%CD%\logs\bot.err.log'"

echo Bot arrancado en 2a plana. Logs: backend\logs\bot.out.log y bot.err.log
endlocal
