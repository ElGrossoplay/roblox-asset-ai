"""Backend en la nube via Replicate (un solo token para imagen, musica, SFX y 3D).

Los nombres de modelo se configuran en config.toml. Formatos aceptados:
  "owner/modelo"            -> modelos "oficiales" (endpoint por modelo)
  "owner/modelo:VERSION"    -> cualquier modelo, con hash de version
Revisa en replicate.com el nombre exacto y los parametros de cada modelo:
cambian con el tiempo.
"""
import json
import time
import urllib.request
from pathlib import Path

from .. import config

API = "https://api.replicate.com/v1"


def _req(url, data=None, metodo=None):
    token = config.secret("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("Falta REPLICATE_API_TOKEN en config/secrets.env")
    req = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None, method=metodo,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "wait=60"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def ejecutar(modelo: str, entrada: dict, timeout: int = 600):
    if not modelo:
        raise RuntimeError("No hay modelo configurado para este modulo")
    if ":" in modelo:
        pred = _req(f"{API}/predictions", {"version": modelo.split(":", 1)[1], "input": entrada})
    else:
        pred = _req(f"{API}/models/{modelo}/predictions", {"input": entrada})
    inicio = time.time()
    while pred.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - inicio > timeout:
            raise TimeoutError("Replicate tardo demasiado")
        time.sleep(2)
        pred = _req(pred["urls"]["get"])
    if pred["status"] != "succeeded":
        raise RuntimeError(f"Replicate: {pred.get('error') or pred['status']}")
    return pred["output"]


def _primera_url(salida):
    if isinstance(salida, str):
        return salida
    if isinstance(salida, list) and salida:
        return _primera_url(salida[0])
    if isinstance(salida, dict):
        for k in ("model_file", "glb", "audio", "output", "mesh", "image"):
            if k in salida and salida[k]:
                return _primera_url(salida[k])
        for v in salida.values():
            try:
                return _primera_url(v)
            except RuntimeError:
                continue
    raise RuntimeError(f"Salida inesperada: {str(salida)[:200]}")


def descargar(url: str, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r, open(destino, "wb") as f:
        f.write(r.read())
    return destino


def imagen(modelo, prompt, destino: Path, aspecto="1:1") -> Path:
    out = ejecutar(modelo, {"prompt": prompt, "aspect_ratio": aspecto, "output_format": "png"})
    return descargar(_primera_url(out), destino)


def audio(modelo, prompt, destino: Path, duracion: float) -> Path:
    out = ejecutar(modelo, {"prompt": prompt, "duration": int(max(1, duracion)), "output_format": "wav"})
    url = _primera_url(out)
    ext = Path(url.split("?")[0]).suffix or ".wav"
    return descargar(url, destino.with_suffix(ext))


def malla_desde_imagen(modelo, imagen_url_o_ruta, destino: Path) -> Path:
    src = imagen_url_o_ruta
    if isinstance(src, Path):  # Replicate acepta data URIs para archivos pequenos
        import base64
        src = "data:image/png;base64," + base64.b64encode(src.read_bytes()).decode()
    out = ejecutar(modelo, {"images": [src], "image": src, "generate_model": True})
    return descargar(_primera_url(out), destino)


def imagen_pollinations(prompt: str, destino: Path, ancho: int = 1024, alto: int = 1024, semilla: int = 0) -> Path:
    """Pollinations.ai: plan gratuito con clave (enter.pollinations.ai). Sin garantia de disponibilidad.
    Verifica en su web la URL vigente si deja de funcionar."""
    import urllib.parse
    url = (f"https://gen.pollinations.ai/image/{urllib.parse.quote(prompt)}"
           f"?model=flux&width={ancho}&height={alto}&seed={semilla}&nologo=true")
    headers = {"User-Agent": "RobloxAssetAI"}
    key = config.secret("POLLINATIONS_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as f:
        f.write(r.read())
    return destino
