# Registra la tarea "crypto-bot" en el Programador de tareas (usuario actual, sin admin).
# Disparo: al iniciar sesion (+1 min) y luego cada 30 min mientras la sesion siga abierta.
# iniciar_bot.bat es idempotente, asi que la repeticion actua de reintento/vigilante:
# si el bot se cayo, lo vuelve a levantar; si ya corre, no hace nada.
# schtasks.exe no sirve aqui: /SC ONLOGON no admite repeticion (/RI) ni reintentos.
# Quitar la tarea: Unregister-ScheduledTask -TaskName crypto-bot -Confirm:$false

$bat = Join-Path $PSScriptRoot 'iniciar_bot.bat'
# conhost --headless evita que parpadee una consola cada 30 min (Windows 11).
$action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument "--headless cmd.exe /c `"$bat`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$trigger.Delay = 'PT1M'
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName 'crypto-bot' -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Arranca el backend de crypto-bot al iniciar sesion y lo vigila cada 30 min.'
