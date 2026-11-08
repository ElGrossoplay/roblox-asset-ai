"""API de alto nivel del motor de IA. Cada funcion prueba los proveedores en el orden de
config/ia.toml y lanza SinIA si ninguno responde (las herramientas caen entonces al modo
procedural). Todo archivo generado se guarda en la carpeta destino indicada."""
import json
import shutil
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from .. import config
from ..paths import CONFIG_DIR, CACHE_DIR
from . import espacios


class SinIA(RuntimeError):
    pass


def cfg() -> dict:
    ruta = CONFIG_DIR / "ia.toml"
    try:
        base = tomllib.loads(ruta.read_text(encoding="utf-8-sig")) if ruta.exists() else {}
    except tomllib.TOMLDecodeError as e:
        raise SinIA(f"config/ia.toml tiene un error: {e}") from e
    modo = config.get().get("ia", {}).get("forzar")
    if modo:
        for cap in base.values():
            if isinstance(cap, dict) and "orden" in cap:
                cap["orden"] = [p for p in cap["orden"] if p == modo] or cap["orden"]
    return base


def disponible() -> bool:
    """False si el usuario eligio 'Offline' en el selector (o ia.activa = false en config.toml)."""
    return bool(config.get().get("ia", {}).get("activa", True))


def _http(url, datos=None, headers=None, timeout=240):
    req = urllib.request.Request(url, data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"User-Agent": "RobloxAssetAI/1.0", **(headers or {}),
                                          **({"Content-Type": "application/json"} if datos is not None else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


_fallos = {}  # (capacidad, proveedor) -> [timestamps]: evita reintentar 20 veces un proveedor caido


def _probar(capacidad, intentos, log):
    import time
    errores = []
    for proveedor, fn in intentos:
        if proveedor not in cfg().get(capacidad, {}).get("orden", [proveedor]):
            continue
        recientes = [t for t in _fallos.get((capacidad, proveedor), []) if time.time() - t < 180]
        if len(recientes) >= 2:
            errores.append(f"{proveedor}: fallo hace poco (se reintenta en 3 min)")
            continue
        try:
            r = fn()
            _fallos.pop((capacidad, proveedor), None)
            return r
        except Exception as e:  # noqa: BLE001
            _fallos[(capacidad, proveedor)] = recientes + [time.time()]
            errores.append(f"{proveedor}: {str(e)[:140]}")
            log(f"    {proveedor} no disponible ({str(e)[:90]})")
    raise SinIA("; ".join(errores) or "sin proveedores configurados")


def _ordenar(capacidad, intentos):
    orden = cfg().get(capacidad, {}).get("orden", [])
    return sorted(intentos, key=lambda x: orden.index(x[0]) if x[0] in orden else 99)


# ============================================================= IMAGEN
def imagen(prompt: str, destino: Path, ancho=1024, alto=1024, semilla=0, negativo="", log=print) -> Path:
    c = cfg().get("imagen", {})
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    ancho, alto = int(ancho) // 64 * 64, int(alto) // 64 * 64

    def hf_space():
        ult = None
        for sp in c.get("spaces", []):
            try:
                fs = espacios.llamar(sp, {"prompt": prompt, "negativo": negativo or None, "semilla": semilla, "aleatoria": False,
                                          "ancho": ancho, "alto": alto, "pasos": 4 if "schnell" in sp.lower() or "turbo" in sp.lower() else None},
                                     "image", ("infer", "generate", "predict", "run"), (".png", ".webp", ".jpg", ".jpeg"), log)
                return _a_png(fs[0], destino)
            except Exception as e:  # noqa: BLE001
                ult = e
                log(f"    {sp}: {str(e)[:80]}")
        raise ult or SinIA("sin spaces")

    def pollinations():
        key = config.secret("POLLINATIONS_API_KEY")
        q = {"model": c.get("pollinations_model", "flux"), "width": ancho, "height": alto, "seed": semilla, "nologo": "true"}
        if key:
            q["key"] = key
        url = f"https://gen.pollinations.ai/image/{urllib.parse.quote(prompt)}?{urllib.parse.urlencode(q)}"
        datos, tipo = _http(url, headers={"Authorization": f"Bearer {key}"} if key else None)
        if "image" not in tipo and not datos[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"RIFF"):
            raise SinIA(datos[:120].decode(errors="ignore"))
        tmp = destino.with_suffix(".tmp")
        tmp.write_bytes(datos)
        return _a_png(tmp, destino, borrar=True)

    def hf_inference():
        token = config.secret("HF_TOKEN")
        if not token:
            raise SinIA("falta HF_TOKEN")
        from huggingface_hub import InferenceClient
        img = InferenceClient(token=token).text_to_image(prompt, model=c.get("hf_inference_model"), width=ancho, height=alto,
                                                         negative_prompt=negativo or None)
        img.save(destino)
        return destino

    def local():
        from ..generators import local as L
        return L.imagen(c.get("local_model", "stabilityai/sdxl-turbo"), prompt, destino, max(ancho, alto))

    def replicate():
        from ..generators import cloud
        return cloud.imagen(config.get()["imagen"]["cloud_model"], prompt, destino, "16:9" if ancho > alto else "1:1")

    log(f"  IA imagen: {prompt[:90]}")
    return _probar("imagen", _ordenar("imagen", [("hf_space", hf_space), ("pollinations", pollinations),
                                                   ("hf_inference", hf_inference), ("local", local), ("replicate", replicate)]), log)


def _a_png(origen: Path, destino: Path, borrar=False) -> Path:
    from PIL import Image
    Image.open(origen).convert("RGBA" if destino.suffix == ".png" else "RGB").save(destino)
    if borrar:
        Path(origen).unlink(missing_ok=True)
    return destino


# ============================================================= 3D
def modelo3d(prompt: str | None, destino: Path, imagen_ref: Path | None = None, semilla=0, log=print) -> Path:
    c = cfg().get("modelo3d", {})
    destino = Path(destino)

    def hf_space():
        ult = None
        for sp in c.get("spaces", []):
            try:
                datos = {"prompt": None if imagen_ref else prompt, "imagen": imagen_ref, "semilla": semilla or 1234,
                         "aleatoria": False, "quitar_fondo": True}
                fs = espacios.llamar(sp, datos, "model3d", ("generation_all", "generate", "image_to_3d", "run", "predict"),
                                     (".glb", ".gltf", ".obj"), log)
                glbs = [f for f in fs if f.suffix.lower() in (".glb", ".gltf")] or fs
                elegido = next((f for f in glbs if "textur" in f.name.lower()), glbs[-1])
                shutil.copy(elegido, destino.with_suffix(elegido.suffix))
                return destino.with_suffix(elegido.suffix)
            except Exception as e:  # noqa: BLE001
                ult = e
                log(f"    {sp}: {str(e)[:80]}")
        raise ult or SinIA("sin spaces 3D")

    def replicate():
        from ..generators import cloud
        if not imagen_ref:
            raise SinIA("replicate necesita imagen de referencia")
        return cloud.malla_desde_imagen(config.get()["malla3d"]["cloud_model"], imagen_ref, destino)

    log("  IA 3D: " + (f"imagen {Path(imagen_ref).name}" if imagen_ref else (prompt or "")[:80]))
    return _probar("modelo3d", _ordenar("modelo3d", [("hf_space", hf_space), ("replicate", replicate)]), log)


# ============================================================= AUDIO
def _audio(capacidad, prompt, destino, duracion, letra=None, log=print):
    c = cfg().get(capacidad, {})
    destino = Path(destino)

    def hf_space():
        ult = None
        for sp in c.get("spaces", []):
            try:
                fs = espacios.llamar(sp, {"prompt": prompt, "duracion": duracion, "letra": letra or ("[instrumental]" if capacidad == "musica" else None),
                                          "semilla": 0, "aleatoria": True},
                                     "audio", ("generate", "text2music", "predict", "infer", "run"), (".wav", ".mp3", ".ogg", ".flac"), log)
                destino.parent.mkdir(parents=True, exist_ok=True)
                final = destino.with_suffix(fs[0].suffix.lower())
                shutil.copy(fs[0], final)
                return final
            except Exception as e:  # noqa: BLE001
                ult = e
                log(f"    {sp}: {str(e)[:80]}")
        raise ult or SinIA("sin spaces de audio")

    def local():
        from ..generators import local as L
        if capacidad == "musica":
            return L.musica(c.get("local_model"), prompt, destino.with_suffix(".wav"), duracion)
        return L.sfx_stable_audio(c.get("local_model"), prompt, destino.with_suffix(".wav"), duracion)

    log(f"  IA {capacidad}: {prompt[:90]}")
    return _probar(capacidad, _ordenar(capacidad, [("hf_space", hf_space), ("local", local)]), log)


def sfx(prompt: str, destino: Path, duracion=2.5, log=print) -> Path:
    return _audio("sfx", prompt, destino, duracion, log=log)


def musica(prompt: str, destino: Path, duracion=45, letra=None, log=print) -> Path:
    return _audio("musica", prompt, destino, duracion, letra, log)


# ============================================================= TEXTO (LLM)
def texto(sistema: str, usuario: str, log=print, json_mode=False, max_tokens=3000) -> str:
    c = cfg().get("texto", {})

    def ollama():
        url = config.get()["director"].get("ollama_url", "http://127.0.0.1:11434")
        body = {"model": c.get("ollama_model", "qwen2.5-coder:7b"), "stream": False,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
        if json_mode:
            body["format"] = "json"
        datos, _ = _http(url + "/api/chat", body, timeout=600)
        return json.loads(datos)["message"]["content"]

    def pollinations():
        key = config.secret("POLLINATIONS_API_KEY")
        q = {"model": c.get("pollinations_model", "openai"), "system": sistema}
        if json_mode:
            q["json"] = "true"
        if key:
            q["key"] = key
        url = f"https://gen.pollinations.ai/text/{urllib.parse.quote(usuario[:6000])}?{urllib.parse.urlencode(q)}"
        datos, _ = _http(url, headers={"Authorization": f"Bearer {key}"} if key else None)
        return datos.decode("utf-8", errors="ignore")

    def hf_inference():
        token = config.secret("HF_TOKEN")
        if not token:
            raise SinIA("falta HF_TOKEN")
        from huggingface_hub import InferenceClient
        r = InferenceClient(token=token).chat_completion(
            [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            model=c.get("hf_inference_model"), max_tokens=max_tokens)
        return r.choices[0].message.content

    def anthropic():
        key = config.secret("ANTHROPIC_API_KEY")
        if not key:
            raise SinIA("falta ANTHROPIC_API_KEY")
        body = {"model": c.get("anthropic_model", "claude-haiku-5-5"), "max_tokens": max_tokens, "system": sistema,
                "messages": [{"role": "user", "content": usuario}]}
        datos, _ = _http("https://api.anthropic.com/v1/messages", body,
                         {"x-api-key": key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in json.loads(datos)["content"])

    return _probar("texto", _ordenar("texto", [("ollama", ollama), ("pollinations", pollinations),
                                                 ("hf_inference", hf_inference), ("anthropic", anthropic)]), log)


def texto_json(sistema: str, usuario: str, log=print):
    import re
    crudo = texto(sistema + "\nResponde SOLO con JSON valido.", usuario, log, json_mode=True)
    m = re.search(r"(\{.*\}|\[.*\])", crudo, re.S)
    if not m:
        raise SinIA("el LLM no devolvio JSON")
    return json.loads(m.group(1))


# ============================================================= diagnostico
def probar_conexiones(log=print) -> dict:
    """Prueba rapida (sin generar nada pesado) de cada proveedor."""
    res = {}
    try:
        import gradio_client  # noqa: F401
        res["gradio_client"] = "instalado"
    except ImportError:
        res["gradio_client"] = "FALTA: ejecuta INSTALAR.bat"
    for cap in ("imagen", "modelo3d", "sfx", "musica"):
        for sp in cfg().get(cap, {}).get("spaces", [])[:2]:
            try:
                espacios._api(sp)
                res[f"{cap}: {sp}"] = "ok"
            except Exception as e:  # noqa: BLE001
                res[f"{cap}: {sp}"] = f"no responde ({str(e)[:60]})"
    res["HF_TOKEN"] = "configurado" if config.secret("HF_TOKEN") else "sin token (cuota GPU anonima, mas baja)"
    res["POLLINATIONS_API_KEY"] = "configurada" if config.secret("POLLINATIONS_API_KEY") else "sin clave"
    try:
        _http(config.get()["director"].get("ollama_url", "http://127.0.0.1:11434") + "/api/tags", timeout=3)
        res["ollama"] = "ok"
    except Exception:  # noqa: BLE001
        res["ollama"] = "no esta corriendo"
    return res
