"""Diagnostico completo de compatibilidad. Ejecutar: DIAGNOSTICO.bat  (o python -m app.diagnostico)
Genera logs/diagnostico.txt para revisar o compartir si algo falla."""
import importlib
import json
import os
import platform
import shutil
import socket
import sys
import tempfile
import time

from .paths import LOGS_DIR, OUTPUT_DIR, ROOT, force_portable_env

REQUISITOS = {"numpy": "1.26", "PIL": "10.0", "gradio_client": "1.3", "huggingface_hub": "0.25"}


def _ver(t):
    return tuple(int(x) for x in str(t).split("+")[0].split(".")[:3] if x.isdigit())


def ejecutar(log=print) -> dict:
    force_portable_env()
    r = {}

    def anotar(clave, valor, ok=True):
        r[clave] = ("OK   " if ok else "MAL  ") + str(valor)
        log(f"{'✔' if ok else '✘'} {clave}: {valor}")

    anotar("sistema", f"{platform.system()} {platform.release()} ({platform.machine()})")
    anotar("python", f"{sys.version.split()[0]} en {sys.executable}", sys.version_info >= (3, 11))
    anotar("carpeta del proyecto", str(ROOT))
    if any(ord(c) > 127 for c in str(ROOT)):
        anotar("ruta con acentos", "la ruta tiene caracteres especiales; deberia funcionar, pero si falla Blender muevelo a una ruta simple", False)
    for mod, minimo in REQUISITOS.items():
        try:
            m = importlib.import_module(mod)
            v = getattr(m, "__version__", "?")
            anotar(f"paquete {mod}", v, v == "?" or _ver(v) >= _ver(minimo))
        except ImportError:
            anotar(f"paquete {mod}", "NO INSTALADO (ejecuta INSTALAR.bat)", mod in ("gradio_client", "huggingface_hub") and False)
    try:
        prueba = OUTPUT_DIR / f"_prueba_{os.getpid()}.tmp"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
        anotar("escritura en el disco", "OK")
    except OSError as e:
        anotar("escritura en el disco", f"sin permiso: {e}", False)
    libre = shutil.disk_usage(ROOT).free / 1e9
    anotar("espacio libre", f"{libre:.1f} GB", libre > 3)
    anotar("carpeta temporal", tempfile.gettempdir(), str(ROOT) in tempfile.gettempdir())
    from . import config
    try:
        cfg = config.get(reload=True)
        anotar("config.toml", "valido")
    except SystemExit as e:
        anotar("config.toml", str(e).strip(), False)
        cfg = {}
    puerto = int(cfg.get("server", {}).get("port", 8765))
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", puerto))
        anotar("puerto", f"{puerto} libre")
    except OSError:
        anotar("puerto", f"{puerto} ocupado (la app usara el siguiente libre o ya esta abierta)", True)
    finally:
        s.close()
    from .forge.util import fuentes_disponibles
    anotar("fuentes", ", ".join(list(fuentes_disponibles())[:5]) or "ninguna", bool(fuentes_disponibles()))
    # Blender
    from . import blender
    inf = blender.info(refrescar=True)
    if "ruta" in inf:
        anotar("blender", f"{inf['texto']} en {inf['ruta']}")
        try:
            t0 = time.time()
            from .generators import mesh_pro
            prueba = ROOT / "cache" / "diag_blender.glb"
            mesh_pro.guardar_glb(mesh_pro.construir("barril", 1), prueba)
            blender.pulir_procedural(prueba, prueba, "barril", fbx=True, preview=None, log=lambda *_: None)
            anotar("blender (prueba real)", f"pulio y exporto GLB+FBX en {time.time() - t0:.0f}s")
        except Exception as e:  # noqa: BLE001
            anotar("blender (prueba real)", str(e)[:200], False)
    else:
        anotar("blender", inf.get("error", "no encontrado") + " (opcional)", True)
    # IA
    try:
        from .ia import motor
        for k, v in motor.probar_conexiones(lambda *_: None).items():
            anotar(f"IA {k}", v, not str(v).startswith(("no responde", "FALTA")))
    except Exception as e:  # noqa: BLE001
        anotar("IA", str(e)[:200], False)
    informe = LOGS_DIR / "diagnostico.txt"
    informe.write_text(f"Diagnostico {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n" +
                       "\n".join(f"{v}  |  {k}" for k, v in r.items()), encoding="utf-8")
    return r


if __name__ == "__main__":
    for flujo in (sys.stdout,):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ejecutar()
    print(f"\nInforme: {LOGS_DIR / 'diagnostico.txt'}")
