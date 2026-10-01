@echo off
chcp 65001 >nul
REM Instala lo necesario para el runner local (una sola vez).
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual en .venv ...
  py -3 -m venv .venv || python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements-prod.txt playwright python-dotenv
python -m playwright install chromium
echo.
echo Listo. Ahora:
echo   1) Copia .env.example a .env y llena SUPABASE_URL y SUPABASE_KEY (service role).
echo   2) Ejecuta runner\login_primera_vez.bat e inicia sesion TU en Instagram y Facebook.
pause
