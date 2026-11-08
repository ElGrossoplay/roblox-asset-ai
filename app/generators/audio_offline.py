"""Sintesis procedural de efectos de sonido y musica (solo numpy).

No necesita internet ni GPU. Los resultados son WAV 44.1 kHz mono,
formato que Roblox acepta para subir como Audio.
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100


def guardar_wav(path: Path, audio: np.ndarray, sr: int = SR) -> Path:
    audio = np.asarray(audio, dtype=np.float64)
    pico = np.max(np.abs(audio)) or 1.0
    audio = audio / pico * 0.89
    datos = (audio * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(datos.tobytes())
    return path


# ------------------------------------------------------------- utilidades
def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _env(n, a=0.005, r=None, curva=4.0):
    """Envolvente ataque + caida exponencial."""
    t = np.arange(n) / SR
    dur = n / SR
    r = r if r is not None else dur
    att = np.clip(t / max(a, 1e-4), 0, 1)
    dec = np.exp(-curva * t / max(r, 1e-4))
    return att * dec


def _ruido(n, rng):
    return rng.uniform(-1, 1, n)


def _lowpass(x, alpha):
    """Filtro pasa-bajos de un polo (alpha 0..1, menor = mas oscuro)."""
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def _lp_rapido(x, ventana):
    ventana = max(1, int(ventana))
    k = np.ones(ventana) / ventana
    return np.convolve(x, k, mode="same")


def _sweep(f0, f1, dur, forma="sin"):
    t = _t(dur)
    f = np.geomspace(max(f0, 1), max(f1, 1), len(t))
    fase = 2 * np.pi * np.cumsum(f) / SR
    if forma == "square":
        return np.sign(np.sin(fase))
    if forma == "saw":
        return 2 * ((fase / (2 * np.pi)) % 1) - 1
    return np.sin(fase)


# ------------------------------------------------------------- efectos
def _moneda(rng):
    a = _sweep(988, 988, 0.08, "square") * 0.6
    b = _sweep(1319, 1319, 0.35, "square")
    b *= _env(len(b), r=0.25)
    return np.concatenate([a, b])


def _salto(rng):
    x = _sweep(220, 880, 0.25, "square")
    return x * _env(len(x), r=0.3, curva=2)


def _click(rng):
    x = _sweep(1800, 900, 0.04) + 0.3 * _ruido(int(SR * 0.04), rng)
    return x * _env(len(x), a=0.001, r=0.02)


def _powerup(rng):
    partes = []
    for i, f in enumerate([523, 659, 784, 1047, 1319]):
        s = _sweep(f, f * 1.02, 0.09, "square") * (0.6 + i * 0.1)
        partes.append(s * _env(len(s), r=0.12, curva=1.5))
    return np.concatenate(partes)


def _explosion(rng):
    n = int(SR * 1.6)
    x = _lp_rapido(_ruido(n, rng), 18) * 3 + 0.6 * _sweep(90, 30, 1.6)
    return x * _env(n, a=0.002, r=0.7, curva=3)


def _laser(rng):
    x = _sweep(1600, 180, 0.28, "saw")
    return x * _env(len(x), a=0.001, r=0.3, curva=3)


def _golpe(rng):
    n = int(SR * 0.6)
    x = _sweep(120, 40, 0.6) + 0.4 * _lp_rapido(_ruido(n, rng), 30)
    return x * _env(n, a=0.001, r=0.25, curva=5)


def _pasos(rng, brillo=10):
    sil = int(SR * 0.42)
    partes = []
    for _ in range(4):
        n = int(SR * 0.08)
        p = _lp_rapido(_ruido(n, rng), brillo) * _env(n, a=0.002, r=0.05, curva=6)
        partes += [p, np.zeros(sil - n)]
    return np.concatenate(partes)


def _puerta(rng):
    t = _t(1.4)
    f = 180 + 60 * np.sin(2 * np.pi * 0.7 * t) + 30 * rng.standard_normal(len(t)).cumsum() / 400
    fase = 2 * np.pi * np.cumsum(f) / SR
    x = np.sign(np.sin(fase)) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 11 * t)))
    x = _lp_rapido(x, 6)
    return x * np.clip(t * 4, 0, 1) * np.clip((1.4 - t) * 3, 0, 1)


def _latido(rng):
    def golpe(d):
        return _sweep(70, 45, d) * _env(int(SR * d), a=0.003, r=0.08, curva=6)
    pulso = np.concatenate([golpe(0.15), np.zeros(int(SR * 0.12)), golpe(0.15) * 0.7, np.zeros(int(SR * 0.55))])
    return np.tile(pulso, 2)


def _viento(rng, dur=4.0, tono=0.02):
    n = int(SR * dur)
    x = _lowpass(_ruido(n, rng), tono)
    mod = 0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * _t(dur) + rng.uniform(0, 6))
    return x * mod * np.clip(_t(dur) * 2, 0, 1) * np.clip((dur - _t(dur)) * 2, 0, 1)


def _grito(rng):
    t = _t(1.8)
    f = 700 + 250 * np.sin(2 * np.pi * 0.8 * t) + 40 * np.sin(2 * np.pi * 6 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x = _lp_rapido(x, 4) * np.clip(t * 3, 0, 1) * np.exp(-1.5 * t)
    eco = np.zeros_like(x)
    d = int(SR * 0.25)
    eco[d:] = x[:-d] * 0.5
    return x * 0.6 + eco


def _olas(rng):
    dur = 6.0
    n = int(SR * dur)
    x = _lowpass(_ruido(n, rng), 0.08)
    mod = (0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * _t(dur) - np.pi / 2)) ** 2
    return x * mod


def _chapuzon(rng):
    n = int(SR * 0.7)
    x = _lp_rapido(_ruido(n, rng), 4) * _env(n, a=0.003, r=0.35, curva=4)
    burbujas = sum(_sweep(f, f * 1.6, 0.7) * _env(n, a=0.01, r=0.1, curva=8) * 0.2
                   for f in rng.uniform(400, 900, 5))
    return x + burbujas


def _teleport(rng):
    t = _t(0.9)
    x = np.sin(2 * np.pi * np.cumsum(300 + 1500 * t + 200 * np.sin(2 * np.pi * 25 * t)) / SR)
    return x * np.sin(np.pi * t / 0.9)


def _alarma(rng):
    partes = [_sweep(660, 880, 0.35, "square"), _sweep(880, 660, 0.35, "square")]
    return _lp_rapido(np.tile(np.concatenate(partes), 3), 3)


def _espada(rng):
    n = int(SR * 0.45)
    x = _ruido(n, rng)
    x = x - _lp_rapido(x, 6)
    swish = np.sin(np.pi * np.arange(n) / n) ** 3
    shing = _sweep(2400, 2300, 0.45) * _env(n, a=0.05, r=0.4, curva=3) * 0.3
    return x * swish + shing


def _hechizo(rng):
    t = _t(1.2)
    x = sum(np.sin(2 * np.pi * f * t * (1 + 0.3 * t)) * 0.3 for f in (660, 990, 1320))
    brillo = _ruido(len(t), rng) * (rng.random(len(t)) > 0.995)
    return (x + brillo * 2) * np.sin(np.pi * t / 1.2)


def _campana(rng):
    t = _t(2.0)
    x = sum(a * np.sin(2 * np.pi * 880 * r * t) * np.exp(-d * t)
            for a, r, d in [(1, 1, 2), (0.6, 2.76, 3), (0.4, 5.4, 5), (0.2, 8.9, 7)])
    return x


def _hielo(rng):
    partes = []
    for _ in range(6):
        n = int(SR * rng.uniform(0.02, 0.06))
        p = (_ruido(n, rng) - _lp_rapido(_ruido(n, rng), 4)) * _env(n, a=0.001, r=0.02, curva=6)
        partes += [p, np.zeros(int(SR * rng.uniform(0.01, 0.08)))]
    return np.concatenate(partes)


def _glitch(rng):
    partes = []
    for _ in range(10):
        d = rng.uniform(0.02, 0.07)
        f = rng.uniform(200, 2000)
        partes.append(_sweep(f, f * rng.uniform(0.5, 2), d, "square"))
    return np.concatenate(partes) * 0.7


def _disparo(rng):
    n = int(SR * 0.8)
    x = _ruido(n, rng) * _env(n, a=0.0005, r=0.12, curva=6) + _sweep(150, 50, 0.8) * _env(n, r=0.2, curva=5)
    eco = np.zeros_like(x)
    d = int(SR * 0.18)
    eco[d:] = _lp_rapido(x[:-d], 10) * 0.4
    return x + eco


def _pajaros(rng):
    dur = 5.0
    out = np.zeros(int(SR * dur))
    for _ in range(14):
        ini = int(rng.uniform(0, dur - 0.3) * SR)
        d = rng.uniform(0.06, 0.18)
        f0 = rng.uniform(2500, 4500)
        c = _sweep(f0, f0 * rng.uniform(0.7, 1.4), d) * np.sin(np.pi * np.arange(int(SR * d)) / int(SR * d))
        out[ini:ini + len(c)] += c * rng.uniform(0.3, 1)
    return out + 0.05 * _viento(rng, dur, 0.01)


SFX = {
    "moneda": _moneda, "salto": _salto, "click": _click, "powerup": _powerup,
    "explosion": _explosion, "laser": _laser, "golpe_sordo": _golpe, "pasos": _pasos,
    "puerta_crujido": _puerta, "latido": _latido, "susurro_viento": lambda r: _viento(r, 5, 0.03),
    "grito_lejano": _grito, "olas": _olas, "chapuzon": _chapuzon, "teletransporte": _teleport,
    "alarma": _alarma, "espada": _espada, "hechizo": _hechizo, "pasos_nieve": lambda r: _pasos(r, 3),
    "viento": _viento, "campana": _campana, "hielo_romper": _hielo, "glitch": _glitch,
    "disparo": _disparo, "pajaros": _pajaros,
}


def generar_sfx(nombre: str, destino: Path, semilla: int = 0) -> Path:
    rng = np.random.default_rng(semilla or abs(hash(nombre)) % 2**32)
    fn = SFX.get(nombre)
    if fn is None:  # nombre desconocido: elige por palabras clave
        for clave, f in SFX.items():
            if clave.split("_")[0] in nombre:
                fn = f
                break
        else:
            fn = _click
    return guardar_wav(destino, fn(rng))


# ------------------------------------------------------------- musica
ESCALAS = {
    "mayor": [0, 2, 4, 5, 7, 9, 11],
    "menor_natural": [0, 2, 3, 5, 7, 8, 10],
    "menor_armonica": [0, 2, 3, 5, 7, 8, 11],
    "dorica": [0, 2, 3, 5, 7, 9, 10],
    "frigia": [0, 1, 3, 5, 7, 8, 10],
    "mayor_pentatonica": [0, 2, 4, 7, 9],
}
PROGRESIONES = {
    "mayor": [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 4]],
    "menor": [[0, 5, 2, 6], [0, 3, 4, 0], [0, 6, 5, 4]],
}


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _nota(f, dur, onda, vel=1.0):
    t = _t(dur)
    n = len(t)
    if onda == "pad":
        x = sum(np.sin(2 * np.pi * f * d * t) for d in (1, 1.003, 0.997, 2.001)) / 3
        env = np.clip(t / 0.4, 0, 1) * np.clip((dur - t) / 0.4, 0, 1)
    elif onda == "synth":
        x = 2 * ((f * t) % 1) - 1 + 0.5 * (2 * ((f * 1.007 * t) % 1) - 1)
        x = _lp_rapido(x, 6)
        env = _env(n, a=0.01, r=dur, curva=2.5)
    elif onda == "campana":
        x = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-6 * t)
        env = _env(n, a=0.002, r=dur, curva=4)
    else:  # pluck (cuerda Karplus-Strong simplificada)
        periodo = max(2, int(SR / f))
        buf = np.random.default_rng(int(f)).uniform(-1, 1, periodo)
        x = np.empty(n)
        for i in range(n):
            x[i] = buf[i % periodo]
            buf[i % periodo] = 0.996 * 0.5 * (buf[i % periodo] + buf[(i + 1) % periodo])
        env = np.clip((dur - t) / 0.02, 0, 1)
    return x * env * vel


def _bombo(rng):
    return _sweep(150, 45, 0.25) * _env(int(SR * 0.25), a=0.001, r=0.12, curva=4)


def _caja(rng):
    n = int(SR * 0.18)
    return (_ruido(n, rng) * 0.7 + _sweep(220, 180, 0.18) * 0.3) * _env(n, a=0.001, r=0.08, curva=5)


def _hihat(rng):
    n = int(SR * 0.05)
    x = _ruido(n, rng)
    return (x - _lp_rapido(x, 3)) * _env(n, a=0.0005, r=0.03, curva=6) * 0.5


def _poner(pista, sonido, inicio):
    i = int(inicio * SR)
    if i >= len(pista):
        return
    f = min(len(pista), i + len(sonido))
    pista[i:f] += sonido[: f - i]


def generar_musica(cfg: dict, destino: Path, duracion: float = 30, semilla: int = 0) -> Path:
    """Loop musical: pad de acordes + bajo + melodia/arpegio + bateria."""
    rng = np.random.default_rng(semilla or 7)
    bpm = float(cfg.get("bpm", 90))
    escala = ESCALAS.get(cfg.get("escala", "mayor"), ESCALAS["mayor"])
    raiz = int(cfg.get("raiz", 57))
    onda = cfg.get("onda", "pluck")
    beat = 60.0 / bpm
    compas = 4 * beat
    n_compases = max(4, int(round(duracion / compas / 4)) * 4)
    total = n_compases * compas
    pista = np.zeros(int(SR * total) + SR)

    tipo = "menor" if escala[2] == 3 else "mayor"
    prog = PROGRESIONES[tipo][rng.integers(len(PROGRESIONES[tipo]))]

    def grado(g, octava=0):
        g = g % len(escala) if len(escala) == 7 else g
        oct_extra, idx = divmod(g, len(escala))
        return raiz + escala[idx] + 12 * (octava + oct_extra)

    for c in range(n_compases):
        g = prog[c % len(prog)] if len(escala) == 7 else [0, 3, 1, 2][c % 4]
        t0 = c * compas
        acorde = [grado(g), grado(g + 2), grado(g + 4)]
        for m in acorde:  # pad
            _poner(pista, _nota(_hz(m - 12), compas, "pad", 0.18), t0)
        for b in range(4):  # bajo
            _poner(pista, _nota(_hz(grado(g) - 24), beat * 0.9, "synth", 0.35 if b % 2 == 0 else 0.25), t0 + b * beat)
        # melodia / arpegio en corcheas
        for s in range(8):
            if rng.random() < 0.72:
                m = acorde[s % 3] + 12 if rng.random() < 0.6 else grado(g + rng.integers(0, 7), 1)
                _poner(pista, _nota(_hz(m), beat * 0.6, onda, 0.28), t0 + s * beat / 2)
        if cfg.get("drums", True):
            for b in range(4):
                if b in (0, 2):
                    _poner(pista, _bombo(rng) * 0.8, t0 + b * beat)
                else:
                    _poner(pista, _caja(rng) * 0.45, t0 + b * beat)
                for h in range(2):
                    _poner(pista, _hihat(rng) * (0.5 if h else 0.3), t0 + b * beat + h * beat / 2)

    pista = pista[: int(SR * total)]
    # reverb muy simple (ecos difusos)
    rev = np.zeros_like(pista)
    for d, g in [(0.031, 0.3), (0.047, 0.25), (0.089, 0.2), (0.137, 0.15)]:
        k = int(SR * d)
        rev[k:] += pista[:-k] * g
    mezcla = pista + rev
    return guardar_wav(destino, np.tanh(mezcla * 1.2))


# =====================================================================
#  v2: los motores nuevos reemplazan a los de arriba (que quedan como respaldo)
# =====================================================================
_sfx_v1, _musica_v1 = generar_sfx, generar_musica


def generar_sfx(nombre: str, destino: Path, semilla: int = 0, mods: dict | None = None) -> Path:  # noqa: F811
    try:
        from . import sfx_pro
        return sfx_pro.generar(nombre, destino, semilla, mods)
    except Exception:  # noqa: BLE001
        return _sfx_v1(nombre, destino, semilla)


def generar_musica(cfg: dict, destino: Path, duracion: float = 30, semilla: int = 0,  # noqa: F811
                   genero: str | None = None, stems_dir: Path | None = None) -> Path:
    try:
        from . import musica_pro
        ruta, info = musica_pro.generar(cfg, destino, duracion, semilla, genero, stems_dir)
        cfg["_info"] = info
        return ruta
    except Exception:  # noqa: BLE001
        return _musica_v1(cfg, destino, duracion, semilla)
