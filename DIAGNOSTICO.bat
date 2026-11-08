@echo off
chcp 65001 >nul
title Roblox Asset AI - Diagnostico
cd /d "%~dp0"
call "%~dp0_entorno.bat"
if not exist "%PYEXE%" (
  echo Python portable no instalado. Ejecuta INSTALAR.bat primero.
  pause & exit /b 1
)
"%PYEXE%" -m app.diagnostico
echo.
echo Informe guardado en logs\diagnostico.txt
pause
