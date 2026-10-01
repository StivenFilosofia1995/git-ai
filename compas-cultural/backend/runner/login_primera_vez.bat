@echo off
chcp 65001 >nul
REM Abre un navegador visible para que TU inicies sesion en Instagram y Facebook.
REM La sesion queda guardada en %LOCALAPPDATA%\CulturaEterea\pw-profile (nunca la contrasena).
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m runner.main --login
