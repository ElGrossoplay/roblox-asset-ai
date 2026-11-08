"""Carga config.toml y secrets.env (sin dependencias externas)."""
import copy
import os
import threading
import tomllib
from .paths import CONFIG_DIR

_cache = None
_local = threading.local()  # permite que un trabajo use otro backend sin tocar config.toml


def _load_secrets() -> None:
    path = CONFIG_DIR / "secrets.env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


def get(reload: bool = False) -> dict:
    global _cache
    if _cache is None or reload:
        _load_secrets()
        texto = (CONFIG_DIR / "config.toml").read_text(encoding="utf-8-sig")  # tolera BOM del Bloc de notas
        try:
            _cache = tomllib.loads(texto)
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"\n  ERROR en config\\config.toml: {e}\n  (revisa comillas y signos '=' en esa linea)\n") from e
    return getattr(_local, "override", None) or _cache


def usar_backend(backend: str | None) -> None:
    """Llamado al inicio de un trabajo (en su hilo). backend: None/'auto' = lo de config.toml.
    'offline' = todo procedural. 'pollinations'/'cloud'/'local' = solo cambia imagen
    (y musica/sfx/3D cuando el backend existe para ese modulo)."""
    _local.override = None
    if not backend or backend == "auto":
        return
    cfg = copy.deepcopy(get(reload=True))
    soporta = {"imagen": {"offline", "pollinations", "cloud", "local"}, "musica": {"offline", "cloud", "local"},
               "sfx": {"offline", "cloud", "local"}, "malla3d": {"offline", "cloud"}}
    for modulo, validos in soporta.items():
        if backend in validos:
            cfg[modulo]["backend"] = backend
    if backend == "offline":
        cfg["director"]["backend"] = "offline"
        cfg["ia"] = {"activa": False}
    elif backend in ("hf_space", "pollinations", "local", "replicate"):
        cfg["ia"] = {"activa": True, "forzar": backend if backend != "replicate" else None}
    _local.override = cfg


def secret(name: str) -> str:
    get()
    return os.environ.get(name, "")
