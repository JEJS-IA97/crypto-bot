@echo off
rem Detiene el bot (puerto 8000).
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if (-not $c) { Write-Output 'El bot no esta corriendo.'; exit 0 }; $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; Write-Output 'Bot detenido.'"
