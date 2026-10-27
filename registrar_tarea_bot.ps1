# Registra la tarea "crypto-bot" en el Programador de tareas (usuario actual, sin admin).
# Disparos: al iniciar sesion (+1 min), al despertar de la suspension, y cada 30 min de vigilante.
# iniciar_bot.bat es idempotente: si el bot ya corre no hace nada; si se cayo, lo levanta.
# Todo corre oculto (sin ventana). Quitar la tarea: Unregister-ScheduledTask -TaskName crypto-bot -Confirm:$false
# Uso: clic derecho -> "Ejecutar con PowerShell" (o: powershell -ExecutionPolicy Bypass -File registrar_tarea_bot.ps1)

$bat = Join-Path $PSScriptRoot 'iniciar_bot.bat'
# conhost --headless evita que parpadee una consola (Windows 11).
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument "--headless cmd.exe /c `"$bat`""

$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = 'PT1M'
$logon.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)).Repetition

# Al volver de la suspension (evento 1 de Power-Troubleshooter en el registro System).
$class = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$wake = $class | New-CimInstance -ClientOnly
$wake.Enabled = $true
$wake.Delay = 'PT1M'
$wake.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'crypto-bot' -Action $action -Trigger @($logon, $wake) -Settings $settings -Force `
    -Description 'Arranca el backend de crypto-bot al iniciar sesion y al despertar, y lo vigila cada 30 min.' | Out-Null

# Que la PC no se suspenda sola mientras este enchufada (la pantalla si se apaga a los 10 min).
# Para volver a como estaba: powercfg /change standby-timeout-ac 30
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 10

Start-ScheduledTask -TaskName 'crypto-bot'
Write-Output 'Listo: tarea crypto-bot registrada (inicio de sesion + al despertar + cada 30 min) y suspension desactivada con corriente.'
