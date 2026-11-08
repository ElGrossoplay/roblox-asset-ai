@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Borrando archivos temporales y cache de pip (no borra tus packs ni modelos)...
if exist "cache\temp" rmdir /s /q "cache\temp"
if exist "cache\pip" rmdir /s /q "cache\pip"
for /d /r "app" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
mkdir "cache\temp"
echo Listo.
pause
