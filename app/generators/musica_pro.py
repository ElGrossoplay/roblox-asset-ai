"""Compositor musical procedural por generos (estereo, loop perfecto, stems opcionales).

Cada genero define tempo, escala, progresiones, patrones de bateria, instrumentos y mezcla.
La melodia se construye con motivos (frase A, variacion A', frase B) sobre notas del acorde,
el bajo sigue la fundamental y la bateria usa patrones de 16 pasos con swing y redobles.
"""
from pathlib import Path

import numpy as np

from . import dsp
from .dsp import SR, env_adsr, env_exp, filtro, fm, n_muestras, osc, ruido

ESCALAS = {
    "mayor": [0, 2, 4, 5, 7, 9, 11], "menor_natural": [0, 2, 3, 5, 7, 8, 10],
    "menor_armonica": [0, 2, 3, 5, 7, 8, 11], "dorica": [0, 2, 3, 5, 7, 9, 10],
    "frigia": [0, 1, 3, 5, 7, 8, 10], "mayor_pentatonica": [0, 2, 4, 7, 9], "mixolidia": [0, 2, 4, 5, 7, 9, 10],
}

# patrones de 16 pasos: X acento, x normal, g fantasma, r redoble (tresillo de hi-hat)
GENEROS = {
    "lofi": {"bpm": (72, 86), "escala": "dorica", "raiz": 50, "swing": 0.58,
             "prog": [[0, 3, 6, 2], [1, 4, 0, 0], [0, 5, 3, 4]], "siete": True,
             "bateria": {"kick": "x.......x.x.....", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.xg"},
             "kit": "lofi", "acordes": "epiano", "bajo": "sine", "melodia": "campana", "arpegio": None,
             "densidad": 0.35, "reverb": 0.22, "lofi": True},
    "chiptune": {"bpm": (132, 150), "escala": "mayor", "raiz": 60, "swing": 0.5,
                 "prog": [[0, 4, 5, 3], [0, 5, 3, 4], [5, 3, 0, 4]], "siete": False,
                 "bateria": {"kick": "x...x...x...x...", "snare": "....x.......x...", "hat": "..x...x...x...x."},
                 "kit": "chip", "acordes": None, "bajo": "tri", "melodia": "pulso", "arpegio": "pulso_arp",
                 "densidad": 0.7, "reverb": 0.05},
    "synthwave": {"bpm": (94, 108), "escala": "menor_natural", "raiz": 45, "swing": 0.5,
                  "prog": [[0, 5, 2, 6], [0, 6, 5, 4], [5, 3, 0, 4]], "siete": False,
                  "bateria": {"kick": "x...x...x...x...", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."},
                  "kit": "eighties", "acordes": "pad", "bajo": "bajo_saw8", "melodia": "lead_saw", "arpegio": "arp_saw",
                  "densidad": 0.5, "reverb": 0.3},
    "edm": {"bpm": (122, 128), "escala": "menor_natural", "raiz": 45, "swing": 0.5,
            "prog": [[5, 3, 0, 4], [0, 5, 2, 6], [3, 4, 0, 0]], "siete": False,
            "bateria": {"kick": "x...x...x...x...", "clap": "....x.......x...", "ohat": "..x...x...x...x.", "hat": "xxxxxxxxxxxxxxxx"},
            "kit": "edm", "acordes": "supersaw", "bajo": "sub_offbeat", "melodia": "pluck_lead", "arpegio": None,
            "densidad": 0.6, "reverb": 0.22, "sidechain": 0.7},
    "trap": {"bpm": (136, 146), "escala": "menor_armonica", "raiz": 45, "swing": 0.5,
             "prog": [[0, 0, 5, 4], [0, 3, 5, 4], [0, 5, 3, 6]], "siete": False,
             "bateria": {"kick": "x.....x...x.....", "snare": "........X.......", "hat": "x.x.x.x.x.xrx.x.r"[:16]},
             "kit": "trap", "acordes": "pad_oscuro", "bajo": "808", "melodia": "campana", "arpegio": None,
             "densidad": 0.4, "reverb": 0.2},
    "orquestal": {"bpm": (82, 98), "escala": "menor_natural", "raiz": 50, "swing": 0.5,
                  "prog": [[0, 5, 2, 6], [0, 3, 4, 0], [5, 6, 0, 0]], "siete": False,
                  "bateria": {"timpani": "x.......x.......", "tom": "..............xx"},
                  "kit": "orquesta", "acordes": "cuerdas", "bajo": "cello", "melodia": "metales", "arpegio": "arpa",
                  "densidad": 0.4, "reverb": 0.4},
    "terror": {"bpm": (60, 70), "escala": "menor_armonica", "raiz": 38, "swing": 0.5,
               "prog": [[0, 0, 1, 0], [0, 5, 1, 0]], "siete": False,
               "bateria": {"latido": "x..x............"},
               "kit": "terror", "acordes": "dron", "bajo": None, "melodia": "caja_musical", "arpegio": None,
               "densidad": 0.12, "reverb": 0.55, "golpes": True},
    "acustico": {"bpm": (88, 100), "escala": "mayor", "raiz": 55, "swing": 0.54,
                 "prog": [[0, 4, 5, 3], [0, 3, 0, 4], [5, 3, 0, 4]], "siete": False,
                 "bateria": {"kick": "x.......x.......", "rim": "....x.......x...", "shaker": "xgxgxgxgxgxgxgxg"},
                 "kit": "acustico", "acordes": "guitarra", "bajo": "bajo_pluck", "melodia": "marimba", "arpegio": None,
                 "densidad": 0.45, "reverb": 0.2},
    "reggaeton": {"bpm": (88, 96), "escala": "menor_natural", "raiz": 45, "swing": 0.5,
                  "prog": [[0, 5, 2, 6], [5, 3, 0, 4]], "siete": False,
                  "bateria": {"kick": "x...x...x...x...", "snare": "...x..x....x..x.", "hat": "x.x.x.x.x.x.x.x."},
                  "kit": "urbano", "acordes": "pluck_acordes", "bajo": "sub_kick", "melodia": "pluck_lead", "arpegio": None,
                  "densidad": 0.5, "reverb": 0.18},
    "tropical": {"bpm": (100, 112), "escala": "mayor_pentatonica", "raiz": 57, "swing": 0.5,
                 "prog": [[0, 4, 5, 3], [0, 3, 4, 4]], "siete": False,
                 "bateria": {"kick": "x...x...x...x...", "clap": "....x.......x...", "shaker": "xgxgxgxgxgxgxgxg", "conga": "..x..x....x..x.."},
                 "kit": "tropical", "acordes": "marimba_acordes", "bajo": "bajo_pluck", "melodia": "steel", "arpegio": None,
                 "densidad": 0.55, "reverb": 0.2},
    "rock": {"bpm": (112, 138), "escala": "menor_natural", "raiz": 40, "swing": 0.5,
             "prog": [[0, 5, 6, 0], [0, 3, 5, 4], [0, 6, 5, 6]], "siete": False,
             "bateria": {"kick": "x.....x.x.......", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
             "kit": "rock", "acordes": "power", "bajo": "bajo_saw8", "melodia": "lead_dist", "arpegio": None,
             "densidad": 0.45, "reverb": 0.15},
}

PALABRAS_GENERO = [
    ("lofi", ["lofi", "lo-fi", "chill", "estudiar", "relax"]),
    ("chiptune", ["chiptune", "8bit", "8-bit", "retro", "arcade", "pixel", "nes"]),
    ("trap", ["trap", "808", "hip hop", "hiphop", "drill"]),
    ("reggaeton", ["reggaeton", "reggaetón", "dembow", "perreo", "urbano"]),
    ("rock", ["rock", "metal", "guitarra electrica", "punk"]),
    ("edm", ["edm", "electronica", "electrónica", "house", "dance", "techno", "cyberpunk"]),
    ("synthwave", ["synthwave", "synth", "80s", "outrun", "space", "espacio", "galax", "sci-fi", "scifi", "neon"]),
    ("terror", ["terror", "horror", "miedo", "dark ambient", "drone", "creepy", "suspenso"]),
    ("orquestal", ["orquest", "orchestral", "epic", "épic", "fantasy", "fantasia", "medieval", "batalla", "jefe", "boss"]),
    ("tropical", ["tropical", "steel drum", "playa", "isla", "caribe", "verano", "ukulele"]),
    ("acustico", ["acoustic", "acustic", "acústic", "folk", "cozy", "acogedor", "granja", "music box", "winter", "invierno", "navidad", "western", "desert", "bosque"]),
]


def detectar_genero(texto: str, defecto="acustico") -> str:
    t = (texto or "").lower()
    for g, ws in PALABRAS_GENERO:
        if any(w in t for w in ws):
            return g
    return defecto


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ============================================================= instrumentos (mono)
def _ks(f, dur, brillo=0.5, decay=0.996, rng=None):
    """Karplus-Strong vectorizado por bloques (cuerda pulsada)."""
    rng = rng or np.random.default_rng(int(f))
    P = max(2, int(SR / f))
    n = n_muestras(dur)
    bloque = filtro(rng.uniform(-1, 1, P * 4), "lp", 1500 + 9000 * brillo)[:P]
    out = np.empty(n + P)
    i = 0
    while i < n:
        out[i:i + P] = bloque
        bloque = 0.5 * (bloque + np.roll(bloque, -1)) * decay ** (P / 100)
        i += P
    return out[:n] * env_adsr(n, 0.001, 0.0, 1.0, 0.02)


def _saws(f, n, voces=5, detune=0.012):
    off = np.linspace(-detune, detune, voces)
    return sum(osc(f * (1 + d), n=n, forma="saw", fase0=k * 0.13) for k, d in enumerate(off)) / voces


def inst(nombre, f, dur, vel=1.0, rng=None):
    n = n_muestras(dur)
    tt = np.arange(n) / SR
    if nombre == "epiano":
        n2 = n_muestras(dur + 0.6)
        e = env_exp(n2, 1.6 + dur, 0.003)
        x = fm(f, 1.0, 1.8, n=n2, env_indice=env_exp(n2, 0.5)) * e + fm(f * 4, 1.0, 0.4, n=n2) * env_exp(n2, 0.15) * 0.15
        return x * vel * 0.5
    if nombre in ("campana", "caja_musical"):
        n2 = n_muestras(dur + (1.2 if nombre == "campana" else 0.8))
        r = 3.5 if nombre == "campana" else 5.0
        x = fm(f, r, 1.2, n=n2, env_indice=env_exp(n2, 0.4)) * env_exp(n2, 1.4, 0.002)
        return x * vel * 0.45
    if nombre in ("pad", "pad_oscuro", "supersaw"):
        a, r, fc = {"pad": (0.35, 0.5, 2200), "pad_oscuro": (0.5, 0.6, 1100), "supersaw": (0.01, 0.15, 4500)}[nombre]
        n2 = n_muestras(dur + r)
        x = filtro(_saws(f, n2, 7, 0.015), "lp", fc, 0.9)
        return x * env_adsr(n2, a, 0.2, 0.8, r) * vel * 0.35
    if nombre == "cuerdas":
        n2 = n_muestras(dur + 0.6)
        tt2 = np.arange(n2) / SR
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * tt2) * np.clip(tt2 - 0.3, 0, 1)
        x = filtro(sum(osc(f * vib * (1 + d), n=n2, forma="saw") for d in (-0.006, 0, 0.007)) / 3, "lp", 2600, 0.7)
        return x * env_adsr(n2, 0.25, 0.3, 0.85, 0.5) * vel * 0.4
    if nombre == "cello":
        return inst("cuerdas", f, dur, vel, rng) * 1.3
    if nombre == "metales":
        n2 = n_muestras(dur + 0.25)
        tt2 = np.arange(n2) / SR
        vib = 1 + 0.005 * np.sin(2 * np.pi * 5.5 * tt2) * np.clip(tt2 - 0.25, 0, 1)
        x = osc(f * vib, n=n2, forma="saw") * 0.7 + osc(f * vib * 1.003, n=n2, forma="square") * 0.3
        brillo = filtro(x, "lp", 3000, 1.0)
        oscuro = filtro(x, "lp", 700, 0.8)
        mezcla = np.clip(tt2 / 0.12, 0, 1)
        return (oscuro * (1 - mezcla) + brillo * mezcla) * env_adsr(n2, 0.06, 0.2, 0.8, 0.25) * vel * 0.45
    if nombre in ("arpa", "guitarra", "pluck_acordes", "bajo_pluck"):
        brillo = {"arpa": 0.6, "guitarra": 0.45, "pluck_acordes": 0.7, "bajo_pluck": 0.3}[nombre]
        return _ks(f, dur + 0.8, brillo, 0.997, rng) * vel * 0.6
    if nombre == "pluck_lead":
        n2 = n_muestras(dur + 0.3)
        x = filtro(_saws(f, n2, 3, 0.008), "lp", 3500, 1.2) * env_exp(n2, 0.45 + dur, 0.002)
        return x * vel * 0.5
    if nombre == "lead_saw":
        n2 = n_muestras(dur + 0.2)
        tt2 = np.arange(n2) / SR
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.8 * tt2) * np.clip(tt2 - 0.15, 0, 1)
        x = filtro(_saws(f * vib, n2, 3, 0.006), "lp", 3200, 1.1)
        return x * env_adsr(n2, 0.01, 0.15, 0.75, 0.2) * vel * 0.4
    if nombre == "lead_dist":
        n2 = n_muestras(dur + 0.2)
        tt2 = np.arange(n2) / SR
        vib = 1 + 0.008 * np.sin(2 * np.pi * 6 * tt2) * np.clip(tt2 - 0.2, 0, 1)
        x = filtro(dsp.saturar(osc(f * vib, n=n2, forma="saw"), 6), "lp", 3800)
        return x * env_adsr(n2, 0.005, 0.1, 0.85, 0.15) * vel * 0.32
    if nombre in ("pulso", "pulso_arp"):
        ancho = 0.25 if nombre == "pulso" else 0.125
        tt2 = tt
        vib = 1 + (0.006 * np.sin(2 * np.pi * 6 * tt2) * np.clip(tt2 - 0.2, 0, 1) if nombre == "pulso" else 0)
        return osc(f * vib, n=n, forma="square", ancho=ancho) * env_adsr(n, 0.002, 0.05, 0.8, 0.02) * vel * 0.28
    if nombre == "tri":
        return osc(f, n=n, forma="tri") * env_adsr(n, 0.002, 0.02, 0.9, 0.02) * vel * 0.6
    if nombre == "arp_saw":
        n2 = n_muestras(dur + 0.1)
        return filtro(osc(f, n=n2, forma="saw"), "lp", 2600, 1.4) * env_exp(n2, 0.35, 0.002) * vel * 0.35
    if nombre in ("marimba", "marimba_acordes"):
        n2 = n_muestras(min(dur, 0.6) + 0.6)
        x = osc(f, n=n2) * env_exp(n2, 0.9) + osc(f * 4, n=n2) * env_exp(n2, 0.12) * 0.25 + osc(f * 9.9, n=n2) * env_exp(n2, 0.03) * 0.1
        return x * vel * 0.55
    if nombre == "steel":
        n2 = n_muestras(dur + 0.6)
        tt2 = np.arange(n2) / SR
        bend = 1 + 0.02 * np.exp(-tt2 / 0.02)
        x = sum(osc(f * k * bend, n=n2) * a * env_exp(n2, d) for k, a, d in ((1, 1, 1.0), (2.0, 0.5, 0.6), (3.01, 0.25, 0.35), (4.1, 0.1, 0.2)))
        return x * vel * 0.45
    if nombre == "power":
        n2 = n_muestras(dur + 0.05)
        x = sum(osc(f * k * (1 + d), n=n2, forma="saw") for k, d in ((1, 0), (1.4983, 0.002), (2, -0.002)))
        return filtro(dsp.saturar(x, 7), "lp", 3200) * env_adsr(n2, 0.003, 0.1, 0.8, 0.05) * vel * 0.28
    if nombre == "dron":
        n2 = n_muestras(dur + 1.5)
        tt2 = np.arange(n2) / SR
        x = sum(osc(f * k * (1 + 0.003 * np.sin(2 * np.pi * 0.11 * tt2 + k)), n=n2, forma="saw") for k in (0.5, 1.0, 1.0595))
        return filtro(x, "lp", 700, 1.5) * env_adsr(n2, 1.2, 0.5, 0.9, 1.5) * vel * 0.3
    # ---------------- bajos
    if nombre == "sine":
        return osc(f, n=n) * env_adsr(n, 0.005, 0.1, 0.85, 0.05) * vel * 0.8
    if nombre in ("bajo_saw8", "sub_offbeat", "sub_kick"):
        x = filtro(osc(f, n=n, forma="saw"), "lp", 800 if nombre == "bajo_saw8" else 300, 1.2) * 0.6 + osc(f, n=n) * 0.6
        return x * env_adsr(n, 0.004, 0.08, 0.8, 0.04) * vel * 0.7
    if nombre == "808":
        n2 = n_muestras(dur + 0.2)
        tt2 = np.arange(n2) / SR
        fr = f * (1 + 1.0 * np.exp(-tt2 / 0.03))
        return dsp.saturar(osc(fr, n=n2) * env_exp(n2, 1.2 + dur, 0.002), 2.0) * vel * 0.8
    return osc(f, n=n) * env_adsr(n, 0.01, 0.1, 0.7, 0.1) * vel * 0.4


# ============================================================= bateria
def drum(nombre, kit, rng):
    if nombre == "kick":
        if kit == "chip":
            n = n_muestras(0.12)
            return osc(np.geomspace(300, 50, n), n=n, forma="tri") * env_exp(n, 0.1, 0.001)
        largo = {"trap": 0.9, "edm": 0.45, "urbano": 0.5}.get(kit, 0.35)
        n = n_muestras(largo)
        cuerpo = osc(np.geomspace(150, 45, n) * (1 if kit != "lofi" else 0.9), n=n) * env_exp(n, largo, 0.001)
        click = filtro(ruido(n, rng), "bp", 3500, 1) * env_exp(n, 0.008, 0.0003) * 0.5
        x = cuerpo + click
        return dsp.saturar(x, 1.5) if kit in ("edm", "urbano", "rock") else x
    if nombre == "snare":
        if kit == "chip":
            n = n_muestras(0.12)
            return dsp.bitcrush(ruido(n, rng) * env_exp(n, 0.1, 0.001) * 2, 4, 4)
        n = n_muestras(0.25)
        tono = osc(np.geomspace(240, 180, n), n=n) * env_exp(n, 0.08, 0.001)
        rui = filtro(ruido(n, rng), "bp", 3500 if kit != "lofi" else 2200, 0.7) * env_exp(n, 0.18, 0.001)
        x = tono * 0.6 + rui * 1.6
        if kit == "eighties":
            x = dsp.reverb(x, 0.9, 0.6, 6000)[: n_muestras(0.8)] * env_adsr(n_muestras(0.8), 0, 0, 1, 0.05) * 1.0
        return x
    if nombre == "clap":
        n = n_muestras(0.3)
        x = np.zeros(n)
        for k, d in enumerate((0, 0.011, 0.022)):
            m = n_muestras(0.2)
            dsp.poner(x, filtro(ruido(m, rng), "bp", 1300, 1.5) * env_exp(m, 0.06 if k < 2 else 0.2, 0.0005), d)
        return x * 1.6
    if nombre in ("hat", "ohat"):
        if kit == "chip":
            n = n_muestras(0.04)
            return dsp.bitcrush(ruido(n, rng) * env_exp(n, 0.03, 0.0005), 4, 2) * 0.5
        d = 0.05 if nombre == "hat" else 0.28
        n = n_muestras(d)
        x = filtro(ruido(n, rng), "hp", 7500, 0.8) * env_exp(n, d, 0.0005)
        return x * (0.55 if nombre == "hat" else 0.6)
    if nombre == "shaker":
        n = n_muestras(0.08)
        return filtro(ruido(n, rng), "bp", 6500, 1.0) * env_adsr(n, 0.015, 0.02, 0.4, 0.03) * 0.5
    if nombre == "rim":
        n = n_muestras(0.06)
        return (filtro(ruido(n, rng), "bp", 1800, 4) + osc(1700, n=n) * 0.3) * env_exp(n, 0.04, 0.0003) * 1.2
    if nombre in ("tom", "conga"):
        n = n_muestras(0.35)
        f0 = 140 if nombre == "tom" else 260
        return osc(np.geomspace(f0 * 1.4, f0, n), n=n) * env_exp(n, 0.3 if nombre == "tom" else 0.18, 0.001)
    if nombre == "timpani":
        n = n_muestras(1.6)
        x = sum(osc(np.geomspace(105, 90, n) * k, n=n) * a for k, a in ((1, 1), (1.5, 0.4), (1.99, 0.25))) * env_exp(n, 1.4, 0.003)
        return x + filtro(ruido(n, rng), "lp", 600) * env_exp(n, 0.1) * 0.4
    if nombre == "latido":
        n = n_muestras(0.25)
        return filtro(osc(np.geomspace(70, 40, n), n=n) * env_exp(n, 0.18, 0.004), "lp", 250) * 1.2
    if nombre == "crash":
        n = n_muestras(2.0)
        return filtro(ruido(n, rng), "hp", 4500) * env_exp(n, 1.8, 0.001) * 0.45
    return np.zeros(10)


class Pista:
    def __init__(self, n, pan=0.0, envio=0.2, gan=1.0):
        self.x = np.zeros(n)
        self.pan, self.envio, self.gan = pan, envio, gan


def _voicing(raiz, grados, escala, prev, siete=False, registro=(52, 70)):
    """Acorde a partir de grados de la escala, con conduccion de voces (inversion mas cercana)."""
    L = len(escala)
    notas = []
    for paso in ((0, 2, 4, 6) if siete else (0, 2, 4)):
        g = grados + paso
        notas.append(raiz + escala[g % L] + 12 * (g // L))
    mejores = []
    for inv in range(len(notas)):
        cand = sorted(notas[inv:] + [m + 12 for m in notas[:inv]])
        for oct_ in (-12, 0, 12):
            c = [m + oct_ for m in cand]
            if registro[0] <= c[0] and c[-1] <= registro[1] + 6:
                mejores.append(c)
    if not mejores:
        return notas
    if prev is None:
        return min(mejores, key=lambda c: abs(np.mean(c) - np.mean(registro)))
    return min(mejores, key=lambda c: sum(abs(a - b) for a, b in zip(c, prev)))


RITMOS = [  # (paso_inicio, duracion_en_pasos) dentro de un compas de 16
    [(0, 3), (4, 2), (6, 2), (8, 4), (12, 4)],
    [(0, 2), (2, 2), (4, 4), (10, 2), (12, 2), (14, 2)],
    [(0, 6), (6, 2), (8, 2), (10, 2), (12, 4)],
    [(2, 2), (4, 2), (6, 2), (8, 6), (14, 2)],
    [(0, 4), (4, 4), (8, 4), (12, 4)],
    [(0, 1), (1, 1), (2, 2), (4, 2), (6, 2), (8, 2), (10, 2), (12, 4)],
]


def _motivo(rng, densidad):
    candidatos = sorted(RITMOS, key=lambda r: abs(len(r) / 8 - densidad * 1.4))
    return candidatos[rng.integers(0, min(3, len(candidatos)))]


def _melodia_compas(rng, ritmo, acorde, escala, raiz, prev, alto=72):
    """Notas: tiempos fuertes = nota del acorde, el resto = pasos de escala cerca de la anterior."""
    pitches = sorted(set(acorde))
    esc_abs = [raiz + e + 12 * o for o in range(-1, 4) for e in escala]
    esc_abs = [m for m in esc_abs if alto - 10 <= m <= alto + 12]
    tonos_acorde = [m for m in esc_abs if (m - raiz) % 12 in {(p - raiz) % 12 for p in pitches}] or esc_abs
    notas = []
    actual = prev or min(tonos_acorde, key=lambda m: abs(m - alto))
    for ini, dur in ritmo:
        if ini % 4 == 0:
            actual = min(tonos_acorde, key=lambda m: abs(m - actual) + rng.uniform(0, 3))
        else:
            idx = min(range(len(esc_abs)), key=lambda i: abs(esc_abs[i] - actual))
            idx = int(np.clip(idx + rng.choice([-2, -1, 1, 1, 2]), 0, len(esc_abs) - 1))
            actual = esc_abs[idx]
        notas.append((ini, dur, actual))
    return notas, actual


def componer(genero: str, duracion: float = 40, semilla: int = 0, bpm=None, escala=None, raiz=None):
    g = GENEROS[genero]
    rng = np.random.default_rng(semilla or 11)
    bpm = float(bpm or rng.uniform(*g["bpm"]))
    escala_n = escala if escala in ESCALAS else g["escala"]
    esc = ESCALAS[escala_n]
    raiz = int(raiz or g["raiz"])
    paso = 60 / bpm / 4  # semicorchea
    seg_compas = paso * 16
    compases = int(max(16 if duracion >= 20 else 8, round(duracion / seg_compas / 4) * 4))
    total = compases * seg_compas
    cola = 3.0
    N = n_muestras(total + cola)
    progA = g["prog"][rng.integers(len(g["prog"]))]
    progB = g["prog"][rng.integers(len(g["prog"]))]
    if len(esc) == 5:  # pentatonica: grados acotados
        progA = [d % 5 for d in progA]
        progB = [d % 5 for d in progB]

    P = {"acordes": Pista(N, -0.15, 0.35, 0.8), "bajo": Pista(N, 0, 0.05, 1.0), "melodia": Pista(N, 0.12, 0.3, 0.85),
         "arpegio": Pista(N, 0.3, 0.3, 0.55), "bateria": Pista(N, 0, 0.12, 1.0), "fx": Pista(N, -0.3, 0.6, 0.6)}
    cache = {}

    def nota(pista, nombre, midi, ini_paso, dur_pasos, vel=1.0, pan_extra=None):
        clave = (nombre, int(midi), int(dur_pasos), round(vel, 1))
        if clave not in cache:
            cache[clave] = inst(nombre, _hz(midi), dur_pasos * paso, round(vel, 1), np.random.default_rng(int(midi) * 7 + 1))
        swing = g["swing"]
        t0 = ini_paso * paso + (paso * (swing - 0.5) * 2 if ini_paso % 2 == 1 else 0)
        t0 += rng.normal(0, 0.004) if pista is not P["bateria"] else 0
        dsp.poner(pista.x, cache[clave] * rng.uniform(0.9, 1.0), max(0, t0))

    tambores = {}

    def golpe(nombre, ini_paso, vel=1.0):
        if nombre not in tambores:
            tambores[nombre] = [drum(nombre, g["kit"], np.random.default_rng(k + 3)) for k in range(3)]
        swing = g["swing"]
        t0 = ini_paso * paso + (paso * (swing - 0.5) * 2 if ini_paso % 2 == 1 else 0)
        dsp.poner(P["bateria"].x, tambores[nombre][rng.integers(3)] * vel, t0)

    tiempos_kick = []
    prev_acorde, prev_mel = None, None
    motivo = _motivo(rng, g["densidad"])
    motivo_b = _motivo(rng, g["densidad"] * 1.2)
    frase_a = None
    for c in range(compases):
        seccion_b = (c // 8) % 2 == 1
        prog = progB if seccion_b else progA
        grado = prog[c % 4]
        acorde = _voicing(raiz + 12, grado, esc, prev_acorde, g.get("siete"))
        prev_acorde = acorde
        base = c * 16
        fundamental = raiz + esc[grado % len(esc)] - 12 + 12 * (grado // len(esc))

        # ---- acordes
        a = g["acordes"]
        if a in ("epiano", "pad", "pad_oscuro", "cuerdas", "dron"):
            for m in acorde if a != "dron" else [acorde[0] - 12, acorde[0] - 11 if rng.random() < 0.5 else acorde[0] - 5]:
                nota(P["acordes"], a, m, base, 16, 0.8)
        elif a == "supersaw":
            for s in (2, 6, 10, 14) if not seccion_b else range(0, 16, 2):
                for m in acorde:
                    nota(P["acordes"], a, m, base + s, 1.5, 0.75)
        elif a in ("guitarra", "pluck_acordes"):
            rasgueo = [0, 3, 6, 8, 10, 12, 14] if a == "guitarra" else [0, 3, 6, 10, 12]
            for s in rasgueo:
                for k, m in enumerate(acorde):
                    nota(P["acordes"], a, m, base + s + k * 0.08, 3, 0.55 if s % 4 else 0.7)
        elif a == "marimba_acordes":
            for s in (0, 3, 6, 10, 12):
                for m in acorde:
                    nota(P["acordes"], "marimba", m, base + s, 2, 0.4)
        elif a == "power":
            for s in range(0, 16, 2):
                nota(P["acordes"], "power", fundamental + 12, base + s, 1.8, 0.8 if s % 4 == 0 else 0.6)

        # ---- bajo
        b = g["bajo"]
        if b in ("sine", "cello"):
            nota(P["bajo"], b, fundamental, base, 8, 0.9)
            nota(P["bajo"], b, fundamental + (7 if b == "sine" else 0), base + 8, 8, 0.8)
        elif b == "bajo_saw8":
            for s in range(0, 16, 2):
                nota(P["bajo"], b, fundamental + (12 if s % 4 == 2 and g["kit"] == "eighties" else 0), base + s, 1.8, 0.85)
        elif b == "tri":
            for s in range(0, 16, 2):
                nota(P["bajo"], b, fundamental + (12 if s % 4 == 2 else 0), base + s, 1.8, 0.9)
        elif b == "sub_offbeat":
            for s in (2, 6, 10, 14):
                nota(P["bajo"], b, fundamental, base + s, 1.8, 0.9)
        elif b == "sub_kick":
            for s in (0, 3, 6, 8, 11, 14):
                nota(P["bajo"], b, fundamental, base + s, 2, 0.85)
        elif b == "808":
            for s in (0, 6, 10) if c % 2 == 0 else (0, 10):
                nota(P["bajo"], b, fundamental, base + s, 5, 0.9)
        elif b == "bajo_pluck":
            for s in (0, 6, 8, 14):
                nota(P["bajo"], b, fundamental + (7 if s == 14 else 0), base + s, 3, 0.8)

        # ---- melodia (motivo A, variacion A', frase B)
        mel = g["melodia"]
        if mel and not (genero == "terror" and rng.random() > 0.35):
            ritmo = motivo_b if seccion_b else motivo
            alto = 74 + (3 if seccion_b else 0) if mel != "caja_musical" else 84
            if c % 8 in (2, 3, 6) and frase_a and not seccion_b:  # repite la idea (memorable)
                notas_m = [(i, d, m + (acorde[0] - frase_a[1])) for i, d, m in frase_a[0]]
                if c % 8 == 6:
                    notas_m = notas_m[:-1]
            else:
                notas_m, prev_mel = _melodia_compas(rng, ritmo, acorde, esc, raiz, prev_mel, alto)
                if c % 8 in (0, 1) and not seccion_b:
                    frase_a = (notas_m, acorde[0])
            descanso = (c % 8 == 7)  # respira al final de la frase
            for ini, d, m in notas_m:
                if descanso and ini > 8:
                    continue
                nota(P["melodia"], mel, m, base + ini, d, 0.85 if ini % 4 == 0 else 0.7)

        # ---- arpegio
        arp = g["arpegio"]
        if arp and (seccion_b or arp in ("arpa", "pulso_arp")):
            orden = acorde + [acorde[0] + 12]
            for s in range(0, 16, 1 if arp != "arpa" else 2):
                m = orden[(s // (1 if arp != "arpa" else 2)) % len(orden)] + (12 if arp == "arp_saw" else 0)
                nota(P["arpegio"], arp, m, base + s, 1 if arp != "arpa" else 3, 0.6)

        # ---- bateria
        intro = c == 0 and genero not in ("chiptune", "rock")
        for pieza, patron in g["bateria"].items():
            if intro and pieza not in ("hat", "shaker", "timpani", "latido"):
                continue
            for s, ch in enumerate(patron):
                if ch == ".":
                    continue
                vel = {"X": 1.0, "x": 0.85, "g": 0.35, "r": 0.6}.get(ch, 0.8) * rng.uniform(0.9, 1.0)
                if ch == "r":  # redoble en tresillos
                    for k in range(3):
                        golpe(pieza, base + s + k / 3, vel * 0.8)
                    continue
                golpe(pieza, base + s, vel)
                if pieza == "kick":
                    tiempos_kick.append((base + s) * paso)
        if c % 8 == 7 and g["kit"] not in ("terror",):  # redoble al final de cada frase
            pieza = "tom" if g["kit"] in ("orquesta", "rock", "acustico", "tropical") else ("snare" if "snare" in g["bateria"] else "clap" if "clap" in g["bateria"] else None)
            if pieza:
                for k, s in enumerate((12, 13, 14, 15)):
                    golpe(pieza, base + s, 0.5 + k * 0.12)
        if c % 8 == 0 and g["kit"] in ("rock", "eighties", "edm", "orquesta"):
            golpe("crash", base, 0.8)

        # ---- golpes atmosfericos (terror)
        if g.get("golpes") and rng.random() < 0.4:
            m = n_muestras(3.0)
            f = rng.uniform(80, 300)
            hit = fm(f, rng.uniform(1.3, 3.7), 3.0, n=m, env_indice=env_exp(m, 1.5)) * env_exp(m, 2.5, 0.002) * 0.5
            dsp.poner(P["fx"].x, hit, base * paso + rng.uniform(0, seg_compas))

    # ---------------------------------------------------------- mezcla
    if g.get("sidechain"):
        env = np.ones(N)
        lon = n_muestras(0.18)
        curva = 1 - g["sidechain"] * np.exp(-np.arange(lon) / (0.05 * SR))
        for tk in tiempos_kick:
            i = int(tk * SR)
            j = min(N, i + lon)
            env[i:j] = np.minimum(env[i:j], curva[: j - i])
        P["acordes"].x *= env
        P["bajo"].x *= env
    P["bajo"].x = filtro(P["bajo"].x, "lp", 1800)
    P["acordes"].x = filtro(P["acordes"].x, "hp", 180)
    P["melodia"].x = filtro(P["melodia"].x, "hp", 250)
    if g["arpegio"] in ("arp_saw", "pulso_arp"):
        P["arpegio"].x = dsp.delay(P["arpegio"].x, paso * 3, 0.35, 0.35, 4)[:N]

    estereo = np.zeros((N, 2))
    envio = np.zeros(N)
    stems = {}
    for nombre_p, pista in P.items():
        if not np.any(pista.x):
            continue
        st = dsp.panear(pista.x * pista.gan, pista.pan)
        stems[nombre_p] = st
        estereo += st
        envio += pista.x * pista.gan * pista.envio
    # reverb estereo (dos respuestas distintas = amplitud)
    tiempo_rev = 1.4 + g["reverb"] * 3
    for canal, sem in ((0, 5), (1, 9)):
        ir = dsp.impulso(tiempo_rev, 5500, np.random.default_rng(sem))
        estereo[:, canal] += dsp.conv_fft(envio, ir)[:N] * g["reverb"] * 1.4

    # loop perfecto: la cola despues del final vuelve al inicio
    L = n_muestras(total)
    final = estereo[:L].copy()
    resto = estereo[L:]
    final[: len(resto)] += resto

    if g.get("lofi"):
        tt = np.arange(L) / SR
        wow = tt + 0.0018 * np.sin(2 * np.pi * 0.5 * tt)
        for ch in range(2):
            final[:, ch] = filtro(np.interp(wow * SR, np.arange(L), final[:, ch]), "lp", 4800)
        crackle = np.zeros(L)
        r2 = np.random.default_rng(1)
        idx = r2.integers(0, L, int(total * 12))
        crackle[idx] = r2.uniform(-0.25, 0.25, len(idx))
        final += (filtro(crackle, "hp", 1500) + ruido(L, r2, "rosa") * 0.01)[:, None]
    for ch in range(2):
        final[:, ch] = filtro(final[:, ch], "hp", 28)
    final = dsp.limitador(dsp.normalizar(dsp.saturar(final * 0.9, 1.2), -0.8), 0.85)
    info = {"genero": genero, "bpm": round(bpm), "escala": escala_n, "compases": compases, "segundos": round(total, 1)}
    return final, {k: v[:L] for k, v in stems.items()}, info


def generar(cfg: dict, destino: Path, duracion: float = 40, semilla: int = 0, genero: str | None = None,
            stems_dir: Path | None = None) -> tuple:
    texto = " ".join(str(cfg.get(k, "")) for k in ("genero", "prompt"))
    genero = genero if genero in GENEROS else (cfg.get("genero") if cfg.get("genero") in GENEROS else detectar_genero(texto))
    audio, stems, info = componer(genero, duracion, semilla, cfg.get("bpm_forzado"), cfg.get("escala_forzada"))
    dsp.guardar_wav(destino, audio, normal=False)
    if stems_dir:
        for k, v in stems.items():
            dsp.guardar_wav(Path(stems_dir) / f"{k}.wav", v)
    return destino, info
