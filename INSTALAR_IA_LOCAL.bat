@echo off
chcp 65001 >nul
title Roblox Asset AI - IA local (GPU)
cd /d "%~dp0"
call "%~dp0_entorno.bat"
echo.
echo  Esto instala PyTorch (CUDA), diffusers y transformers DENTRO del disco.
echo  Ocupa unos 5-6 GB, y cada modelo descargado despues ocupa 2-7 GB mas
echo  (quedan en la carpeta models). Requiere GPU NVIDIA con 6 GB+ de VRAM.
echo.
choice /m "Continuar"
if errorlevel 2 exit /b
if not exist "%PYEXE%" call "%~dp0INSTALAR.bat"
"%PYEXE%" -m pip install --no-warn-script-location torch --index-url https://download.pytorch.org/whl/cu124
"%PYEXE%" -m pip install --no-warn-script-location -r "%RAIZ%requirements-local.txt"
echo.
echo  Listo. En config\config.toml cambia backend = "local" en los modulos que quieras.
pause
