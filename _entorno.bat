@echo off
rem Variables comunes: todo queda dentro del disco externo.
set "RAIZ=%~dp0"
set "PY=%RAIZ%runtime\python"
set "PYEXE=%PY%\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
set "PIP_CACHE_DIR=%RAIZ%cache\pip"
set "HF_HOME=%RAIZ%models\huggingface"
set "TORCH_HOME=%RAIZ%models\torch"
set "OLLAMA_MODELS=%RAIZ%models\ollama"
set "TEMP=%RAIZ%cache\temp"
set "TMP=%RAIZ%cache\temp"
if not exist "%RAIZ%cache\temp" mkdir "%RAIZ%cache\temp"
