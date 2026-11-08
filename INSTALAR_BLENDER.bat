@echo off
chcp 65001 >nul
title Roblox Asset AI - Blender portable
cd /d "%~dp0"
echo.
echo  Descarga Blender LTS oficial (portable, ~1 GB descomprimido) en runtime\blender.
echo  No se instala en Windows. Si ya tienes Blender instalado, no hace falta: se detecta solo.
echo.
choice /m "Continuar"
if errorlevel 2 exit /b
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\instalar_blender.ps1" -Serie 4.5
if errorlevel 1 (
  echo.
  echo ERROR. Revisa tu conexion o descarga el .zip de blender.org y descomprimelo en runtime\blender
)
pause
