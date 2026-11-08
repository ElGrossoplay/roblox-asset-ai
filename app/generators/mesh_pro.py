"""Modelos 3D low-poly estilizados (.glb) + vista previa renderizada (PNG).

- Primitivas: caja, cilindro/cono, esfera (icosfera), torno (perfil girado), extrusion de silueta, toro.
- Cada pieza tiene su color; ademas se exportan colores por vertice (variacion por cara y
  oclusion suave abajo) para el look "low poly" sombreado. Si el importador ignora los colores
  de vertice, el color del material ya es correcto.
- Unidades: 1 = 1 stud de Roblox (en el importador usa "Scale: 1" / unidad stud).
"""
import json
import math
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# ============================================================= utilidades de color
def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255


def tono(c, k):
    return np.clip(np.asarray(c) * k, 0, 1)


COLORES = {"rojo": "#d94141", "azul": "#3f73d9", "verde": "#4caf50", "amarillo": "#f2c94c", "morado": "#8e5bd9",
           "violeta": "#8e5bd9", "naranja": "#f2994a", "rosa": "#f28bc0", "celeste": "#62c5f2", "dorado": "#e8b73a",
           "blanco": "#f2f2f2", "negro": "#2b2b30", "gris": "#9aa0a8", "cafe": "#8a5a36", "café": "#8a5a36", "marron": "#8a5a36"}

MADERA, MADERA_OSC = rgb("#9a6a3f"), rgb("#6e4526")
PIEDRA, METAL, ORO = rgb("#8d9096"), rgb("#b9c0c9"), rgb("#e8b73a")
HOJA, HOJA_OSC = rgb("#5aa647"), rgb("#3b7f37")


# ============================================================= malla
class Malla:
    """Coleccion de piezas: cada pieza = (vertices Nx3, caras Mx3, color rgb 0..1)."""

    def __init__(self):
        self.piezas = []

    def add(self, v, f, color, nombre=""):
        self.piezas.append((np.asarray(v, float), np.asarray(f, int), np.asarray(color, float), nombre))
        return self

    def extend(self, otra, T=None):
        for v, f, c, n in otra.piezas:
            self.piezas.append((v if T is None else T(v), f, c, n))
        return self

    def transformar(self, T):
        self.piezas = [(T(v), f, c, n) for v, f, c, n in self.piezas]
        return self

    def apoyar_en_suelo(self):
        ymin = min(v[:, 1].min() for v, *_ in self.piezas)
        return self.transformar(lambda v: v - [0, ymin, 0])

    def caja_limite(self):
        todos = np.vstack([v for v, *_ in self.piezas])
        return todos.min(0), todos.max(0)


def mover(dx=0, dy=0, dz=0):
    return lambda v: v + [dx, dy, dz]


def escalar(sx=1, sy=None, sz=None):
    sy = sx if sy is None else sy
    sz = sx if sz is None else sz
    return lambda v: v * [sx, sy, sz]


def rotar(rx=0, ry=0, rz=0):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx
    return lambda v: v @ R.T


def componer(*Ts):
    def T(v):
        for t in Ts:
            v = t(v)
        return v
    return T


# ============================================================= primitivas
def caja(sx, sy, sz, centro=(0, 0, 0), base=True):
    x, y, z = sx / 2, sy, sz / 2
    y0 = 0 if base else -sy / 2
    v = np.array([[-x, y0, -z], [x, y0, -z], [x, y0 + y, -z], [-x, y0 + y, -z],
                  [-x, y0, z], [x, y0, z], [x, y0 + y, z], [-x, y0 + y, z]]) + centro
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]
    return v, np.array(f)


def torno(perfil, lados=10, tapar=True, ruido=0.0, rng=None):
    """Gira un perfil [(radio, altura), ...] alrededor del eje Y (barriles, botellas, troncos...)."""
    rng = rng or np.random.default_rng(0)
    ang = np.linspace(0, 2 * np.pi, lados, endpoint=False)
    verts = []
    for i, (r, y) in enumerate(perfil):
        jit = 1 + (rng.uniform(-ruido, ruido, lados) if ruido else 0)
        verts += [(r * jit[k] * math.cos(a) if ruido else r * math.cos(a), y, (r * jit[k] if ruido else r) * math.sin(a)) for k, a in enumerate(ang)]
    caras = []
    for i in range(len(perfil) - 1):
        for k in range(lados):
            a, b = i * lados + k, i * lados + (k + 1) % lados
            c, d = a + lados, b + lados
            caras += [(a, c, b), (b, c, d)]
    verts = np.array(verts, float)
    if tapar:
        abajo, arriba = len(verts), len(verts) + 1
        verts = np.vstack([verts, [0, perfil[0][1], 0], [0, perfil[-1][1], 0]])
        u = (len(perfil) - 1) * lados
        for k in range(lados):
            if perfil[0][0] > 1e-6:
                caras.append((abajo, k, (k + 1) % lados))
            if perfil[-1][0] > 1e-6:
                caras.append((arriba, u + (k + 1) % lados, u + k))
    return verts, np.array(caras)


def cilindro(r0, r1, h, lados=10, y0=0.0, **kw):
    return torno([(r0, y0), (r1, y0 + h)], lados, **kw)


def icosfera(sub=1, radio=1.0, ruido=0.0, rng=None, achatar=1.0):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(sub):
        cache, nf = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = v[a] + v[b]
                v.append(m / np.linalg.norm(m))
                cache[k] = len(v) - 1
            return cache[k]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    V = np.array(v) * radio
    if ruido:
        rng = rng or np.random.default_rng(0)
        # ruido coherente: suma de ondas en direcciones aleatorias
        d = rng.normal(size=(5, 3))
        fase = rng.uniform(0, 6, 5)
        n = sum(np.sin(V @ d[i] * (1.5 + i) + fase[i]) / (1 + i) for i in range(5))
        V = V * (1 + ruido * n[:, None] / 1.6)
    V[:, 1] *= achatar
    return V, np.array(f)


def extruir(silueta, grosor, centrar=True):
    """Extruye un poligono 2D (x, y) en Z. Triangulacion en abanico (silueta convexa o estrellada)."""
    s = np.asarray(silueta, float)
    n = len(s)
    z = grosor / 2
    centro = s.mean(0)
    v = np.vstack([np.c_[s, np.full(n, -z)], np.c_[s, np.full(n, z)], [[*centro, -z], [*centro, z]]])
    c0, c1 = 2 * n, 2 * n + 1
    f = []
    for i in range(n):
        j = (i + 1) % n
        f += [(i, j, j + n), (i, j + n, i + n), (c0, j, i), (c1, i + n, j + n)]
    return v, np.array(f)


def toro(R, r, lados=14, anillos=8):
    v, f = [], []
    for i in range(lados):
        a = 2 * np.pi * i / lados
        for j in range(anillos):
            b = 2 * np.pi * j / anillos
            v.append(((R + r * math.cos(b)) * math.cos(a), r * math.sin(b), (R + r * math.cos(b)) * math.sin(a)))
    for i in range(lados):
        for j in range(anillos):
            a, b = i * anillos + j, i * anillos + (j + 1) % anillos
            c, d = ((i + 1) % lados) * anillos + j, ((i + 1) % lados) * anillos + (j + 1) % anillos
            f += [(a, c, b), (b, c, d)]
    return np.array(v), np.array(f)


def prisma_techo(ancho, alto, largo):
    x, z = ancho / 2, largo / 2
    v = np.array([[-x, 0, -z], [x, 0, -z], [0, alto, -z], [-x, 0, z], [x, 0, z], [0, alto, z]])
    f = [(0, 2, 1), (3, 4, 5), (0, 3, 5), (0, 5, 2), (1, 2, 5), (1, 5, 4), (0, 1, 4), (0, 4, 3)]
    return v, np.array(f)


def estrella2d(r1, r2, puntas=5):
    return [((r1 if i % 2 == 0 else r2) * math.cos(math.pi / 2 + i * math.pi / puntas),
             (r1 if i % 2 == 0 else r2) * math.sin(math.pi / 2 + i * math.pi / puntas)) for i in range(puntas * 2)]


# ============================================================= props
def p_arbol(rng, c):
    m = Malla()
    alto = rng.uniform(4, 6)
    m.add(*torno([(0.55, 0), (0.42, alto * 0.3), (0.32, alto)], 8, ruido=0.08, rng=rng), MADERA)
    hoja = c if c is not None else HOJA
    for k in range(rng.integers(3, 6)):
        r = rng.uniform(1.3, 2.0)
        v, f = icosfera(1, r, 0.2, rng, 0.85)
        ang = rng.uniform(0, 6.28)
        d = 0 if k == 0 else rng.uniform(0.8, 1.4)
        m.add(v + [d * math.cos(ang), alto + rng.uniform(0, 1.4) - (0.2 if k else 0), d * math.sin(ang)], f, tono(hoja, rng.uniform(0.85, 1.1)))
    return m


def p_pino(rng, c):
    m = Malla()
    m.add(*cilindro(0.4, 0.3, 1.6, 7), MADERA_OSC)
    hoja = c if c is not None else rgb("#2f7a4b")
    pisos = rng.integers(3, 5)
    for i in range(pisos):
        r = 2.4 - i * (1.8 / pisos)
        y = 1.2 + i * 1.5
        m.add(*cilindro(r, 0.05, 2.4, 8, y, ruido=0.12, rng=rng), tono(hoja, 0.9 + i * 0.06))
    return m


def p_palmera(rng, c):
    m = Malla()
    curva = rng.uniform(0.6, 1.4)
    alto = rng.uniform(6, 8)
    segs = 6
    for i in range(segs):
        y0, y1 = alto * i / segs, alto * (i + 1) / segs
        dx0, dx1 = curva * (i / segs) ** 2, curva * ((i + 1) / segs) ** 2
        v, f = cilindro(0.45 - i * 0.04, 0.4 - i * 0.04, y1 - y0, 7, 0)
        m.add(v + [dx0, y0, 0] + np.c_[(v[:, 1] / (y1 - y0)) * (dx1 - dx0), 0 * v[:, 1], 0 * v[:, 1]], f, tono(MADERA, 1.05 if i % 2 else 0.9))
    top = np.array([curva, alto, 0])
    hoja = c if c is not None else HOJA
    for k in range(7):
        a = k / 7 * 2 * np.pi + rng.uniform(-0.2, 0.2)
        largo = rng.uniform(3.2, 4.2)
        v, f = extruir([(0, -0.1), (largo * 0.5, -0.55), (largo, -0.05), (largo * 0.5, 0.45), (0, 0.1)], 0.08)
        v = componer(rotar(rx=math.pi / 2), rotar(rz=-rng.uniform(0.35, 0.7)), rotar(ry=a))(v)
        m.add(v + top, f, tono(hoja, rng.uniform(0.85, 1.1)))
    for k in range(3):
        v, f = icosfera(0, 0.35)
        m.add(v + top + [0.3 * math.cos(k * 2.1), -0.35, 0.3 * math.sin(k * 2.1)], f, rgb("#7a4a24"))
    return m


def p_arbol_seco(rng, c):
    m = Malla()
    m.add(*torno([(0.5, 0), (0.35, 2.5), (0.15, 5)], 7, ruido=0.1, rng=rng), tono(MADERA_OSC, 0.8))
    for k in range(5):
        v, f = cilindro(0.16, 0.03, rng.uniform(1.5, 2.5), 5)
        a = rng.uniform(0, 6.28)
        v = componer(rotar(rz=rng.uniform(0.6, 1.1)), rotar(ry=a), mover(0, rng.uniform(2.2, 4.5), 0))(v)
        m.add(v, f, tono(MADERA_OSC, 0.75))
    return m


def p_cerezo(rng, c):
    return p_arbol(rng, c if c is not None else rgb("#f4a7c8"))


def p_arbusto(rng, c):
    m = Malla()
    hoja = c if c is not None else HOJA
    for k in range(rng.integers(3, 6)):
        r = rng.uniform(0.7, 1.1)
        v, f = icosfera(1, r, 0.18, rng, 0.8)
        m.add(v + [rng.uniform(-0.9, 0.9), r * 0.6, rng.uniform(-0.9, 0.9)], f, tono(hoja, rng.uniform(0.8, 1.05)))
    if rng.random() < 0.5:
        for k in range(5):
            v, f = icosfera(0, 0.14)
            m.add(v + [rng.uniform(-1, 1), rng.uniform(0.9, 1.4), rng.uniform(-1, 1)], f, rgb(rng.choice(["#e94b5a", "#f2c94c", "#ffffff"])))
    return m


def p_flor(rng, c):
    m = Malla()
    m.add(*cilindro(0.06, 0.05, 1.4, 5), HOJA_OSC)
    petalo = c if c is not None else rgb(rng.choice(["#f25c7a", "#f2c94c", "#a66cf2", "#ffffff", "#f2994a"]))
    for k in range(6):
        v, f = icosfera(1, 0.28, 0, None, 0.35)
        a = k * math.pi / 3
        m.add(v * [1.3, 1, 0.8] + [0.32 * math.cos(a), 1.45, 0.32 * math.sin(a)], f, petalo)
    m.add(icosfera(1, 0.18)[0] + [0, 1.5, 0], icosfera(1, 0.18)[1], rgb("#f2c94c"))
    v, f = extruir([(0, 0), (0.5, 0.15), (0.6, 0.3), (0.2, 0.25)], 0.04)
    m.add(componer(rotar(rx=math.pi / 2), mover(0, 0.5, 0))(v), f, HOJA)
    return m


def p_hongo(rng, c):
    m = Malla()
    m.add(*torno([(0.35, 0), (0.3, 0.8), (0.25, 1.4)], 9), rgb("#f1e6d0"))
    sombrero = c if c is not None else rgb(rng.choice(["#d94141", "#8e5bd9", "#e07a3f"]))
    m.add(*torno([(0.3, 1.25), (1.3, 1.35), (1.2, 1.7), (0.8, 2.1), (0.0, 2.3)], 12), sombrero)
    for k in range(6):
        a, d = rng.uniform(0, 6.28), rng.uniform(0.4, 0.95)
        h = 2.3 - (d / 1.3) ** 2 * 0.95
        m.add(icosfera(0, 0.12)[0] + [d * math.cos(a), h, d * math.sin(a)], icosfera(0, 0.12)[1], rgb("#ffffff"))
    return m


def p_pasto(rng, c):
    m = Malla()
    hoja = c if c is not None else HOJA
    for k in range(14):
        h = rng.uniform(0.6, 1.4)
        v, f = extruir([(-0.08, 0), (0.08, 0), (rng.uniform(-0.2, 0.2), h)], 0.03)
        v = componer(rotar(ry=rng.uniform(0, 6.28)), mover(rng.uniform(-0.6, 0.6), 0, rng.uniform(-0.6, 0.6)))(v)
        m.add(v, f, tono(hoja, rng.uniform(0.8, 1.15)))
    return m


def p_roca(rng, c):
    m = Malla()
    col = c if c is not None else PIEDRA
    v, f = icosfera(1, 1.3, 0.35, rng, 0.7)
    v[:, 1] = np.maximum(v[:, 1], -0.2)
    m.add(v * [rng.uniform(1, 1.5), 1, rng.uniform(0.9, 1.3)], f, col)
    return m


def p_grupo_rocas(rng, c):
    m = Malla()
    for k in range(rng.integers(3, 6)):
        s = rng.uniform(0.4, 1.0)
        r = p_roca(rng, c)
        m.extend(r, componer(escalar(s), rotar(ry=rng.uniform(0, 6)), mover(rng.uniform(-1.8, 1.8), 0, rng.uniform(-1.8, 1.8))))
    return m


def p_cristal(rng, c):
    m = Malla()
    col = c if c is not None else rgb(rng.choice(["#5ad1f2", "#a66cf2", "#f25c9a", "#5af2a6"]))
    for k in range(rng.integers(3, 7)):
        h = rng.uniform(1.2, 3.2) * (1.4 if k == 0 else 1)
        r = h * 0.2
        v, f = torno([(r * 0.8, 0), (r, h * 0.75), (0, h)], 6)
        inc = 0 if k == 0 else rng.uniform(0.25, 0.6)
        v = componer(rotar(rz=inc), rotar(ry=rng.uniform(0, 6.28)))(v)
        m.add(v, f, tono(col, rng.uniform(0.85, 1.15)))
    v, f = icosfera(1, 1.0, 0.3, rng, 0.35)
    m.add(v, f, tono(PIEDRA, 0.7))
    return m


def p_tronco(rng, c):
    m = Malla()
    largo = rng.uniform(3, 5)
    v, f = cilindro(0.55, 0.5, largo, 9, ruido=0.06, rng=rng)
    m.add(componer(rotar(rz=math.pi / 2), mover(largo / 2, 0.5, 0))(v), f, MADERA)
    v, f = cilindro(0.45, 0.45, 0.02, 9)
    m.add(componer(rotar(rz=math.pi / 2), mover(largo / 2 + 0.01, 0.5, 0))(v), f, rgb("#d8b27a"))
    return m


def p_cerca(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    for i in range(4):
        m.add(*caja(0.35, 2.2 + rng.uniform(-0.1, 0.1), 0.35, (i * 1.6, 0, 0)), tono(col, rng.uniform(0.9, 1.05)))
    for y in (0.7, 1.6):
        m.add(*caja(4.9, 0.25, 0.18, (2.4, y, 0.2)), tono(col, 0.9))
    return m


def p_banca(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    for z in (-0.25, 0.05, 0.35):
        m.add(*caja(3.2, 0.12, 0.26, (0, 1.0, z)), tono(col, rng.uniform(0.92, 1.05)))
    for y in (1.5, 1.85):
        m.add(*caja(3.2, 0.25, 0.08, (0, y, -0.42)), col)
    for x in (-1.3, 1.3):
        m.add(*caja(0.15, 1.0, 0.9, (x, 0, 0)), tono(METAL, 0.5))
        m.add(*caja(0.15, 1.2, 0.12, (x, 1.0, -0.42)), tono(METAL, 0.5))
    return m


def p_lampara(rng, c):
    m = Malla()
    m.add(*torno([(0.45, 0), (0.4, 0.3), (0.15, 0.4), (0.12, 4.5)], 8), tono(METAL, 0.35))
    luz = c if c is not None else rgb("#ffe08a")
    m.add(*torno([(0.15, 4.4), (0.5, 4.6), (0.45, 5.4), (0.0, 5.5)], 6), luz)
    m.add(*torno([(0.55, 5.35), (0.3, 5.8), (0, 5.85)], 6), tono(METAL, 0.35))
    return m


def p_antorcha(rng, c):
    m = Malla()
    m.add(*cilindro(0.12, 0.18, 2.0, 6), MADERA_OSC)
    m.add(*cilindro(0.22, 0.22, 0.25, 6, 1.9), tono(METAL, 0.5))
    m.add(*torno([(0.25, 2.1), (0.3, 2.4), (0.0, 3.1)], 6, ruido=0.1, rng=rng), rgb("#ff8a1a"))
    m.add(*torno([(0.14, 2.15), (0.16, 2.35), (0.0, 2.8)], 6), rgb("#ffe14d"))
    return m


def p_barril(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    perfil = [(0.75, 0), (0.88, 0.6), (0.92, 1.0), (0.88, 1.4), (0.75, 2.0)]
    m.add(*torno(perfil, 14), col)
    for y in (0.3, 1.7):
        r = np.interp(y, [p[1] for p in perfil], [p[0] for p in perfil]) + 0.02
        m.add(*cilindro(r, r, 0.12, 14, y - 0.06), tono(METAL, 0.55))
    m.add(*cilindro(0.72, 0.72, 0.03, 14, 1.99), tono(col, 0.8))
    return m


def p_caja(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#c08a4c")
    m.add(*caja(1.8, 1.8, 1.8), col)
    osc_ = tono(col, 0.7)
    for (sx, sy, sz, cx, cy, cz) in [(1.84, 0.25, 0.25, 0, 0, -0.8), (1.84, 0.25, 0.25, 0, 1.55, -0.8), (1.84, 0.25, 0.25, 0, 0, 0.8),
                                     (1.84, 0.25, 0.25, 0, 1.55, 0.8), (0.25, 1.84, 0.25, -0.8, -0.02, -0.8), (0.25, 1.84, 0.25, 0.8, -0.02, -0.8),
                                     (0.25, 1.84, 0.25, -0.8, -0.02, 0.8), (0.25, 1.84, 0.25, 0.8, -0.02, 0.8)]:
        m.add(*caja(sx, sy, sz, (cx, cy, cz)), osc_)
    return m


def p_cofre(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#a8652f")
    m.add(*caja(2.4, 1.2, 1.5), col)
    v, f = torno([(0.75, 0), (0.75, 2.4)], 10, tapar=True)
    v = v[:, [1, 0, 2]] * [1, 1, 1]
    sel = v[:, 1] < 0
    v[sel, 1] = 0
    m.add(v + [-1.2, 1.2, 0], f, tono(col, 1.1))
    for x in (-1.0, 0, 1.0):
        m.add(*caja(0.18, 1.25, 1.55, (x, 0, 0)), ORO)
    m.add(*caja(0.4, 0.5, 0.15, (0, 0.9, 0.8)), tono(ORO, 0.8))
    return m


def p_moneda(rng, c):
    m = Malla()
    col = c if c is not None else ORO
    v, f = cilindro(1.0, 1.0, 0.25, 20)
    m.add(componer(rotar(rx=math.pi / 2), mover(0, 1.2, 0))(v), f, col)
    v, f = extruir(estrella2d(0.55, 0.24), 0.32)
    m.add(v + [0, 1.2, 0], f, tono(col, 1.15))
    return m


def p_gema(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#38d9ff")
    v, f = torno([(0.0, 0), (1.0, 1.0), (0.65, 1.5), (0.0, 1.55)], 8)
    m.add(v, f, col)
    return m


def p_espada(rng, c):
    m = Malla()
    hoja = c if c is not None else METAL
    v, f = extruir([(-0.18, 0), (0.18, 0), (0.18, 3.2), (0, 3.7), (-0.18, 3.2)], 0.08)
    m.add(v + [0, 1.4, 0], f, hoja)
    m.add(*caja(1.4, 0.2, 0.3, (0, 1.25, 0)), ORO)
    m.add(*cilindro(0.11, 0.11, 1.0, 6, 0.3), rgb("#5a3a22"))
    m.add(icosfera(1, 0.2)[0] + [0, 0.25, 0], icosfera(1, 0.2)[1], ORO)
    return m


def p_escudo(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#3f73d9")
    sil = [(0, -1.4), (1.1, -0.6), (1.2, 0.9), (0, 1.2), (-1.2, 0.9), (-1.1, -0.6)]
    v, f = extruir(sil, 0.25)
    m.add(v + [0, 1.5, 0], f, col)
    v, f = extruir([(x * 1.12, y * 1.12) for x, y in sil], 0.18)
    m.add(v + [0, 1.5, -0.06], f, ORO)
    v, f = extruir(estrella2d(0.5, 0.22), 0.3)
    m.add(v + [0, 1.6, 0.05], f, ORO)
    return m


def p_pocion(rng, c):
    m = Malla()
    liquido = c if c is not None else rgb(rng.choice(["#a64cf2", "#e94b5a", "#4cd97b", "#4c9ef2"]))
    m.add(*torno([(0.0, 0.05), (0.75, 0.2), (0.95, 0.7), (0.7, 1.25), (0.0, 1.3)], 12), liquido)
    m.add(*torno([(0.5, 1.2), (0.28, 1.4), (0.28, 2.0), (0.38, 2.1), (0.0, 2.12)], 10, tapar=True), rgb("#d6ecf5"))
    m.add(*cilindro(0.26, 0.3, 0.4, 8, 2.05), rgb("#8a5a32"))
    return m


def p_casa(rng, c):
    m = Malla()
    pared = c if c is not None else rgb(rng.choice(["#f2e3c6", "#e8d1b0", "#d9e6f2", "#f2d0c6"]))
    techo = rgb(rng.choice(["#b5473a", "#4a5f8a", "#5a7a3a", "#7a4a2a"]))
    a, l, h = rng.uniform(6, 8), rng.uniform(5, 7), rng.uniform(4, 5)
    m.add(*caja(a, h, l), pared)
    v, f = prisma_techo(a + 1.0, rng.uniform(2.5, 3.5), l + 1.0)
    m.add(v + [0, h, 0], f, techo)
    m.add(*caja(1.4, 2.4, 0.2, (0, 0, l / 2)), MADERA_OSC)
    for x in (-a / 3.2, a / 3.2):
        m.add(*caja(1.2, 1.2, 0.15, (x, h * 0.45, l / 2)), rgb("#9ad4f2"))
        m.add(*caja(1.45, 0.15, 0.25, (x, h * 0.45 - 0.1, l / 2)), tono(pared, 0.8))
    m.add(*caja(0.9, 2.5, 0.9, (a / 4, h + 0.5, -l / 5)), tono(PIEDRA, 0.85))
    return m


def p_torre(rng, c):
    m = Malla()
    col = c if c is not None else PIEDRA
    h = rng.uniform(9, 12)
    m.add(*torno([(2.2, 0), (2.0, h)], 12), col)
    m.add(*torno([(2.0, h), (2.5, h + 0.4), (2.5, h + 1.2)], 12, tapar=True), tono(col, 0.9))
    for k in range(8):
        a = k * math.pi / 4
        m.add(*caja(0.7, 0.8, 0.7, (2.3 * math.cos(a), h + 1.2, 2.3 * math.sin(a))), tono(col, 0.95))
    m.add(*torno([(2.3, h + 0.6), (0, h + 4.5)], 12), rgb("#3f5fa8") if rng.random() < 0.5 else rgb("#b5473a"))
    m.add(*caja(1.2, 2.2, 0.3, (0, 0, 2.0)), MADERA_OSC)
    return m


def p_letrero(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    m.add(*caja(0.3, 2.6, 0.3), tono(col, 0.8))
    m.add(*caja(2.6, 1.2, 0.18, (0, 2.0, 0.2)), col)
    m.add(*caja(2.3, 0.12, 0.05, (0, 2.6, 0.31)), tono(col, 0.7))
    return m


def p_pozo(rng, c):
    m = Malla()
    m.add(*torno([(1.5, 0), (1.5, 1.2), (1.1, 1.2), (1.1, 0.2)], 12, tapar=False), PIEDRA)
    m.add(*cilindro(1.1, 1.1, 0.05, 12, 0.6), rgb("#3f7fbf"))
    for x in (-1.3, 1.3):
        m.add(*caja(0.25, 2.8, 0.25, (x, 1.0, 0)), MADERA_OSC)
    v, f = prisma_techo(3.4, 1.2, 2.2)
    m.add(v + [0, 3.6, 0], f, rgb("#b5473a"))
    return m


def p_puesto(rng, c):
    m = Malla()
    toldo = c if c is not None else rgb(rng.choice(["#d94141", "#3f73d9", "#4caf50"]))
    m.add(*caja(4, 1.2, 1.6), MADERA)
    for x in (-1.9, 1.9):
        for z in (-0.7, 0.7):
            m.add(*caja(0.18, 3.2, 0.18, (x, 0, z)), MADERA_OSC)
    for i in range(5):
        col = toldo if i % 2 == 0 else rgb("#ffffff")
        v, f = caja(0.85, 0.12, 2.2, (-1.7 + i * 0.85, 0, 0))
        m.add(componer(rotar(rx=-0.25), mover(0, 3.3, 0.2))(v), f, col)
    for k in range(6):
        m.add(icosfera(0, 0.22)[0] + [rng.uniform(-1.6, 1.6), 1.4, rng.uniform(-0.5, 0.5)], icosfera(0, 0.22)[1],
              rgb(rng.choice(["#e94b5a", "#f2c94c", "#4caf50", "#f2994a"])))
    return m


def p_nube(rng, c):
    m = Malla()
    for k in range(5):
        r = rng.uniform(1.2, 2.0)
        m.add(icosfera(1, r, 0.1, rng, 0.8)[0] + [k * 1.3 - 2.6, rng.uniform(0, 0.6), rng.uniform(-0.5, 0.5)],
              icosfera(1, r)[1], tono(rgb("#ffffff"), rng.uniform(0.92, 1.0)))
    return m.transformar(mover(0, 8, 0))


def p_cohete(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#d94141")
    m.add(*torno([(0.9, 0.6), (1.1, 2.0), (1.05, 4.5), (0.6, 6.0), (0.0, 7.0)], 14), rgb("#eef0f5"))
    m.add(*torno([(0.65, 5.9), (0.0, 7.05)], 14), col)
    for k in range(3):
        v, f = extruir([(0.9, 0.6), (2.0, 0), (1.9, 1.1), (1.0, 2.2)], 0.15)
        m.add(rotar(ry=k * 2 * math.pi / 3)(v), f, col)
    m.add(*cilindro(0.6, 0.8, 0.6, 12), tono(METAL, 0.5))
    v, f = cilindro(0.42, 0.42, 0.12, 12)
    m.add(componer(rotar(rx=math.pi / 2), mover(0, 4.2, 1.05))(v), f, rgb("#62c5f2"))
    return m


def p_calabaza(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#f28a1a")
    for k in range(8):
        a = k * math.pi / 4
        v, f = icosfera(1, 0.75, 0, None, 1.2)
        m.add(v * [0.8, 0.85, 0.8] + [0.55 * math.cos(a), 0.9, 0.55 * math.sin(a)], f, tono(col, 0.95 + 0.07 * (k % 2)))
    m.add(*cilindro(0.15, 0.1, 0.6, 6, 1.6), rgb("#4a7a2a"))
    return m


def p_lapida(rng, c):
    m = Malla()
    col = c if c is not None else tono(PIEDRA, 0.8)
    perfil = [(-0.9, 0), (0.9, 0), (0.9, 1.8)] + [(0.9 * math.cos(a), 1.8 + 0.9 * math.sin(a)) for a in np.linspace(0.3, math.pi - 0.3, 6)] + [(-0.9, 1.8)]
    v, f = extruir(perfil, 0.35)
    m.add(v, f, col)
    m.add(*caja(2.2, 0.25, 1.0), tono(col, 0.85))
    m.add(*caja(0.12, 0.9, 0.05, (0, 1.2, 0.19)), tono(col, 0.6))
    m.add(*caja(0.6, 0.12, 0.05, (0, 1.75, 0.19)), tono(col, 0.6))
    return m


def p_cactus(rng, c):
    m = Malla()
    col = c if c is not None else rgb("#5f9a4a")
    alto = rng.uniform(3, 4.5)
    m.add(*torno([(0.5, 0), (0.55, alto * 0.5), (0.45, alto), (0, alto + 0.35)], 8), col)
    for lado in (-1, 1):
        if rng.random() < 0.85:
            h = rng.uniform(1.2, alto * 0.6)
            v, f = cilindro(0.3, 0.3, 0.8, 7)
            m.add(componer(rotar(rz=math.pi / 2), mover(lado * 0.9, h, 0))(v), f, col)
            v, f = torno([(0.3, 0), (0.28, 1.1), (0, 1.35)], 7)
            m.add(v + [lado * 1.25, h - 0.3, 0], f, tono(col, 1.05))
    if rng.random() < 0.5:
        m.add(icosfera(1, 0.22)[0] + [0, alto + 0.35, 0], icosfera(1, 0.22)[1], rgb("#f25c9a"))
    return m


def p_personaje(rng, c):
    """Proporciones tipo R15 simplificado (4 studs de alto aprox)."""
    m = Malla()
    piel = rgb(rng.choice(["#f2c9a0", "#e0a878", "#b87a4e", "#8a5a36", "#ffd8b0"]))
    camisa = c if c is not None else rgb(rng.choice(["#3f73d9", "#d94141", "#4caf50", "#8e5bd9", "#f2994a"]))
    pantalon = rgb(rng.choice(["#2b3a5a", "#3a3a3f", "#5a4a3a"]))
    for x in (-0.5, 0.5):
        m.add(*caja(0.9, 1.9, 0.95, (x, 0, 0)), pantalon)
        m.add(*caja(0.95, 0.35, 1.05, (x, 0, 0.05)), rgb("#2b2b30"))
    m.add(*caja(2.0, 2.0, 1.0, (0, 1.9, 0)), camisa)
    for x in (-1.5, 1.5):
        m.add(*caja(0.95, 1.6, 0.95, (x, 2.3, 0)), camisa)
        m.add(*caja(0.9, 0.5, 0.9, (x, 1.85, 0)), piel)
    v, f = torno([(0.55, 0), (0.75, 0.15), (0.78, 0.7), (0.7, 1.15), (0.0, 1.25)], 12)
    m.add(v + [0, 3.95, 0], f, piel)
    for x in (-0.25, 0.25):
        m.add(*caja(0.14, 0.24, 0.06, (x, 4.55, 0.74)), rgb("#222226"))
    m.add(*caja(0.4, 0.06, 0.06, (0, 4.3, 0.75)), rgb("#7a3a32"))
    pelo = rgb(rng.choice(["#3a2a1e", "#d9b25a", "#1e1e22", "#a0522d", "#e07a3f"]))
    m.add(*torno([(0.8, 4.65), (0.82, 4.95), (0.6, 5.25), (0.0, 5.32)], 12), pelo)
    return m


def p_jarron(rng, c):
    m = Malla()
    col = c if c is not None else rgb(rng.choice(["#c86a3f", "#3f73d9", "#e8d1b0"]))
    m.add(*torno([(0.0, 0), (0.55, 0.02), (0.85, 0.6), (0.7, 1.3), (0.35, 1.6), (0.45, 1.9), (0.0, 1.85)], 14), col)
    return m


def p_mesa(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    m.add(*caja(3.2, 0.2, 2.0, (0, 1.6, 0)), col)
    for x in (-1.4, 1.4):
        for z in (-0.8, 0.8):
            m.add(*caja(0.2, 1.6, 0.2, (x, 0, z)), tono(col, 0.8))
    return m


def p_silla(rng, c):
    m = Malla()
    col = c if c is not None else MADERA
    m.add(*caja(1.2, 0.15, 1.2, (0, 1.0, 0)), col)
    for x in (-0.5, 0.5):
        for z in (-0.5, 0.5):
            m.add(*caja(0.14, 1.0, 0.14, (x, 0, z)), tono(col, 0.8))
        m.add(*caja(0.14, 1.3, 0.14, (x, 1.1, -0.53)), tono(col, 0.8))
    m.add(*caja(1.2, 0.5, 0.1, (0, 1.85, -0.53)), col)
    return m


PROPS = {
    "arbol": (p_arbol, ["arbol", "árbol", "tree", "roble"]), "pino": (p_pino, ["pino", "pine", "abeto", "navidad"]),
    "palmera": (p_palmera, ["palmera", "palm", "coco"]), "arbol_seco": (p_arbol_seco, ["seco", "muerto", "dead tree"]),
    "cerezo": (p_cerezo, ["cerezo", "sakura", "cherry"]), "arbusto": (p_arbusto, ["arbusto", "bush", "matorral"]),
    "flor": (p_flor, ["flor", "flower", "rosa", "tulipan"]), "hongo": (p_hongo, ["hongo", "seta", "mushroom", "champiñon"]),
    "pasto": (p_pasto, ["pasto", "hierba", "grass", "cesped"]), "roca": (p_roca, ["roca", "piedra", "rock", "stone"]),
    "grupo_rocas": (p_grupo_rocas, ["rocas", "rocks", "pedregal"]), "cristal": (p_cristal, ["cristal", "crystal", "mineral"]),
    "tronco": (p_tronco, ["tronco", "log"]), "cerca": (p_cerca, ["cerca", "valla", "fence", "reja"]),
    "banca": (p_banca, ["banca", "banco", "bench"]), "lampara": (p_lampara, ["lampara", "lámpara", "farol", "poste", "lamp"]),
    "antorcha": (p_antorcha, ["antorcha", "torch"]), "barril": (p_barril, ["barril", "barrel", "tonel"]),
    "caja": (p_caja, ["caja", "crate", "box"]), "cofre": (p_cofre, ["cofre", "chest", "tesoro"]),
    "moneda": (p_moneda, ["moneda", "coin"]), "gema": (p_gema, ["gema", "diamante", "gem", "diamond"]),
    "espada": (p_espada, ["espada", "sword"]), "escudo": (p_escudo, ["escudo", "shield"]),
    "pocion": (p_pocion, ["pocion", "poción", "potion", "botella"]), "casa": (p_casa, ["casa", "house", "cabaña", "hogar"]),
    "torre": (p_torre, ["torre", "tower", "castillo", "castle"]), "letrero": (p_letrero, ["letrero", "cartel", "sign"]),
    "pozo": (p_pozo, ["pozo", "well"]), "puesto": (p_puesto, ["puesto", "tienda", "stall", "mercado", "kiosko"]),
    "nube": (p_nube, ["nube", "cloud"]), "cohete": (p_cohete, ["cohete", "rocket", "nave"]),
    "calabaza": (p_calabaza, ["calabaza", "pumpkin", "halloween"]), "lapida": (p_lapida, ["lapida", "lápida", "tumba", "grave", "cementerio"]),
    "cactus": (p_cactus, ["cactus"]), "personaje": (p_personaje, ["personaje", "npc", "avatar", "character", "persona"]),
    "jarron": (p_jarron, ["jarron", "jarrón", "vasija", "vase", "maceta"]), "mesa": (p_mesa, ["mesa", "table"]),
    "silla": (p_silla, ["silla", "chair"]),
}
# compatibilidad con los nombres antiguos
ALIAS = {"arbol_seco": "arbol_seco"}

NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}


def interpretar(prompt: str) -> list:
    """'3 rocas grises y una casa roja' -> [('grupo_rocas'/'roca', color, cantidad), ...]"""
    t = prompt.lower()
    palabras = re.findall(r"[\wáéíóúñ]+", t)
    encontrados = []
    for nombre, (_, sinonimos) in PROPS.items():
        for s in sinonimos:
            for m in re.finditer(r"\b" + re.escape(s), t):
                encontrados.append((m.start(), nombre, s))
                break
    encontrados.sort()
    vistos, salida = set(), []
    for pos, nombre, s in encontrados:
        if nombre in vistos or (nombre == "roca" and "grupo_rocas" in vistos):
            continue
        vistos.add(nombre)
        ventana = t[pos: pos + len(s) + 16]  # en espanol el adjetivo va despues: "casa roja"
        color = next((rgb(v) for k, v in COLORES.items()
                      if re.search(r"\b" + (k[:-1] if k[-1] in "oae" and len(k) >= 4 else k), ventana)), None)
        previo = re.findall(r"(\d+|un|una|uno|dos|tres|cuatro|cinco|seis)\s+\w*\s*$", t[max(0, pos - 12):pos])
        cant = 1
        if previo:
            cant = int(previo[-1]) if previo[-1].isdigit() else NUMEROS.get(previo[-1], 1)
        if nombre == "grupo_rocas" and cant > 1:
            nombre = "roca"
        salida.append((nombre, color, max(1, min(cant, 6))))
    return salida


def construir(nombre: str, semilla: int = 0, color=None, escala: float = 1.0) -> Malla:
    fn = PROPS.get(nombre, PROPS["roca"])[0]
    rng = np.random.default_rng(semilla or (abs(hash(nombre)) % 2**31))
    m = fn(rng, None if color is None else np.asarray(color, float))
    if escala != 1:
        m.transformar(escalar(escala))
    return m.apoyar_en_suelo()


# ============================================================= exportacion GLB
def _aplanar(v, f, color, rng):
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    pos = tri.reshape(-1, 3)
    nor = np.repeat(n, 3, 0)
    jit = np.repeat(rng.uniform(0.9, 1.0, len(f)), 3)[:, None]
    return pos.astype(np.float32), nor.astype(np.float32), jit


def guardar_glb(m: Malla, destino: Path, semilla=0) -> Path:
    rng = np.random.default_rng(semilla + 5)
    ymin, ymax = (lambda a, b: (a[1], b[1]))(*m.caja_limite())
    altura = max(ymax - ymin, 1e-6)
    # agrupa piezas del mismo color en una sola primitiva (menos MeshParts al importar)
    grupos = {}
    for v, f, c, _ in m.piezas:
        clave = tuple(np.round(c, 3))
        grupos.setdefault(clave, []).append((v, f))
    buffer, accessors, views, prims, mats = bytearray(), [], [], [], []

    def agregar(arr, tipo, minmax=False):
        off = len(buffer)
        datos = arr.tobytes()
        buffer.extend(datos)
        while len(buffer) % 4:
            buffer.extend(b"\0")
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(datos), "target": 34962})
        acc = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(arr), "type": tipo}
        if minmax:
            acc["min"], acc["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    for idx, (color, piezas) in enumerate(grupos.items()):
        P, N, C = [], [], []
        for v, f in piezas:
            pos, nor, jit = _aplanar(v, f, color, rng)
            ao = 0.72 + 0.28 * np.clip((pos[:, 1:2] - ymin) / (altura * 0.35), 0, 1)  # oclusion suave abajo
            P.append(pos)
            N.append(nor)
            C.append(np.clip(jit * ao, 0, 1).astype(np.float32).repeat(3, 1))
        P, N, C = np.vstack(P), np.vstack(N), np.vstack(C)
        prims.append({"attributes": {"POSITION": agregar(P, "VEC3", True), "NORMAL": agregar(N, "VEC3"), "COLOR_0": agregar(C, "VEC3")},
                      "material": idx})
        lin = [float(x) ** 2.2 for x in color]
        mats.append({"name": f"color_{idx}", "doubleSided": True,
                     "pbrMetallicRoughness": {"baseColorFactor": [*lin, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.85}})
    gltf = {"asset": {"version": "2.0", "generator": "RobloxAssetAI mesh_pro"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": destino.stem}], "meshes": [{"name": destino.stem, "primitives": prims}],
            "materials": mats, "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(buffer)}]}
    js = json.dumps(gltf).encode()
    while len(js) % 4:
        js += b" "
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(buffer)))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(buffer), 0x004E4942) + bytes(buffer))
    return destino


def guardar_obj(m: Malla, destino: Path) -> Path:
    """OBJ + MTL (alternativa para Blender u otros programas)."""
    mtl = destino.with_suffix(".mtl")
    lineas, mats, base = [f"mtllib {mtl.name}"], [], 1
    for i, (v, f, c, _) in enumerate(m.piezas):
        mats.append(f"newmtl m{i}\nKd {c[0]:.3f} {c[1]:.3f} {c[2]:.3f}\n")
        lineas.append(f"usemtl m{i}")
        lineas += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in v]
        lineas += [f"f {a + base} {b + base} {cc + base}" for a, b, cc in f]
        base += len(v)
    destino.write_text("\n".join(lineas), encoding="utf-8")
    mtl.write_text("\n".join(mats), encoding="utf-8")
    return destino


# ============================================================= vista previa (rasterizador simple)
def render(m: Malla, destino: Path, tam=512, fondo=("#2a3550", "#121826")) -> Path:
    S = tam * 2
    mn, mx = m.caja_limite()
    centro = (mn + mx) / 2
    radio = np.linalg.norm(mx - mn) / 2 + 1e-6
    R = componer(rotar(ry=-0.65), rotar(rx=0.38))  # gira (yaw) y luego mira desde arriba (pitch)
    luz = np.array([0.45, 0.8, 0.55])
    luz /= np.linalg.norm(luz)
    tris = []
    for v, f, c, _ in m.piezas:
        vv = R(v - centro)
        tri = vv[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        luzc = 0.42 + 0.58 * np.clip(np.abs(n @ luz), 0, 1)
        prof = tri[:, :, 2].mean(1)
        for k in range(len(f)):
            tris.append((prof[k], tri[k], np.clip(c * luzc[k], 0, 1)))
    tris.sort(key=lambda x: x[0])
    img = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(img)
    a, b = rgb(fondo[0]) * 255, rgb(fondo[1]) * 255
    for y in range(S):
        tt = y / S
        d.line([(0, y), (S, y)], fill=tuple(int(x) for x in a * (1 - tt) + b * tt))
    # sombra en el suelo
    sombra = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sombra).ellipse([S * 0.25, S * 0.72, S * 0.75, S * 0.84], fill=110)
    img.paste((8, 10, 16), mask=sombra.filter(ImageFilter.GaussianBlur(S * 0.03)))
    escala = S * 0.42 / radio
    for _, tri, col in tris:
        pts = [(S / 2 + p[0] * escala, S * 0.5 - p[1] * escala) for p in tri]
        fill = tuple(int(x * 255) for x in col)
        d.polygon(pts, fill=fill, outline=fill)
    img = img.resize((tam, tam), Image.LANCZOS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def pulir(destino: Path, nombre: str, log=print) -> bool:
    """Si Blender esta disponible: biseles/normales profesionales + FBX + vista previa Cycles.
    Devuelve True si se pulio. Nunca rompe: ante cualquier fallo deja el modelo original."""
    from .. import blender, config
    cfg = config.get().get("blender", {})
    if not cfg.get("pulir_procedurales", True) or not blender.disponible():
        return False
    try:
        prev = destino.with_suffix(".png") if cfg.get("render_preview", True) else None
        blender.pulir_procedural(destino, destino, nombre, cfg.get("exportar_fbx", True), prev, log)
        return True
    except blender.BlenderError as e:
        log(f"    Blender no pudo pulir {nombre} ({str(e)[:100]})")
        return False
