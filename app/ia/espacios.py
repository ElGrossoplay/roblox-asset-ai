"""Cliente ADAPTABLE para Hugging Face Spaces (Gradio).

Cada Space expone parametros distintos y cambian con el tiempo. En vez de fijar firmas,
este modulo lee la API del Space (view_api), elige el endpoint mas adecuado y llena
cada parametro por su nombre/tipo:  prompt, imagen, semilla, duracion, ancho, alto...
Los parametros que no reconoce se dejan con su valor por defecto.
"""
import os
import re
import time
from pathlib import Path

from .. import config
from ..paths import CACHE_DIR

_clientes = {}
_apis = {}

SINONIMOS = {
    "prompt": ["prompt", "caption", "text", "texto", "description", "tags", "input_text", "positive", "query", "message"],
    "negativo": ["negative", "neg_prompt", "negative_prompt"],
    "imagen": ["image", "input_image", "img", "image_input", "front", "mv_image_front", "reference"],
    "semilla": ["seed"],
    "aleatoria": ["randomize_seed", "random_seed", "randomize"],
    "ancho": ["width"],
    "alto": ["height"],
    "pasos": ["num_inference_steps", "steps", "inference_steps", "infer_step"],
    "duracion": ["duration", "audio_duration", "seconds", "length", "seconds_total", "audio_length"],
    "letra": ["lyrics", "lyric"],
    "guia": ["guidance_scale", "guidance", "cfg", "cfg_scale"],
    "quitar_fondo": ["rembg", "remove_background", "check_box_rembg", "remove_bg"],
}


class SinSpace(RuntimeError):
    pass


def _cliente(space: str):
    if space in _clientes:
        return _clientes[space]
    try:
        from gradio_client import Client
    except ImportError as e:
        raise SinSpace("Falta gradio_client (ejecuta INSTALAR.bat de nuevo)") from e
    token = config.secret("HF_TOKEN") or None
    destino = CACHE_DIR / "gradio"
    destino.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("GRADIO_TEMP_DIR", str(destino))
    try:
        c = Client(space, token=token, download_files=str(destino), verbose=False) if token else \
            Client(space, download_files=str(destino), verbose=False)
    except TypeError:  # versiones antiguas usan hf_token
        c = Client(space, hf_token=token, verbose=False)
    _clientes[space] = c
    return c


def _api(space: str) -> dict:
    if space not in _apis:
        c = _cliente(space)
        try:
            info = c.view_api(print_info=False, return_format="dict")
        except TypeError:
            info = c.view_api(return_format="dict")
        _apis[space] = info or {}
    return _apis[space]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", (s or "").lower().replace(" ", "_"))


def _rol(param: dict) -> str | None:
    nombre = _norm(param.get("parameter_name") or param.get("label") or "")
    etiqueta = _norm(param.get("label") or "")
    for rol, palabras in SINONIMOS.items():
        for w in palabras:
            if nombre == w or etiqueta == w:
                return rol
    for rol, palabras in SINONIMOS.items():
        for w in palabras:
            if w in nombre or w in etiqueta:
                return rol
    comp = (param.get("component") or "").lower()
    if comp == "image":
        return "imagen"
    return None


def _es_salida_archivo(ret: dict) -> bool:
    comp = (ret.get("component") or "").lower()
    tipo = str(ret.get("python_type", {}).get("type", "")).lower()
    return comp in ("image", "audio", "model3d", "file", "video", "gallery") or "filepath" in tipo or "file" in tipo


def elegir_endpoint(api: dict, necesita: set, salida: str, preferidos=()) -> tuple:
    """Devuelve (api_name, parametros) del endpoint que mejor encaja."""
    endpoints = dict(api.get("named_endpoints") or {})
    mejores = []
    for nombre, ep in endpoints.items():
        params = ep.get("parameters", [])
        roles = {_rol(p) for p in params}
        rets = ep.get("returns", [])
        if not any(_es_salida_archivo(r) for r in rets):
            continue
        if "prompt" in necesita and "prompt" not in roles and "imagen" not in necesita:
            continue
        if "imagen" in necesita and "imagen" not in roles:
            continue
        puntos = len(necesita & roles) * 10
        comps = " ".join((r.get("component") or "").lower() for r in rets)
        if salida in comps:
            puntos += 25
        n = nombre.lower()
        for i, pref in enumerate(preferidos):
            if pref in n:
                puntos += 40 - i
        if any(w in n for w in ("example", "random", "clear", "reset", "update", "lambda", "toggle", "load")):
            puntos -= 30
        mejores.append((puntos, nombre, params))
    if not mejores:
        raise SinSpace("El Space no tiene un endpoint compatible")
    mejores.sort(key=lambda x: -x[0])
    return mejores[0][1], mejores[0][2]


def _valor(param: dict, rol: str | None, datos: dict):
    if rol and rol in datos and datos[rol] is not None:
        v = datos[rol]
        if rol == "imagen":
            from gradio_client import handle_file
            return handle_file(str(v))
        tipo = str(param.get("python_type", {}).get("type", "")).lower()
        if "int" in tipo and isinstance(v, (int, float)):
            return int(v)
        if "float" in tipo and isinstance(v, (int, float)):
            return float(v)
        return v
    if param.get("parameter_has_default"):
        return param.get("parameter_default")
    tipo = str(param.get("python_type", {}).get("type", "")).lower()
    if "bool" in tipo:
        return False
    if "int" in tipo or "float" in tipo:
        return param.get("example_input") if param.get("example_input") is not None else 0
    return param.get("example_input")


def _archivos(resultado) -> list:
    """Extrae rutas locales de archivos de cualquier estructura de respuesta."""
    out = []

    def rec(x):
        if isinstance(x, str):
            if os.path.exists(x):
                out.append(Path(x))
        elif isinstance(x, dict):
            for k in ("value", "path", "name", "video", "image", "audio", "file"):
                if k in x:
                    rec(x[k])
            for v in x.values():
                if isinstance(v, (list, tuple, dict)):
                    rec(v)
        elif isinstance(x, (list, tuple)):
            for i in x:
                rec(i)
    rec(resultado)
    vistos, unicos = set(), []
    for p in out:
        if str(p) not in vistos:
            vistos.add(str(p))
            unicos.append(p)
    return unicos


def llamar(space: str, datos: dict, salida: str, preferidos=(), extensiones=(), log=print) -> list:
    """Llama al Space y devuelve la lista de archivos generados (filtrados por extension si se pide)."""
    api = _api(space)
    necesita = {k for k, v in datos.items() if v is not None and k in ("prompt", "imagen")}
    nombre, params = elegir_endpoint(api, necesita, salida, preferidos)
    kwargs = {}
    for p in params:
        pname = p.get("parameter_name")
        if not pname:
            continue
        kwargs[pname] = _valor(p, _rol(p), datos)
    log(f"    HF Space {space} {nombre}")
    t0 = time.time()
    res = _cliente(space).predict(api_name=nombre, **kwargs)
    archivos = _archivos(res)
    if extensiones:
        archivos = [a for a in archivos if a.suffix.lower() in extensiones] or archivos
    if not archivos:
        raise SinSpace(f"{space} no devolvio archivos")
    log(f"    listo en {time.time() - t0:.0f}s")
    return archivos
