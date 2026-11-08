@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_entorno.bat"
set /p "TEMA=Describe tu juego: "
"%PYEXE%" -m app.cli "%TEMA%"
pause
