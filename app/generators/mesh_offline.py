"""Props low-poly procedurales exportados como .glb (glTF 2.0 binario).

Roblox Studio los importa con el 3D Importer o via Open Cloud (tipo Model).
Cada prop esta hecho de partes con su propio material (color de la paleta).
"""
import json
import struct
from pathlib import Path

import numpy as np

from .image_offline import hex_rgb


# ------------------------------------------------------------- primitivas
def _icosfera(sub=1):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
         (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
         (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(sub):
        cache, nf = {}, []

        def mid(a, b):
            key = tuple(sorted((a, b)))
            if key not in cache:
                m = v[a] + v[b]
                v.append(m / np.linalg.norm(m))
                cache[key] = len(v) - 1
            return cache[key]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(v), np.array(f)


def _cilindro(r0, r1, h, lados=8, y0=0.0):
    ang = np.linspace(0, 2 * np.pi, lados, endpoint=False)
    abajo = np.stack([np.cos(ang) * r0, np.full(lados, y0), np.sin(ang) * r0], 1)
    arriba = np.stack([np.cos(ang) * r1, np.full(lados, y0 + h), np.sin(ang) * r1], 1)
    v = np.vstack([abajo, arriba, [[0, y0, 0], [0, y0 + h, 0]]])
    c0, c1 = 2 * lados, 2 * lados + 1
    f = []
    for i in range(lados):
        j = (i + 1) % lados
        f += [(i, j + lados, j), (i, i + lados, j + lados), (c0, i, j), (c1, j + lados, i + lados)]
    return v, np.array(f)


def _caja(sx, sy, sz, y0=0.0):
    x, y, z = sx / 2, sy, sz / 2
    v = np.array([[-x, y0, -z], [x, y0, -z], [x, y0 + y, -z], [-x, y0 + y, -z],
                  [-x, y0, z], [x, y0, z], [x, y0 + y, z], [-x, y0 + y, z]])
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]
    return v, np.array(f)


def _plano(v, f):
    """Desindexa para sombreado plano low-poly y calcula normales."""
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    pos = tri.reshape(-1, 3)
    nor = np.repeat(n, 3, axis=0)
    return pos.astype(np.float32), nor.astype(np.float32)


def _deformar(v, rng, fuerza):
    return v * (1 + rng.uniform(-fuerza, fuerza, (len(v), 1)))


# ------------------------------------------------------------- props
def _prop(nombre, P, rng):
    """Devuelve lista de (vertices, caras, color_rgb)."""
    marron = np.array([110, 75, 45.])
    gris = np.array([125, 125, 130.])
    verde = next((c for c in P if c[1] > c[0] and c[1] > c[2]), np.array([70, 140, 60.]))
    acento = P[min(3, len(P) - 1)]
    k = nombre.lower()
    if "personaje" in k or "npc" in k or "avatar" in k:
        piel = np.array([255, 205, 160.])
        camisa, pantalon = P[min(1, len(P) - 1)], P[0] * 0.8 + 20
        def caja(sx, sy, sz, x, y, z, c):
            v, f = _caja(sx, sy, sz)
            return (v + [x, y, z], f, c)
        return [caja(0.95, 2, 1, -0.5, 0, 0, pantalon), caja(0.95, 2, 1, 0.5, 0, 0, pantalon),
                caja(2, 2, 1, 0, 2, 0, camisa), caja(1, 2, 1, -1.5, 2, 0, piel), caja(1, 2, 1, 1.5, 2, 0, piel),
                caja(1.2, 1.2, 1.2, 0, 4, 0, piel), caja(0.18, 0.18, 0.05, -0.25, 4.7, -0.62, np.array([30, 30, 35.])),
                caja(0.18, 0.18, 0.05, 0.25, 4.7, -0.62, np.array([30, 30, 35.]))]
    if "palmera" in k:
        partes = [(*_cilindro(0.25, 0.15, 5, 7), marron)]
        for i in range(6):
            a = i / 6 * 2 * np.pi
            v, f = _caja(0.5, 0.08, 2.4)
            v[:, 2] += 1.2
            v[:, 1] -= v[:, 2] * 0.25
            rot = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
            partes.append((v @ rot.T + [0, 5, 0], f, verde))
        return partes
    if "pino" in k:
        partes = [(*_cilindro(0.3, 0.25, 1.2, 6), marron)]
        for i, (r, y) in enumerate([(1.8, 1.0), (1.4, 2.2), (0.9, 3.3)]):
            partes.append((*_cilindro(r, 0.05, 1.6, 7, y), verde * (0.8 + 0.1 * i)))
        return partes
    if "cactus" in k:
        c = np.array([90, 140, 70.])
        return [(*_cilindro(0.4, 0.38, 3, 8), c), (*_cilindro(0.25, 0.25, 1.2, 6, 1.4), c)]
    if "seco" in k:
        partes = [(*_cilindro(0.3, 0.12, 4, 6), marron * 0.7)]
        for i in range(4):
            v, f = _cilindro(0.08, 0.03, 1.6, 5)
            a = i * np.pi / 2 + 0.4
            rot = np.array([[np.cos(a), -0.7, 0], [0.7, np.cos(a), 0], [0, 0, 1]])
            partes.append((v @ rot.T + [0, 2.5 + i * 0.3, 0], f, marron * 0.6))
        return partes
    if "arbol" in k:
        v, f = _icosfera(1)
        v = _deformar(v, rng, 0.15) * [1.6, 1.4, 1.6] + [0, 3.6, 0]
        return [(*_cilindro(0.35, 0.25, 2.6, 7), marron), (v, f, verde)]
    if "cristal" in k:
        v, f = _cilindro(0.5, 0.0, 2.2, 6)
        v2, f2 = _cilindro(0.5, 0.0, -0.7, 6)
        return [(v, f, acento), (v2, f2, acento * 0.8)]
    if "barril" in k:
        return [(*_cilindro(0.6, 0.6, 1.4, 12), marron),
                (*_cilindro(0.63, 0.63, 0.1, 12, 0.25), gris), (*_cilindro(0.63, 0.63, 0.1, 12, 1.05), gris)]
    if "lampara" in k:
        return [(*_cilindro(0.1, 0.1, 3.5, 6), gris * 0.6), (*_caja(0.5, 0.5, 0.5, 3.5), acento),
                (*_cilindro(0.4, 0.4, 0.15, 8), gris * 0.5)]
    # roca por defecto
    v, f = _icosfera(1)
    v = _deformar(v, rng, 0.25) * [1.3, 0.8, 1.1] + [0, 0.5, 0]
    return [(v, f, gris * 0.8 + P[0] * 0.2)]


def guardar_glb(partes, destino: Path) -> Path:
    buffer = bytearray()
    accessors, views, meshes_prims, materials = [], [], [], []
    for idx, (v, f, color) in enumerate(partes):
        pos, nor = _plano(np.asarray(v, float), np.asarray(f, int))
        for arr, tipo in ((pos, "pos"), (nor, "nor")):
            off = len(buffer)
            datos = arr.tobytes()
            buffer += datos
            while len(buffer) % 4:
                buffer += b"\0"
            views.append({"buffer": 0, "byteOffset": off, "byteLength": len(datos), "target": 34962})
            acc = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(arr), "type": "VEC3"}
            if tipo == "pos":
                acc["min"], acc["max"] = arr.min(0).tolist(), arr.max(0).tolist()
            accessors.append(acc)
        c = (np.clip(color, 0, 255) / 255).tolist()
        materials.append({"name": f"mat{idx}", "doubleSided": True, "pbrMetallicRoughness": {
            "baseColorFactor": [*(x ** 2.2 for x in c), 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.85}})
        meshes_prims.append({"attributes": {"POSITION": len(accessors) - 2, "NORMAL": len(accessors) - 1},
                             "material": idx})
    gltf = {
        "asset": {"version": "2.0", "generator": "RobloxAssetAI"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": destino.stem}],
        "meshes": [{"name": destino.stem, "primitives": meshes_prims}],
        "materials": materials, "accessors": accessors, "bufferViews": views,
        "buffers": [{"byteLength": len(buffer)}],
    }
    js = json.dumps(gltf).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(buffer)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(buffer), 0x004E4942) + bytes(buffer))
    return destino


def generar_prop(nombre: str, paleta: list, destino: Path, semilla: int = 0) -> Path:
    rng = np.random.default_rng(semilla or abs(hash(nombre)) % 2**32)
    P = [hex_rgb(c) for c in paleta]
    return guardar_glb(_prop(nombre, P, rng), destino)


# =====================================================================
#  v2: modelos mejorados (mesh_pro) con respaldo al generador antiguo
# =====================================================================
_prop_v1 = generar_prop


def generar_prop(nombre: str, paleta: list, destino: Path, semilla: int = 0, color=None,  # noqa: F811
                 preview: bool = True, obj: bool = False) -> Path:
    try:
        from . import mesh_pro
        m = mesh_pro.construir(nombre, semilla, color)
        mesh_pro.guardar_glb(m, destino, semilla)
        if preview:
            mesh_pro.render(m, destino.with_suffix(".png"), 384)
        mesh_pro.pulir(destino, nombre)
        if obj:
            mesh_pro.guardar_obj(m, destino.with_suffix(".obj"))
        return destino
    except Exception:  # noqa: BLE001
        return _prop_v1(nombre, paleta, destino, semilla)
