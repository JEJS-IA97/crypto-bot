@echo off
rem Reinicia el bot: lo lanza el propio bot (data\restart.flag) fuera de su arbol de procesos.
timeout /t 3 /nobreak >nul
call "%~dp0detener_bot.bat"
timeout /t 5 /nobreak >nul
call "%~dp0iniciar_bot.bat"
