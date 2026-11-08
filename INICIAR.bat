@echo off
chcp 65001 >nul
title Roblox Asset AI
cd /d "%~dp0"
call "%~dp0_entorno.bat"
if not exist "%PYEXE%" (
  echo Primero hay que instalar. Abriendo INSTALAR.bat...
  call "%~dp0INSTALAR.bat"
)
"%PYEXE%" -m app.main
if errorlevel 1 pause
