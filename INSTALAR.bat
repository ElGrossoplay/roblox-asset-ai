@echo off
chcp 65001 >nul
title Roblox Asset AI - Instalacion portable
cd /d "%~dp0"
call "%~dp0_entorno.bat"
set "PYVER=3.12.8"

echo.
echo  ==============================================================
echo   Roblox Asset AI - instalacion PORTABLE
echo   Todo se guarda en: %RAIZ%
echo   (nada se instala en C:, no toca el registro de Windows)
echo  ==============================================================
echo.

if exist "%PYEXE%" goto :pip

echo [1/3] Descargando Python %PYVER% portable (unos 11 MB)...
if not exist "%PY%" mkdir "%PY%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "Invoke-WebRequest 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip' -OutFile \"$env:RAIZ\cache\python.zip\";" ^
  "Expand-Archive -Force \"$env:RAIZ\cache\python.zip\" \"$env:PY\";" ^
  "Remove-Item \"$env:RAIZ\cache\python.zip\";" ^
  "Set-Content -Encoding ascii \"$env:PY\python312._pth\" 'python312.zip','.','Lib\site-packages','..\..','import site'"
if not exist "%PYEXE%" (
  echo ERROR: no se pudo descargar Python. Revisa tu conexion a internet.
  pause & exit /b 1
)

:pip
if exist "%PY%\Scripts\pip.exe" goto :deps
echo [2/3] Instalando pip...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile \"$env:RAIZ\cache\get-pip.py\""
"%PYEXE%" "%RAIZ%cache\get-pip.py" --no-warn-script-location
del "%RAIZ%cache\get-pip.py" 2>nul

:deps
echo [3/3] Instalando librerias basicas (numpy, pillow)...
"%PYEXE%" -m pip install --no-warn-script-location -r "%RAIZ%requirements.txt"
if errorlevel 1 (
  echo ERROR instalando librerias.
  pause & exit /b 1
)

if not exist "%RAIZ%config\secrets.env" copy "%RAIZ%config\secrets.env.example" "%RAIZ%config\secrets.env" >nul

echo.
echo  Listo. Ahora abre INICIAR.bat
echo  (Opcional: INSTALAR_IA_LOCAL.bat si tienes GPU NVIDIA)
echo.
pause
