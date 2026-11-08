"""Post-proceso de modelos 3D generados por IA (GLB con textura) para que entren bien a Roblox.

- Lector/escritor GLB propio (sin dependencias): posiciones, UV, normales, colores, textura base.
- Aplica las transformaciones de nodos, centra el modelo y lo apoya en el suelo (Y = 0).
- Escala a una altura en studs.
- Roblox admite hasta 20.000 triangulos por MeshPart: si el modelo tiene mas, se DIVIDE en
  varias mallas que comparten la misma textura (no se pierde calidad). Si es enorme, se reduce
  por agrupacion de vertices y la textura se hornea a colores.
- Vista previa PNG con la textura real.
"""
import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TIPOS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
COMPS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Modelo:
    def __init__(self, pos, caras, uv=None, color=None, textura=None):
        self.pos = np.asarray(pos, float)
        self.caras = np.asarray(caras, np.int64)
        self.uv = None if uv is None else np.asarray(uv, float)
        self.color = None if color is None else np.asarray(color, float)  # por vertice (n,3) 0..1
        self.textura = textura  # PIL.Image o None

    @property
    def triangulos(self):
        return len(self.caras)


# ============================================================= lectura
def _matriz(nodo):
    if "matrix" in nodo:
        return np.array(nodo["matrix"], float).reshape(4, 4).T
    T = np.eye(4)
    if "scale" in nodo:
        T = np.diag([*nodo["scale"], 1.0]) @ T
    if "rotation" in nodo:
        x, y, z, w = nodo["rotation"]
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0], [0, 0, 0, 1]])
        T = R @ T
    if "translation" in nodo:
        M = np.eye(4)
        M[:3, 3] = nodo["translation"]
        T = M @ T
    return T


def leer_glb(ruta: Path) -> Modelo:
    datos = Path(ruta).read_bytes()
    if datos[:4] != b"glTF":
        if Path(ruta).suffix.lower() == ".obj":
            return leer_obj(ruta)
        raise ValueError("No es un GLB")
    _, _, total = struct.unpack("<III", datos[:12])
    off, js, binario = 12, None, b""
    while off < total:
        largo, tipo = struct.unpack("<II", datos[off:off + 8])
        trozo = datos[off + 8: off + 8 + largo]
        if tipo == 0x4E4F534A:
            js = json.loads(trozo)
        elif tipo == 0x004E4942:
            binario = trozo
        off += 8 + largo
    g = js

    def accesor(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        dt = np.dtype(TIPOS[a["componentType"]])
        n_comp = COMPS[a["type"]]
        inicio = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        paso = bv.get("byteStride") or dt.itemsize * n_comp
        if paso == dt.itemsize * n_comp:
            arr = np.frombuffer(binario, dt, a["count"] * n_comp, inicio).reshape(a["count"], n_comp)
        else:
            filas = [np.frombuffer(binario, dt, n_comp, inicio + k * paso) for k in range(a["count"])]
            arr = np.array(filas)
        arr = arr.astype(float)
        if a.get("normalized"):
            arr /= np.iinfo(dt).max
        return arr

    def imagen_material(mat_idx):
        try:
            mat = g["materials"][mat_idx]
            tex = mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]
            img = g["images"][g["textures"][tex]["source"]]
            if "bufferView" in img:
                bv = g["bufferViews"][img["bufferView"]]
                b = binario[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
                return Image.open(io.BytesIO(b)).convert("RGB")
            if "uri" in img and img["uri"].startswith("data:"):
                import base64
                return Image.open(io.BytesIO(base64.b64decode(img["uri"].split(",", 1)[1]))).convert("RGB")
            if "uri" in img:
                return Image.open(Path(ruta).parent / img["uri"]).convert("RGB")
        except (KeyError, IndexError, TypeError):
            return None
        return None

    def color_material(mat_idx):
        try:
            return np.array(g["materials"][mat_idx]["pbrMetallicRoughness"]["baseColorFactor"][:3], float) ** (1 / 2.2)
        except (KeyError, IndexError, TypeError):
            return np.array([0.8, 0.8, 0.8])

    piezas = []

    def visitar(ni, M):
        nodo = g["nodes"][ni]
        M2 = M @ _matriz(nodo)
        if "mesh" in nodo:
            for prim in g["meshes"][nodo["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4:
                    continue
                at = prim["attributes"]
                pos = accesor(at["POSITION"])
                pos = (np.c_[pos, np.ones(len(pos))] @ M2.T)[:, :3]
                idx = accesor(prim["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in prim else np.arange(len(pos)).reshape(-1, 3)
                uv = accesor(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else None
                col = accesor(at["COLOR_0"])[:, :3] if "COLOR_0" in at else None
                img = imagen_material(prim["material"]) if "material" in prim else None
                base = color_material(prim["material"]) if "material" in prim else np.array([0.8, 0.8, 0.8])
                if img is None:
                    col = (col if col is not None else np.ones((len(pos), 3))) * base
                piezas.append(Modelo(pos, idx, uv, col, img))
        for h in nodo.get("children", []):
            visitar(h, M2)

    escena = g.get("scenes", [{"nodes": list(range(len(g.get("nodes", []))))}])[g.get("scene", 0)]
    for ni in escena["nodes"]:
        visitar(ni, np.eye(4))
    if not piezas:
        raise ValueError("GLB sin mallas")
    return unir(piezas)


def leer_obj(ruta: Path) -> Modelo:
    v, f = [], []
    for linea in Path(ruta).read_text(errors="ignore").splitlines():
        p = linea.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "f":
            ids = [int(x.split("/")[0]) - 1 for x in p[1:]]
            for k in range(1, len(ids) - 1):
                f.append([ids[0], ids[k], ids[k + 1]])
    return Modelo(v, f, color=np.full((len(v), 3), 0.8))


def unir(piezas: list) -> Modelo:
    """Une piezas. Si hay varias texturas, se hornean a colores por vertice."""
    if len(piezas) == 1:
        return piezas[0]
    pos, caras, cols = [], [], []
    base = 0
    for p in piezas:
        pos.append(p.pos)
        caras.append(p.caras + base)
        cols.append(colores_vertice(p))
        base += len(p.pos)
    return Modelo(np.vstack(pos), np.vstack(caras), None, np.vstack(cols), None)


def colores_vertice(m: Modelo) -> np.ndarray:
    if m.textura is not None and m.uv is not None:
        tex = np.asarray(m.textura, float) / 255
        h, w = tex.shape[:2]
        u = np.clip((m.uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(int)
        v = np.clip((m.uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(int)  # glTF: v=0 arriba
        return tex[v, u, :3]
    if m.color is not None:
        return m.color
    return np.full((len(m.pos), 3), 0.8)


# ============================================================= normalizar y adaptar a Roblox
def normalizar(m: Modelo, altura_studs: float = 6.0) -> Modelo:
    mn, mx = m.pos.min(0), m.pos.max(0)
    centro = (mn + mx) / 2
    pos = m.pos - [centro[0], mn[1], centro[2]]
    alto = max(mx[1] - mn[1], 1e-6)
    pos *= altura_studs / alto
    return Modelo(pos, m.caras, m.uv, m.color, m.textura)


def reducir_clusters(m: Modelo, objetivo: int) -> Modelo:
    """Reduccion por agrupacion de vertices en una grilla (rapida, robusta). La textura se hornea a color."""
    cols = colores_vertice(m)
    mn, mx = m.pos.min(0), m.pos.max(0)
    tam = np.max(mx - mn)
    celdas = 256
    for _ in range(12):
        q = np.floor((m.pos - mn) / (tam / celdas)).astype(np.int64)
        clave = q[:, 0] * 1_000_003 + q[:, 1] * 1_009 + q[:, 2]
        unicas, inv = np.unique(clave, return_inverse=True)
        caras = inv[m.caras]
        validas = (caras[:, 0] != caras[:, 1]) & (caras[:, 1] != caras[:, 2]) & (caras[:, 0] != caras[:, 2])
        caras = caras[validas]
        caras = np.unique(np.sort(caras, 1), axis=0) if len(caras) else caras
        if len(caras) <= objetivo or celdas <= 16:
            break
        celdas = int(celdas * 0.8)
    n = len(unicas)
    pos = np.zeros((n, 3))
    col = np.zeros((n, 3))
    cuenta = np.bincount(inv, minlength=n)[:, None]
    np.add.at(pos, inv, m.pos)
    np.add.at(col, inv, cols)
    pos /= np.maximum(cuenta, 1)
    col /= np.maximum(cuenta, 1)
    # recuperar orientacion de las caras (el sort la puede invertir): comparar con normales originales no es posible tras unir; se exporta doble cara
    return Modelo(pos, caras, None, col, None)


def dividir(m: Modelo, max_tris: int) -> list:
    """Divide en trozos espacialmente compactos de <= max_tris triangulos (comparten textura)."""
    if m.triangulos <= max_tris:
        return [m]
    centros = m.pos[m.caras].mean(1)
    eje = int(np.argmax(np.ptp(centros, 0)))
    orden = np.argsort(centros[:, eje])
    trozos = []
    for i in range(0, len(orden), max_tris):
        sel = m.caras[orden[i:i + max_tris]]
        usados, nuevo = np.unique(sel, return_inverse=True)
        trozos.append(Modelo(m.pos[usados], nuevo.reshape(-1, 3), None if m.uv is None else m.uv[usados],
                             None if m.color is None else m.color[usados], m.textura))
    return trozos


def preparar_para_roblox(ruta_in: Path, ruta_out: Path, altura_studs=6.0, max_tris=18000) -> dict:
    m = normalizar(leer_glb(ruta_in), altura_studs)
    info = {"triangulos_originales": int(m.triangulos)}
    if m.triangulos > max_tris * 6:
        m = reducir_clusters(m, max_tris * 2)
        info["reducido_a"] = int(m.triangulos)
    trozos = dividir(m, max_tris)
    info["mallas"] = len(trozos)
    info["textura"] = m.textura is not None
    escribir_glb(trozos, ruta_out)
    return info


# ============================================================= escritura
def _normales(pos, caras):
    n = np.zeros_like(pos)
    tri = pos[caras]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for k in range(3):
        np.add.at(n, caras[:, k], fn)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def escribir_glb(trozos: list, destino: Path) -> Path:
    buffer = bytearray()
    accessors, views, meshes, nodes, materials, images, textures = [], [], [], [], [], [], []

    def vista(datos: bytes, target=None):
        off = len(buffer)
        buffer.extend(datos)
        while len(buffer) % 4:
            buffer.extend(b"\0")
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(datos)}
        if target:
            v["target"] = target
        views.append(v)
        return len(views) - 1

    def acc(arr, tipo, ct=5126, target=34962, minmax=False):
        a = {"bufferView": vista(arr.tobytes(), target), "componentType": ct, "count": len(arr), "type": tipo}
        if minmax:
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accessors.append(a)
        return len(accessors) - 1

    mat_tex = {}
    for i, t in enumerate(trozos):
        if t.textura is not None and t.uv is not None:
            clave = id(t.textura)
            if clave not in mat_tex:
                png = io.BytesIO()
                t.textura.save(png, "PNG")
                images.append({"bufferView": vista(png.getvalue()), "mimeType": "image/png"})
                textures.append({"source": len(images) - 1})
                materials.append({"name": "textura", "doubleSided": True, "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": len(textures) - 1}, "metallicFactor": 0.0, "roughnessFactor": 0.8}})
                mat_tex[clave] = len(materials) - 1
            mat = mat_tex[clave]
        else:
            if "color" not in mat_tex:
                materials.append({"name": "vertex_color", "doubleSided": True,
                                  "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.0, "roughnessFactor": 0.85}})
                mat_tex["color"] = len(materials) - 1
            mat = mat_tex["color"]
        pos = t.pos.astype(np.float32)
        attrs = {"POSITION": acc(pos, "VEC3", minmax=True), "NORMAL": acc(_normales(t.pos, t.caras).astype(np.float32), "VEC3")}
        if t.uv is not None and t.textura is not None:
            attrs["TEXCOORD_0"] = acc(t.uv.astype(np.float32), "VEC2")
        elif t.color is not None:
            attrs["COLOR_0"] = acc(np.clip(t.color, 0, 1).astype(np.float32), "VEC3")
        ind = acc(t.caras.astype(np.uint32).reshape(-1), "SCALAR", 5125, 34963)
        meshes.append({"name": f"parte_{i + 1}", "primitives": [{"attributes": attrs, "indices": ind, "material": mat}]})
        nodes.append({"mesh": i, "name": f"parte_{i + 1}"})
    g = {"asset": {"version": "2.0", "generator": "RobloxAssetAI malla3d"}, "scene": 0,
         "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes, "materials": materials,
         "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(buffer)}]}
    if images:
        g["images"], g["textures"] = images, textures
        g["samplers"] = [{"magFilter": 9729, "minFilter": 9987}]
        for t in textures:
            t["sampler"] = 0
    js = json.dumps(g).encode()
    while len(js) % 4:
        js += b" "
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(buffer)))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(buffer), 0x004E4942) + bytes(buffer))
    return destino


# ============================================================= vista previa
def render(m: Modelo, destino: Path, tam=512) -> Path:
    S = tam * 2
    cols_v = colores_vertice(m)
    mn, mx = m.pos.min(0), m.pos.max(0)
    centro = (mn + mx) / 2
    radio = np.linalg.norm(mx - mn) / 2 + 1e-9
    ay, ax = -0.65, 0.38
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    v = (m.pos - centro) @ Ry.T @ Rx.T
    tri = v[m.caras]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    luz = np.array([0.45, 0.8, 0.55]) / np.linalg.norm([0.45, 0.8, 0.55])
    ilum = 0.45 + 0.55 * np.abs(n @ luz)
    col = np.clip(cols_v[m.caras].mean(1) * ilum[:, None], 0, 1)
    orden = np.argsort(tri[:, :, 2].mean(1))
    img = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(img)
    for y in range(0, S, 2):
        t = y / S
        c = tuple(int(a * (1 - t) + b * t) for a, b in zip((42, 53, 80), (18, 24, 38)))
        d.rectangle([0, y, S, y + 2], fill=c)
    sombra = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sombra).ellipse([S * 0.25, S * 0.72, S * 0.75, S * 0.84], fill=110)
    img.paste((8, 10, 16), mask=sombra.filter(ImageFilter.GaussianBlur(S * 0.03)))
    esc = S * 0.42 / radio
    xy = np.stack([S / 2 + tri[:, :, 0] * esc, S / 2 - tri[:, :, 1] * esc], -1)
    for k in orden:
        c = tuple(int(x * 255) for x in col[k])
        d.polygon([tuple(p) for p in xy[k]], fill=c, outline=c)
    img = img.resize((tam, tam), Image.LANCZOS)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return Path(destino)
