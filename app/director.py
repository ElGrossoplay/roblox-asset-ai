"""Director de estilo: convierte un tema ("isla tropical de terror") en un
"style pack" coherente que guia a todos los generadores.

Backends:
  offline   -> elige el preset mas parecido (sin internet)
  anthropic -> Claude ajusta el preset al tema exacto
  ollama    -> un LLM local (los modelos quedan en .\\models\\ollama)
Si la IA falla, se usa el resultado offline.
"""
import copy
import json
import re
import unicodedata
import urllib.request

from . import config, presets

SFX_DESCRIPCION = {
    "moneda": "coin pickup chime", "salto": "cartoon jump", "click": "UI button click",
    "powerup": "power-up rising sparkle", "explosion": "explosion boom", "laser": "laser shot",
    "golpe_sordo": "dull heavy impact", "pasos": "footsteps on ground", "puerta_crujido": "creaking wooden door",
    "latido": "heartbeat", "susurro_viento": "eerie wind whisper", "grito_lejano": "distant scream echo",
    "olas": "ocean waves", "chapuzon": "water splash", "teletransporte": "sci-fi teleport",
    "alarma": "sci-fi alarm", "espada": "sword swing", "hechizo": "magic spell cast",
    "pasos_nieve": "footsteps on snow", "viento": "wind ambience", "campana": "bell ding",
    "hielo_romper": "ice cracking", "glitch": "digital glitch", "disparo": "gunshot western",
    "pajaros": "birds chirping ambience",
}


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t[:40] or "pack"


def _offline(tema: str) -> dict:
    nombre = presets.elegir(tema)
    p = copy.deepcopy(presets.PRESETS[nombre])
    p.pop("keywords", None)
    p["tema"] = tema
    p["preset_base"] = nombre
    p["sfx"] = [{"nombre": s, "prompt": f"{SFX_DESCRIPCION.get(s, s)}, {p['mood']}, roblox game sound effect"}
                for s in p["sfx"]]
    p["texturas"] = [{"nombre": t, "prompt": f"seamless tileable {t.replace('_', ' ')} texture, {tema}, stylized game art, top-down, no shadows"}
                     for t in p["texturas"]]
    p["props"] = [{"nombre": pr, "prompt": f"low poly stylized {pr.replace('_', ' ')}, {tema}, game asset, white background"}
                  for pr in p["props"]]
    p["skybox_prompt"] = f"360 panoramic sky, {tema}, {p['mood']}, stylized"
    p["musica"]["prompt"] = f"{p['musica']['prompt']}, theme: {tema}"
    return p


SYSTEM = """Eres director de arte y sonido para juegos de Roblox.
Recibes un tema y un style pack JSON base. Devuelve SOLO un JSON con la MISMA
estructura y claves, ajustando valores al tema: mood, paleta (5 hex), cielo,
lighting, atmosphere, color_correction, bloom, sunrays, musica (bpm 60-140,
escala en [mayor, menor_natural, menor_armonica, dorica, frigia, mayor_pentatonica],
onda en [pad, pluck, synth, campana], drums bool, prompt en ingles),
sfx/texturas/props (listas de {nombre, prompt}; nombres snake_case en espanol,
prompts en ingles) y skybox_prompt. Para sfx usa preferentemente estos nombres:
""" + ", ".join(SFX_DESCRIPCION) + """.
Los valores de lighting deben ser validos para Roblox (ClockTime 0-24, Brightness 0-5,
FogEnd en studs). No agregues texto fuera del JSON."""


def _pedir_llm(tema: str, base: dict) -> str:
    cfg = config.get()["director"]
    user = f"Tema: {tema}\n\nStyle pack base:\n{json.dumps(base, ensure_ascii=False)}"
    if cfg["backend"] == "anthropic":
        key = config.secret("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Falta ANTHROPIC_API_KEY en config/secrets.env")
        body = {"model": cfg.get("anthropic_model", "claude-haiku-5-5"), "max_tokens": 4000,
                "system": SYSTEM, "messages": [{"role": "user", "content": user}]}
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data["content"])
    if cfg["backend"] == "ollama":
        body = {"model": cfg.get("ollama_model", "llama3.2"), "stream": False, "format": "json",
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
        req = urllib.request.Request(cfg.get("ollama_url", "http://127.0.0.1:11434") + "/api/chat",
                                     data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["message"]["content"]
    from .ia import motor
    if motor.disponible():
        return motor.texto(SYSTEM, user, lambda *_: None, json_mode=True)
    raise RuntimeError("backend offline")


def _fusionar(base: dict, ia: dict) -> dict:
    """Toma de la IA solo claves conocidas y con el tipo correcto."""
    out = copy.deepcopy(base)
    for k, v in ia.items():
        if k not in base:
            continue
        if isinstance(base[k], dict) and isinstance(v, dict):
            out[k] = {**base[k], **{kk: vv for kk, vv in v.items() if kk in base[k] or k == "lighting"}}
        elif isinstance(base[k], list) and isinstance(v, list) and v:
            if k == "paleta":
                v = [c for c in v if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c)]
                if len(v) >= 3:
                    out[k] = v[:5]
            elif all(isinstance(i, dict) and "nombre" in i for i in v):
                out[k] = [{**i, "nombre": slug(str(i["nombre"]))} for i in v][:8]
            else:
                out[k] = v
        elif type(base[k]) is type(v):
            out[k] = v
    return out


def crear_style_pack(tema: str, log=print) -> dict:
    base = _offline(tema)
    backend = config.get()["director"]["backend"]
    from .ia import motor
    if backend == "offline" and motor.disponible():
        backend = "ia"
    if backend != "offline":
        try:
            log(f"Director: consultando IA ({backend})...")
            texto = _pedir_llm(tema, base)
            m = re.search(r"\{.*\}", texto, re.S)
            base = _fusionar(base, json.loads(m.group(0)))
            base["director"] = backend
        except Exception as e:  # noqa: BLE001
            log(f"Director IA fallo ({e}); uso preset offline '{base['preset_base']}'.")
            base["director"] = "offline"
    else:
        base["director"] = "offline"
    base["nombre"] = slug(tema)
    return base
