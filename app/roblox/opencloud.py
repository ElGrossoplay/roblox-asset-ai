"""Subida de assets a Roblox con la Open Cloud Assets API.

Docs: https://create.roblox.com/docs/cloud/guides/usage-assets
Limites: el audio tiene cupo mensual (100 subidas con cuenta verificada por ID,
10 sin verificar) y todo pasa por moderacion.
"""
import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .. import config

API = "https://apis.roblox.com/assets/v1"
TIPOS = {".wav": ("Audio", "audio/wav"), ".mp3": ("Audio", "audio/mpeg"), ".ogg": ("Audio", "audio/ogg"),
         ".flac": ("Audio", "audio/flac"), ".png": ("Decal", "image/png"), ".jpg": ("Decal", "image/jpeg"),
         ".fbx": ("Model", "model/fbx"), ".glb": ("Model", "model/gltf-binary"), ".gltf": ("Model", "model/gltf+json")}


def _multipart(campos: dict, archivo: Path, mime: str):
    limite = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="fileContent"; filename="{archivo.name}"\r\n'
                  f"Content-Type: {mime}\r\n\r\n".encode() + archivo.read_bytes() + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def subir(archivo: Path, nombre: str, descripcion: str = "Generado con Roblox Asset AI") -> str:
    key = config.secret("ROBLOX_API_KEY")
    cfg = config.get()["roblox"]
    if not key or not cfg.get("creator_id"):
        raise RuntimeError("Configura ROBLOX_API_KEY (secrets.env) y roblox.creator_id (config.toml)")
    tipo, mime = TIPOS.get(archivo.suffix.lower(), (None, None))
    if not tipo:
        raise ValueError(f"Tipo no soportado: {archivo.suffix}")
    creador = ({"userId": str(cfg["creator_id"])} if cfg.get("creator_tipo", "user") == "user"
               else {"groupId": str(cfg["creator_id"])})
    meta = {"assetType": tipo, "displayName": nombre[:50], "description": descripcion,
            "creationContext": {"creator": creador}}
    cuerpo, ctype = _multipart({"request": json.dumps(meta)}, archivo, mime)
    req = urllib.request.Request(f"{API}/assets", data=cuerpo, method="POST",
                                 headers={"x-api-key": key, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            op = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Open Cloud {e.code}: {e.read().decode(errors='ignore')[:300]}") from e
    return _esperar(op, key)


def _esperar(op: dict, key: str, timeout: int = 120) -> str:
    ruta = op.get("path") or f"operations/{op.get('operationId')}"
    inicio = time.time()
    while not op.get("done"):
        if time.time() - inicio > timeout:
            raise TimeoutError("La operacion de subida no termino a tiempo")
        time.sleep(2)
        req = urllib.request.Request(f"{API}/{ruta}", headers={"x-api-key": key})
        with urllib.request.urlopen(req, timeout=60) as r:
            op = json.loads(r.read())
    if "error" in op:
        raise RuntimeError(f"Subida rechazada: {op['error']}")
    return str(op["response"]["assetId"])
