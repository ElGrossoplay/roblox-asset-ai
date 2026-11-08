"""Puente entre la app y Blender en modo sin ventana (blender -b).

Cada operacion escribe un JSON con los parametros en cache\\blender\\<trabajo>, lanza Blender
con un script de app\\blender\\scripts y lee el JSON de resultado. Cualquier fallo lanza
BlenderError y la herramienta que llamo usa su procesamiento alternativo (sin Blender).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .. import config
from ..paths import CACHE_DIR, LOGS_DIR, ROOT

SCRIPTS = Path(__file__).resolve().parent / "scripts"
VERSION_MINIMA = (3, 6)
_cache = {}


class BlenderError(RuntimeError):
    pass


def _candidatos() -> list:
    cfg = config.get().get("blender", {})
    c = []
    if cfg.get("ruta"):
        c.append(cfg["ruta"])
    c += sorted(glob.glob(str(ROOT / "runtime" / "blender" / "**" / "blender.exe"), recursive=True), reverse=True)
    c += sorted(glob.glob(str(ROOT / "runtime" / "blender" / "**" / "blender"), recursive=True), reverse=True)
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
            if base:
                c += sorted(glob.glob(os.path.join(base, "Blender Foundation", "Blender*", "blender.exe")), reverse=True)
        c += glob.glob(os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "steamapps", "common", "Blender", "blender.exe"))
    else:
        c += ["/usr/bin/blender", "/usr/local/bin/blender", "/Applications/Blender.app/Contents/MacOS/Blender"]
    en_path = shutil.which("blender")
    if en_path:
        c.append(en_path)
    return [x for x in dict.fromkeys(c) if x and os.path.isfile(x)]


def _sin_ventana():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}  # CREATE_NO_WINDOW


def _entorno():
    """Configuracion y cache de Blender dentro del disco externo (no toca el perfil de Windows)."""
    env = dict(os.environ)
    base = CACHE_DIR / "blender_usuario"
    for k, sub in (("BLENDER_USER_CONFIG", "config"), ("BLENDER_USER_SCRIPTS", "scripts"),
                   ("BLENDER_USER_DATAFILES", "datafiles"), ("BLENDER_USER_RESOURCES", "")):
        d = base / sub if sub else base
        d.mkdir(parents=True, exist_ok=True)
        env[k] = str(d)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def info(refrescar=False) -> dict:
    """{'ruta', 'version': (4,5,3), 'texto'} o {'error': ...}."""
    if "info" in _cache and not refrescar:
        return _cache["info"]
    res = {"error": "Blender no encontrado (ejecuta INSTALAR_BLENDER.bat o indica [blender] ruta en config.toml)"}
    for exe in _candidatos():
        try:
            p = subprocess.run([exe, "-b", "--factory-startup", "--version"], capture_output=True, text=True,
                               timeout=60, env=_entorno(), **_sin_ventana())
            m = re.search(r"Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", p.stdout + p.stderr)
            if not m:
                continue
            ver = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            if ver[:2] < VERSION_MINIMA:
                res = {"error": f"Blender {'.'.join(map(str, ver))} es muy antiguo (minimo {VERSION_MINIMA[0]}.{VERSION_MINIMA[1]})", "ruta": exe}
                continue
            res = {"ruta": exe, "version": ver, "texto": ".".join(map(str, ver))}
            break
        except (OSError, subprocess.TimeoutExpired) as e:
            res = {"error": f"No se pudo ejecutar {exe}: {e}"}
    _cache["info"] = res
    return res


def disponible() -> bool:
    if not config.get().get("blender", {}).get("activo", True):
        return False
    return "ruta" in info()


def ejecutar(script: str, params: dict, timeout: int = 900, log=print) -> dict:
    inf = info()
    if "ruta" not in inf:
        raise BlenderError(inf.get("error", "Blender no disponible"))
    trabajo = CACHE_DIR / "blender" / f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    trabajo.mkdir(parents=True, exist_ok=True)
    entrada, salida = trabajo / "entrada.json", trabajo / "salida.json"
    params = {**params, "salida_json": str(salida)}
    entrada.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    cmd = [inf["ruta"], "-b", "--factory-startup", "-noaudio", "--python-exit-code", "3",
           "--python", str(SCRIPTS / script), "--", str(entrada)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=_entorno(), cwd=str(trabajo), **_sin_ventana())
    except subprocess.TimeoutExpired as e:
        raise BlenderError(f"Blender tardo mas de {timeout}s") from e
    registro = (p.stdout or "") + "\n" + (p.stderr or "")
    (LOGS_DIR / "blender_ultimo.log").write_text(registro[-200000:], encoding="utf-8", errors="replace")
    if not salida.exists():
        ultima = next((l for l in reversed(registro.splitlines()) if "Error" in l or "Traceback" in l), registro.strip()[-300:])
        raise BlenderError(f"Blender fallo (codigo {p.returncode}): {ultima[:300]}  (ver logs/blender_ultimo.log)")
    res = json.loads(salida.read_text(encoding="utf-8"))
    if not res.get("ok"):
        raise BlenderError(res.get("error", "error desconocido en Blender"))
    if not config.get().get("blender", {}).get("conservar_temporales", False):
        shutil.rmtree(trabajo, ignore_errors=True)
    log(f"    Blender {inf['texto']}: {script} en {time.time() - t0:.0f}s")
    return res


def limpiar_modelo(entrada: Path, destino: Path, altura_studs=6.0, max_tris=18000, fbx=True, preview: Path | None = None,
                   organico=True, log=print) -> dict:
    """Modelo de IA -> una sola malla limpia, reducida conservando la textura, en studs, GLB (+FBX)."""
    cfg = config.get().get("blender", {})
    return ejecutar("limpiar_ia.py", {
        "entrada": str(entrada), "glb": str(destino), "fbx": str(Path(destino).with_suffix(".fbx")) if fbx else None,
        "altura": float(altura_studs), "max_tris": int(max_tris), "organico": organico,
        "preview": str(preview) if preview else None, "muestras": int(cfg.get("muestras_render", 24)),
        "tam_preview": int(cfg.get("tam_preview", 512))}, int(cfg.get("timeout", 900)), log)


def pulir_procedural(entrada: Path, destino: Path, nombre: str, fbx=True, preview: Path | None = None, log=print) -> dict:
    """Modelo procedural low-poly -> biseles, normales ponderadas, suavizado por angulo, GLB (+FBX)."""
    cfg = config.get().get("blender", {})
    organicos = ("arbol", "pino", "palmera", "arbusto", "roca", "hongo", "nube", "cerezo", "calabaza", "flor", "cactus", "tronco")
    return ejecutar("pulir_procedural.py", {
        "entrada": str(entrada), "glb": str(destino), "fbx": str(Path(destino).with_suffix(".fbx")) if fbx else None,
        "organico": any(o in nombre for o in organicos), "preview": str(preview) if preview else None,
        "muestras": int(cfg.get("muestras_render", 24)), "tam_preview": int(cfg.get("tam_preview", 512))},
        int(cfg.get("timeout", 900)), log)


def renderizar(entrada: Path, destino: Path, log=print) -> dict:
    cfg = config.get().get("blender", {})
    return ejecutar("render.py", {"entrada": str(entrada), "preview": str(destino),
                                  "muestras": int(cfg.get("muestras_render", 24)), "tam_preview": int(cfg.get("tam_preview", 512))},
                    int(cfg.get("timeout", 900)), log)


if __name__ == "__main__":
    print(json.dumps(info(True), indent=2), file=sys.stdout)
