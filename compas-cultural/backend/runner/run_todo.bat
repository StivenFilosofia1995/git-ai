@echo off
chcp 65001 >nul
REM Lo que ejecuta el Programador de tareas: IG (perfiles + feed) y FB.
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m runner.main --ig --feed --fb --limite 25
