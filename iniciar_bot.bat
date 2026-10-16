@echo off
rem Arranca el bot en 2a plana (sin ventana) sobre Neon y log en backend\logs.
rem Idempotente: si el puerto 8000 ya esta escuchado, no hace nada.
rem Guarda el PID del lanzador en backend\logs\bot.pid (detener_bot.bat mata su arbol).
setlocal
cd /d "%~dp0backend"
if not exist logs mkdir logs

rem Corre si el puerto escucha o si el PID del pidfile sigue vivo (el arranque tarda en abrir el puerto).
powershell -NoProfile -Command "$f = 'logs\bot.pid'; $p = if (Test-Path $f) { Get-Process -Id (Get-Content $f) -ErrorAction SilentlyContinue }; if ((Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) -or ($p -and $p.ProcessName -eq 'python')) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
    echo El bot ya esta corriendo en el puerto 8000.
    exit /b 0
)

rem Log de la app en archivo rotado (5x5 MB); stderr queda solo para uvicorn.
set "LOG_FILE=%CD%\logs\bot.log"
rem Nucleo de tendencia diaria (SMA50 y SMA200, 50 %% del capital por par).
rem Va aqui y no en .env: los tests leen el .env y esperan los valores por defecto.
set "TREND_ENABLED=true"
set "TRADING_SYMBOLS=BTCUSDT,ETHUSDT"
set "RISK_MAX_TOTAL_EXPOSURE_PCT=100"
set "STRATEGY_VERSION=trend-001"
rem Laboratorio: torneo de 10 estrategias x 20/50/100 USD en paper (longs y shorts), en vivo por WebSocket.
set "LAB_ENABLED=true"
powershell -NoProfile -Command "(Start-Process -PassThru -WindowStyle Hidden -FilePath '%CD%\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log' -WorkingDirectory '%CD%' -RedirectStandardOutput '%CD%\logs\bot.out.log' -RedirectStandardError '%CD%\logs\bot.err.log').Id | Set-Content -Encoding ascii '%CD%\logs\bot.pid'"

echo Bot arrancado en 2a plana. Logs: backend\logs\bot.log (app) y bot.err.log (uvicorn)
endlocal
