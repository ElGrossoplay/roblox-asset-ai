"""Rutas portables: todo vive dentro de la carpeta del proyecto (el disco externo).

Nada se escribe en C:\\ ni en el perfil de usuario. Si Windows cambia la letra
del disco (E:, F:, ...), las rutas siguen funcionando porque se calculan
desde la ubicacion de este archivo.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / "cache"
MODELS_DIR = ROOT / "models"
LOGS_DIR = ROOT / "logs"
WEB_DIR = ROOT / "web"
TEMP_DIR = CACHE_DIR / "temp"

for _d in (CONFIG_DIR, OUTPUT_DIR, CACHE_DIR, MODELS_DIR, LOGS_DIR, TEMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def force_portable_env() -> None:
    """Redirige caches de librerias de IA al disco externo.

    Se llama al arrancar, para que HuggingFace, PyTorch, pip, etc. no
    descarguen GB de modelos a C:\\Users\\...\\.cache.
    """
    env = {
        "HF_HOME": MODELS_DIR / "huggingface",
        "HUGGINGFACE_HUB_CACHE": MODELS_DIR / "huggingface" / "hub",
        "TRANSFORMERS_CACHE": MODELS_DIR / "huggingface" / "hub",
        "TORCH_HOME": MODELS_DIR / "torch",
        "XDG_CACHE_HOME": CACHE_DIR,
        "PIP_CACHE_DIR": CACHE_DIR / "pip",
        "OLLAMA_MODELS": MODELS_DIR / "ollama",
        "TEMP": TEMP_DIR,
        "TMP": TEMP_DIR,
        "MPLCONFIGDIR": CACHE_DIR / "matplotlib",
    }
    for key, value in env.items():
        Path(value).mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(value)
    import tempfile
    tempfile.tempdir = str(TEMP_DIR)
