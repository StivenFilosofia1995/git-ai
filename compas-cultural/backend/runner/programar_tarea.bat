@echo off
chcp 65001 >nul
REM Programa run_todo.bat dos veces al dia (7:00 y 17:00) en el Programador de tareas de Windows.
schtasks /Create /SC DAILY /TN "CulturaEterea Runner 7am" /TR "\"%~dp0run_todo.bat\"" /ST 07:00 /F
schtasks /Create /SC DAILY /TN "CulturaEterea Runner 5pm" /TR "\"%~dp0run_todo.bat\"" /ST 17:00 /F
echo Tareas creadas. Para quitarlas:
echo   schtasks /Delete /TN "CulturaEterea Runner 7am" /F
echo   schtasks /Delete /TN "CulturaEterea Runner 5pm" /F
pause
