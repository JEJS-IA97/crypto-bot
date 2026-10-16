@echo off
rem Detiene el bot: primero por pidfile (arbol del lanzador del venv), luego por puerto 8000.
rem Solo mata el PID del pidfile si sigue siendo python (evita PIDs reciclados).
powershell -NoProfile -Command "$f = '%~dp0backend\logs\bot.pid'; if (Test-Path $f) { $p = Get-Process -Id (Get-Content $f) -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -eq 'python') { taskkill /T /F /PID $p.Id | Out-Null }; Remove-Item $f }; Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; Write-Output 'Bot detenido.'"
