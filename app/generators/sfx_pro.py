"""Efectos de sonido por capas (transitorio + cuerpo + cola), con variaciones y modificadores.

Modificadores (se detectan en el prompt o vienen en opciones):
  tono   : "grave" 0.75 / "agudo" 1.3       dur   : "corto" 0.6 / "largo" 1.6
  retro  : "8bit", "retro", "arcade"         eco   : "eco", "cueva", "reverb"
  suave  : "suave" / "fuerte"
"""
from pathlib import Path

import numpy as np

from . import dsp
from .dsp import SR, env_adsr, env_exp, filtro, filtro_barrido, n_muestras, osc, ruido, fm


def _nota(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _cat(*xs):
    return np.concatenate(xs)


def _mix(*capas):
    n = max(len(c) for c in capas)
    out = np.zeros(n)
    for c in capas:
        out[:len(c)] += c
    return out


def _sil(seg):
    return np.zeros(n_muestras(seg))


# ============================================================= UI
def click(r, p):
    n = n_muestras(0.05)
    tic = filtro(ruido(n, r), "bp", 3500 * p["tono"], 2.5) * env_exp(n, 0.02, 0.0005)
    cuerpo = osc(1400 * p["tono"], n=n) * env_exp(n, 0.03, 0.0005) * 0.5
    return tic * 2 + cuerpo


def hover(r, p):
    n = n_muestras(0.04)
    return osc(2200 * p["tono"], n=n) * env_exp(n, 0.025, 0.002) * 0.4


def confirmar(r, p):
    a = osc(_nota(76) * p["tono"], 0.08, "square", ancho=0.3) * env_exp(n_muestras(0.08), 0.08)
    b = osc(_nota(83) * p["tono"], 0.22, "square", ancho=0.3) * env_exp(n_muestras(0.22), 0.2)
    return filtro(_cat(a, b), "lp", 5000) * 0.6


def error(r, p):
    n = n_muestras(0.32)
    a = osc(150 * p["tono"], n=n, forma="square") + osc(156 * p["tono"], n=n, forma="square")
    return filtro(a, "lp", 1800) * env_adsr(n, 0.005, 0.05, 0.7, 0.08) * 0.35


def notificacion(r, p):
    def campana(m, d):
        n = n_muestras(d)
        return fm(_nota(m) * p["tono"], 3.5, 2.0, n=n, env_indice=env_exp(n, 0.3)) * env_exp(n, d)
    return _mix(campana(84, 0.9), _cat(_sil(0.11), campana(91, 1.1)) * 0.8)


def abrir_menu(r, p):
    n = n_muestras(0.22)
    return filtro_barrido(ruido(n, r, "rosa"), "bp", 400, 4000 * p["tono"], 1.5) * env_adsr(n, 0.05, 0.1, 0.5, 0.08)


def cerrar_menu(r, p):
    n = n_muestras(0.2)
    return filtro_barrido(ruido(n, r, "rosa"), "bp", 3500 * p["tono"], 350, 1.5) * env_adsr(n, 0.02, 0.1, 0.5, 0.08)


def moneda(r, p):
    t1, t2 = _nota(83) * p["tono"], _nota(88) * p["tono"]
    a = osc(t1, 0.07, "square", ancho=0.25) * 0.6 * env_adsr(n_muestras(0.07), 0.002, 0.02, 0.9, 0.004)
    n = n_muestras(0.45)
    b = osc(t2, n=n, forma="square", ancho=0.25) * env_exp(n, 0.38, 0.003)
    brillo = fm(t2 * 2, 1.41, 1.5, n=n) * env_exp(n, 0.25) * 0.2
    return filtro(_cat(a, b + brillo), "lp", 7000)


def gema(r, p):
    out = np.zeros(n_muestras(1.0))
    for i, m in enumerate((88, 92, 95, 100)):
        n = n_muestras(0.7)
        s = fm(_nota(m) * p["tono"], 2.0, 1.2, n=n, env_indice=env_exp(n, 0.2)) * env_exp(n, 0.6)
        dsp.poner(out, s * (0.9 - i * 0.12), i * 0.055)
    return out


def compra(r, p):
    n = n_muestras(0.8)
    ding = fm(_nota(91) * p["tono"], 3.0, 2.5, n=n, env_indice=env_exp(n, 0.2)) * env_exp(n, 0.7)
    monedas = np.zeros(n)
    for i in range(7):
        m = n_muestras(0.05)
        tic = filtro(ruido(m, r), "bp", r.uniform(4000, 8000), 6) * env_exp(m, 0.04, 0.0005)
        dsp.poner(monedas, tic * r.uniform(0.4, 1), 0.08 + i * r.uniform(0.03, 0.06))
    return ding * 0.7 + monedas * 1.4


def powerup(r, p):
    out = np.zeros(n_muestras(0.75))
    for i, m in enumerate((72, 76, 79, 84, 88, 91)):
        n = n_muestras(0.16)
        s = (osc(_nota(m) * p["tono"], n=n, forma="square", ancho=0.4) + osc(_nota(m) * 1.006 * p["tono"], n=n, forma="square", ancho=0.4)) * 0.5
        dsp.poner(out, filtro(s, "lp", 6000) * env_adsr(n, 0.003, 0.05, 0.6, 0.05), i * 0.075)
    return out


def subir_nivel(r, p):
    out = np.zeros(n_muestras(1.6))
    for i, m in enumerate((67, 72, 76, 79)):
        n = n_muestras(0.35 if i < 3 else 1.1)
        s = sum(osc(_nota(m + o) * p["tono"], n=n, forma="saw") for o in (0, 12)) * 0.35
        s = filtro(s, "lp", 3500) * env_adsr(n, 0.01, 0.1, 0.7, 0.2 if i < 3 else 0.6)
        dsp.poner(out, s, i * 0.12)
    n = len(out)
    out += fm(_nota(96) * p["tono"], 3.5, 1.5, n=n) * env_exp(n, 1.2) * 0.15 * (np.arange(n) > 0.36 * SR)
    return out


def victoria(r, p):
    melodia = [(72, .12), (72, .12), (72, .12), (72, .36), (68, .36), (70, .36), (72, .2), (70, .1), (72, .9)]
    out, tt = np.zeros(n_muestras(3.2)), 0.0
    for m, d in melodia:
        n = n_muestras(d + 0.15)
        s = (osc(_nota(m) * p["tono"], n=n, forma="square", ancho=0.35) * 0.5 + osc(_nota(m - 12) * p["tono"], n=n, forma="tri") * 0.4)
        dsp.poner(out, filtro(s, "lp", 5000) * env_adsr(n, 0.005, 0.05, 0.75, 0.12), tt)
        tt += d
    return out


def derrota(r, p):
    out, tt = np.zeros(n_muestras(2.4)), 0.0
    for m, d in ((67, .3), (66, .3), (65, .3), (64, 1.2)):
        n = n_muestras(d + 0.1)
        vib = 1 + 0.012 * np.sin(2 * np.pi * 5.5 * np.arange(n) / SR) * (d > 1)
        s = osc(_nota(m) * vib * p["tono"], n=n, forma="saw")
        dsp.poner(out, filtro(s, "lp", 1400, 1.2) * env_adsr(n, 0.02, 0.1, 0.8, 0.15) * 0.6, tt)
        tt += d
    return out


# ============================================================= juego
def salto(r, p):
    n = n_muestras(0.28 * p["dur"])
    f = np.geomspace(180, 620, n) * p["tono"]
    s = osc(f, n=n, forma="square", ancho=0.35) * 0.5 + osc(f * 0.5, n=n) * 0.5
    return filtro(s, "lp", 4500) * env_adsr(n, 0.005, 0.1, 0.6, 0.12)


def aterrizaje(r, p):
    n = n_muestras(0.35)
    golpe = osc(np.geomspace(110, 45, n) * p["tono"], n=n) * env_exp(n, 0.2, 0.001)
    polvo = filtro(ruido(n, r, "rosa"), "lp", 1500) * env_exp(n, 0.25, 0.002) * 0.6
    return golpe + polvo


SUPERFICIES = {"tierra": (900, 0.06, 1.0), "pasto": (2500, 0.09, 0.7), "madera": (700, 0.05, 1.2), "piedra": (2200, 0.04, 1.3),
               "nieve": (1800, 0.12, 0.6), "metal": (3000, 0.05, 1.0), "arena": (3500, 0.1, 0.5)}


def pasos(r, p, superficie="tierra"):
    fc, dur, golpe_g = SUPERFICIES.get(superficie, SUPERFICIES["tierra"])
    out = np.zeros(n_muestras(1.9))
    for i in range(4):
        n = n_muestras(dur)
        talon = osc(np.geomspace(140, 60, n) * p["tono"], n=n) * env_exp(n, dur * 0.6, 0.001) * golpe_g * 0.6
        roce = filtro(ruido(n, r, "rosa"), "bp", fc * r.uniform(0.85, 1.15) * p["tono"], 0.9) * env_exp(n, dur * 0.8, 0.003)
        if superficie == "metal":
            roce += fm(r.uniform(900, 1300), 2.7, 1.5, n=n) * env_exp(n, 0.08) * 0.3
        if superficie == "madera":
            roce += osc(r.uniform(180, 240), n=n) * env_exp(n, 0.06) * 0.5
        dsp.poner(out, (talon + roce) * r.uniform(0.7, 1.0), 0.01 + i * 0.47 + r.uniform(0, 0.03))
    return out


def golpe(r, p):
    n = n_muestras(0.35)
    cuerpo = osc(np.geomspace(160, 50, n) * p["tono"], n=n) * env_exp(n, 0.18, 0.001)
    chasquido = filtro(ruido(n, r), "bp", 2500, 1.2) * env_exp(n, 0.03, 0.0005)
    return dsp.saturar(cuerpo * 1.2 + chasquido * 1.5, 1.8)


def golpe_sordo(r, p):
    n = n_muestras(0.7)
    return filtro(osc(np.geomspace(90, 35, n) * p["tono"], n=n) * env_exp(n, 0.4, 0.002)
                  + filtro(ruido(n, r, "marron"), "lp", 400) * env_exp(n, 0.3) * 0.8, "lp", 900)


def espada(r, p):
    n = n_muestras(0.5)
    whoosh = filtro_barrido(ruido(n, r, "rosa"), "bp", 600, 3500, 1.6) * np.sin(np.pi * np.arange(n) / n) ** 2
    anillo = sum(fm(f * p["tono"], 1.0, 0.3, n=n) * a for f, a in ((2850, 1), (4120, 0.6), (5300, 0.3)))
    anillo *= env_exp(n, 0.45, 0.06) * 0.18
    return whoosh + anillo


def hechizo(r, p):
    n = n_muestras(1.2)
    subida = filtro_barrido(ruido(n, r, "rosa"), "bp", 300, 6000 * p["tono"], 3) * env_adsr(n, 0.4, 0.2, 0.6, 0.4) * 0.8
    brillos = np.zeros(n)
    for _ in range(22):
        m = n_muestras(0.25)
        f = r.uniform(1500, 4500) * p["tono"]
        dsp.poner(brillos, fm(f, 2.0, 1.0, n=m) * env_exp(m, 0.2) * r.uniform(0.1, 0.3), r.uniform(0, 1.0))
    return subida + brillos


def explosion(r, p):
    n = n_muestras(2.4 * p["dur"])
    crack = filtro(ruido(n, r), "hp", 1500) * env_exp(n, 0.08, 0.0003) * 1.4
    boom = osc(np.geomspace(85, 28, n) * p["tono"], n=n) * env_exp(n, 1.0, 0.002) * 1.6
    cuerpo = filtro_barrido(ruido(n, r, "marron"), "lp", 3000, 150, 0.8) * env_exp(n, 1.8, 0.004) * 1.5
    escombros = np.zeros(n)
    for _ in range(18):
        m = n_muestras(0.06)
        dsp.poner(escombros, filtro(ruido(m, r), "bp", r.uniform(800, 3000), 3) * env_exp(m, 0.05) * r.uniform(0.1, 0.4), r.uniform(0.2, 1.6))
    return dsp.saturar(crack + boom + cuerpo + escombros, 1.6)


def disparo(r, p):
    n = n_muestras(0.9)
    crack = ruido(n, r) * env_exp(n, 0.06, 0.0002) * 1.5
    cuerpo = osc(np.geomspace(220, 60, n) * p["tono"], n=n) * env_exp(n, 0.15, 0.0005)
    cola = filtro(ruido(n, r, "rosa"), "lp", 1200) * env_exp(n, 0.6, 0.01) * 0.4
    return dsp.saturar(crack + cuerpo + cola, 2)


def laser(r, p):
    n = n_muestras(0.3 * p["dur"])
    f = np.geomspace(2400, 220, n) * p["tono"]
    s = osc(f, n=n, forma="saw") * 0.5 + osc(f * 1.5, n=n, forma="square", ancho=0.2) * 0.3
    return filtro_barrido(s, "lp", 9000, 1200, 2) * env_exp(n, 0.3, 0.001)


def recarga(r, p):
    out = np.zeros(n_muestras(0.7))
    for tt, f in ((0.0, 2500), (0.12, 1800), (0.45, 3000), (0.52, 2200)):
        m = n_muestras(0.05)
        tic = filtro(ruido(m, r), "bp", f * p["tono"], 4) * env_exp(m, 0.04, 0.0003)
        dsp.poner(out, tic + osc(f / 6, n=m) * env_exp(m, 0.03) * 0.4, tt)
    return out


def dano(r, p):
    n = n_muestras(0.35)
    f0 = np.geomspace(260, 150, n) * p["tono"]
    buzz = osc(f0, n=n, forma="saw")
    voz = sum(filtro(buzz, "bp", fo * p["tono"], 6) * g for fo, g in ((700, 1), (1100, 0.6), (2600, 0.25)))
    return voz * env_adsr(n, 0.01, 0.08, 0.6, 0.12) * 1.5


def curar(r, p):
    out = np.zeros(n_muestras(1.1))
    for i, m in enumerate((79, 83, 86, 91, 95)):
        n = n_muestras(0.6)
        dsp.poner(out, fm(_nota(m) * p["tono"], 1.0, 0.6, n=n) * env_adsr(n, 0.04, 0.2, 0.4, 0.3) * 0.5, i * 0.09)
    n = len(out)
    return out + filtro_barrido(ruido(n, r, "rosa"), "bp", 1500, 7000, 4) * env_adsr(n, 0.3, 0.3, 0.3, 0.4) * 0.3


def teletransporte(r, p):
    n = n_muestras(1.0)
    tt = np.arange(n) / SR
    f = (300 + 1800 * tt) * p["tono"] * (1 + 0.08 * np.sin(2 * np.pi * 22 * tt))
    s = osc(f, n=n, forma="square", ancho=0.3) * 0.4 + osc(f * 1.5, n=n) * 0.3
    return filtro_barrido(s, "lp", 600, 9000, 3) * np.sin(np.pi * tt / tt[-1])


def portal(r, p):
    n = n_muestras(3.0)
    tt = np.arange(n) / SR
    zumbido = sum(osc(f * p["tono"] * (1 + 0.004 * np.sin(2 * np.pi * 0.3 * tt + i)), n=n, forma="saw") for i, f in enumerate((55, 82.5, 110.3)))
    zumbido = filtro(zumbido, "lp", 700, 2) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * tt))
    return zumbido * 0.4 + filtro(ruido(n, r, "rosa"), "bp", 2500, 2) * 0.15


def cofre_abrir(r, p):
    return _mix(puerta_crujido(r, {**p, "dur": 0.5}) * 0.8, _cat(_sil(0.45), gema(r, p)))


def puerta_crujido(r, p):
    n = n_muestras(1.4 * p["dur"])
    tt = np.arange(n) / SR
    f = (170 + 70 * np.sin(2 * np.pi * 0.6 * tt) + 25 * np.cumsum(r.standard_normal(n)) / np.sqrt(n) * 0.2) * p["tono"]
    pulsos = (np.sin(2 * np.pi * np.cumsum(np.maximum(f, 40) / 9) / SR) > 0.6).astype(float)
    s = filtro(osc(f, n=n, forma="saw") * (0.3 + pulsos), "bp", 900, 2.5)
    return s * env_adsr(n, 0.1, 0.2, 0.9, 0.25)


def latido(r, p):
    out = np.zeros(n_muestras(1.9))
    for k, tt in enumerate((0.0, 0.28, 0.95, 1.23)):
        n = n_muestras(0.22)
        g = osc(np.geomspace(75, 40, n) * p["tono"], n=n) * env_exp(n, 0.16, 0.004)
        dsp.poner(out, filtro(g, "lp", 300) * (1 if k % 2 == 0 else 0.7), tt)
    return out


def alarma(r, p):
    n = n_muestras(2.0)
    tt = np.arange(n) / SR
    f = (700 + 250 * np.sign(np.sin(2 * np.pi * 2 * tt))) * p["tono"]
    return filtro(osc(f, n=n, forma="square"), "lp", 2500) * 0.5


def campana(r, p):
    n = n_muestras(2.5)
    return sum(fm(880 * k * p["tono"], 1.4, 1.2, n=n) * env_exp(n, 2.2 / k) * a for k, a in ((1, 1), (2.76, 0.4), (5.4, 0.2)))


def hielo_romper(r, p):
    out = np.zeros(n_muestras(0.9))
    for _ in range(14):
        m = n_muestras(r.uniform(0.01, 0.05))
        c = filtro(ruido(m, r), "hp", 3500) * env_exp(m, 0.03, 0.0003)
        c += fm(r.uniform(2500, 6000) * p["tono"], 1.7, 2, n=m) * env_exp(m, 0.04) * 0.4
        dsp.poner(out, c * r.uniform(0.3, 1), r.uniform(0, 0.5))
    return out


def glitch(r, p):
    partes = []
    for _ in range(12):
        d = r.uniform(0.02, 0.07)
        f = r.uniform(200, 2000) * p["tono"]
        s = osc(np.geomspace(f, f * r.uniform(0.5, 2), n_muestras(d)), d, "square", ancho=r.uniform(0.1, 0.5))
        partes.append(dsp.bitcrush(s, 4, 8) * 0.6 if r.random() < 0.5 else s * 0.5)
    return np.concatenate(partes)


def chapuzon(r, p):
    n = n_muestras(0.9)
    golpe_agua = filtro(ruido(n, r), "lp", 3000) * env_exp(n, 0.3, 0.002)
    burbujas = np.zeros(n)
    for _ in range(10):
        m = n_muestras(0.07)
        f = r.uniform(500, 1400) * p["tono"]
        dsp.poner(burbujas, osc(np.geomspace(f, f * 1.8, m), n=m) * env_adsr(m, 0.005, 0.03, 0.3, 0.02) * 0.3, r.uniform(0.05, 0.7))
    return golpe_agua + burbujas


def grito_lejano(r, p):
    n = n_muestras(1.8)
    tt = np.arange(n) / SR
    f = (650 + 230 * np.sin(2 * np.pi * 0.7 * tt) + 30 * np.sin(2 * np.pi * 6 * tt)) * p["tono"]
    buzz = osc(f, n=n, forma="saw")
    voz = sum(filtro(buzz, "bp", fo, 5) * g for fo, g in ((800, 1), (1200, 0.7), (2800, 0.3)))
    voz = filtro(voz, "lp", 2500) * np.clip(tt * 3, 0, 1) * np.exp(-1.4 * tt)
    return dsp.reverb(voz, 2.5, 0.6, 3000)


# ============================================================= ambientes (loops)
def viento(r, p, dur=6.0):
    n = n_muestras(dur)
    tt = np.arange(n) / SR
    base = ruido(n, r, "rosa")
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.17 * tt + r.uniform(0, 6)) * np.sin(2 * np.pi * 0.07 * tt)
    return filtro_barrido(base, "bp", 300, 900, 1.2) * (0.4 + 0.6 * mod)


def susurro_viento(r, p):
    return filtro(viento(r, p, 5.0), "bp", 1400, 2) * 1.5


def lluvia(r, p, dur=6.0):
    n = n_muestras(dur)
    base = filtro(ruido(n, r, "rosa"), "hp", 900) * 0.35
    gotas = np.zeros(n)
    for _ in range(int(dur * 70)):
        m = n_muestras(0.012)
        dsp.poner(gotas, filtro(ruido(m, r), "bp", r.uniform(2500, 7000), 3) * env_exp(m, 0.01, 0.0002) * r.uniform(0.1, 0.5), r.uniform(0, dur))
    return base + gotas


def fuego(r, p, dur=6.0):
    n = n_muestras(dur)
    rugido = filtro(ruido(n, r, "marron"), "lp", 500) * 0.8
    chispas = np.zeros(n)
    for _ in range(int(dur * 18)):
        m = n_muestras(0.008)
        dsp.poner(chispas, ruido(m, r) * env_exp(m, 0.006, 0.0001) * r.uniform(0.2, 1), r.uniform(0, dur))
    return rugido + filtro(chispas, "hp", 1500) * 1.2


def olas(r, p, dur=8.0):
    n = n_muestras(dur)
    tt = np.arange(n) / SR
    mod = (0.5 + 0.5 * np.sin(2 * np.pi * tt / 4 - np.pi / 2)) ** 2
    return filtro_barrido(ruido(n, r, "rosa"), "lp", 500, 2500, 0.7) * (0.15 + mod)


def rio(r, p, dur=6.0):
    n = n_muestras(dur)
    base = filtro(ruido(n, r, "rosa"), "bp", 1200, 0.8) * 0.6
    burbujas = np.zeros(n)
    for _ in range(int(dur * 25)):
        m = n_muestras(0.04)
        f = r.uniform(600, 1800)
        dsp.poner(burbujas, osc(np.geomspace(f, f * 1.5, m), n=m) * env_adsr(m, 0.003, 0.02, 0.3, 0.015) * r.uniform(0.05, 0.2), r.uniform(0, dur))
    return base + burbujas


def pajaros(r, p, dur=6.0):
    out = np.zeros(n_muestras(dur))
    for _ in range(int(dur * 3)):
        ini = r.uniform(0, dur - 0.5)
        f0 = r.uniform(2500, 4800)
        for k in range(r.integers(1, 5)):
            d = r.uniform(0.05, 0.14)
            m = n_muestras(d)
            c = osc(np.geomspace(f0, f0 * r.uniform(0.7, 1.4), m), n=m) * np.sin(np.pi * np.arange(m) / m)
            dsp.poner(out, c * r.uniform(0.2, 0.6), ini + k * (d + 0.03))
    return out + viento(r, p, dur) * 0.08


def noche(r, p, dur=6.0):
    out = np.zeros(n_muestras(dur))
    for grillo in range(3):
        f = r.uniform(3800, 5200)
        periodo = r.uniform(0.6, 1.1)
        tt = r.uniform(0, 0.5)
        while tt < dur - 0.3:
            for k in range(3):
                m = n_muestras(0.03)
                dsp.poner(out, osc(f, n=m) * env_adsr(m, 0.003, 0.01, 0.6, 0.01) * 0.25, tt + k * 0.045)
            tt += periodo
    return out + filtro(ruido(len(out), r, "rosa"), "lp", 400) * 0.05


def cueva(r, p, dur=6.0):
    out = filtro(ruido(n_muestras(dur), r, "marron"), "lp", 200) * 0.2
    for _ in range(int(dur * 1.5)):
        m = n_muestras(0.08)
        f = r.uniform(900, 2200)
        dsp.poner(out, osc(np.geomspace(f * 1.6, f, m), n=m) * env_exp(m, 0.06, 0.001) * 0.5, r.uniform(0, dur - 0.2))
    return dsp.reverb(out, 3.0, 0.7, 2500)[:len(out)]


def trueno(r, p):
    n = n_muestras(4.0)
    crack = filtro(ruido(n, r), "hp", 800) * env_exp(n, 0.25, 0.001)
    rugido = filtro_barrido(ruido(n, r, "marron"), "lp", 1200, 90, 0.8) * env_adsr(n, 0.2, 1.0, 0.6, 2.0)
    retumbe = rugido * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 1.3 * np.arange(n) / SR)))
    return crack * 0.8 + retumbe * 1.5


RECETAS = {
    # UI
    "click": click, "hover": hover, "confirmar": confirmar, "error": error, "notificacion": notificacion,
    "abrir_menu": abrir_menu, "cerrar_menu": cerrar_menu, "moneda": moneda, "gema": gema, "compra": compra,
    "powerup": powerup, "subir_nivel": subir_nivel, "victoria": victoria, "derrota": derrota,
    # juego
    "salto": salto, "aterrizaje": aterrizaje, "pasos": pasos, "golpe": golpe, "golpe_sordo": golpe_sordo,
    "espada": espada, "hechizo": hechizo, "explosion": explosion, "disparo": disparo, "laser": laser,
    "recarga": recarga, "dano": dano, "curar": curar, "teletransporte": teletransporte, "portal": portal,
    "cofre_abrir": cofre_abrir, "puerta_crujido": puerta_crujido, "latido": latido, "alarma": alarma,
    "campana": campana, "hielo_romper": hielo_romper, "glitch": glitch, "chapuzon": chapuzon, "grito_lejano": grito_lejano,
    "trueno": trueno,
    # ambientes en loop
    "viento": viento, "susurro_viento": susurro_viento, "lluvia": lluvia, "fuego": fuego, "olas": olas, "rio": rio,
    "pajaros": pajaros, "noche": noche, "cueva": cueva,
}
for _s in SUPERFICIES:
    RECETAS[f"pasos_{_s}"] = (lambda s: lambda r, p: pasos(r, p, s))(_s)
AMBIENTES = {"viento", "lluvia", "fuego", "olas", "rio", "pajaros", "noche", "cueva", "portal"}


def modificadores(texto: str) -> dict:
    t = (texto or "").lower()
    p = {"tono": 1.0, "dur": 1.0, "retro": False, "eco": False, "gan": 1.0}
    if any(w in t for w in ("grave", "profundo", "pesado", "deep")):
        p["tono"] = 0.75
    if any(w in t for w in ("agudo", "pequeño", "chillon", "cute", "tierno")):
        p["tono"] = 1.3
    if any(w in t for w in ("corto", "rapido", "rápido")):
        p["dur"] = 0.6
    if any(w in t for w in ("largo", "lento", "epico", "épico")):
        p["dur"] = 1.6
    p["retro"] = any(w in t for w in ("8bit", "8-bit", "retro", "arcade", "chiptune", "pixel"))
    p["eco"] = any(w in t for w in ("eco", "cueva", "reverb", "catedral", "espacio"))
    return p


def _loop_perfecto(x, cruce=0.5):
    """Cruza el final con el inicio para que el ambiente se repita sin salto."""
    k = min(len(x) // 3, n_muestras(cruce))
    inicio, fin = x[:k], x[-k:]
    rampa = np.linspace(0, 1, k)
    cuerpo = x[k:-k].copy() if len(x) > 2 * k else x
    return np.concatenate([fin * (1 - rampa) + inicio * rampa, cuerpo])


def generar(nombre: str, destino: Path, semilla: int = 0, mods: dict | None = None) -> Path:
    receta = RECETAS.get(nombre)
    if receta is None:
        receta = next((f for k, f in RECETAS.items() if k.split("_")[0] in nombre or nombre in k), click)
    r = np.random.default_rng(semilla or (abs(hash(nombre)) % 2**31))
    p = {"tono": 1.0, "dur": 1.0, "retro": False, "eco": False, "gan": 1.0, **(mods or {})}
    p["tono"] *= float(np.exp(r.uniform(-0.04, 0.04)))  # cada variacion suena distinta
    x = np.asarray(receta(r, p), float)
    if p["retro"]:
        x = dsp.bitcrush(dsp.normalizar(x), 5, 6)
    if p["eco"]:
        x = dsp.reverb(dsp.delay(x, 0.18, 0.35, 0.3), 2.4, 0.45)
    elif nombre not in AMBIENTES:
        x = dsp.reverb(x, 0.6, 0.12, 7000)  # "sala" corta: suena menos seco/sintetico
    if nombre in AMBIENTES or nombre.startswith(("viento", "lluvia", "fuego", "olas", "rio", "noche", "cueva")):
        x = _loop_perfecto(x)
    else:
        x = dsp.recortar_silencio(x)
    x = dsp.fundido(dsp.filtro(x, "hp", 30), 0.001, 0.03)
    return dsp.guardar_wav(destino, dsp.limitador(dsp.normalizar(x, -0.5), 0.85))
