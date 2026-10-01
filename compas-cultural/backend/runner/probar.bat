@echo off
chcp 65001 >nul
REM Ensayo: 5 perfiles, navegador visible, NO escribe en la base de datos.
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m runner.main --ig --fb --limite 5 --dry-run --ver
pause
