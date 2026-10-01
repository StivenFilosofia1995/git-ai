@echo off
chcp 65001 >nul
REM Envia el boletin semanal a los registrados desde este PC (Gmail).
REM 1) Primero una prueba a tu correo:  enviar_boletin.bat --prueba tu@correo.com
REM 2) Luego a todos:                   enviar_boletin.bat
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m runner.enviar_boletin %*
pause
