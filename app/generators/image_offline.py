"""Texturas tileables y skybox de 6 caras, generados por codigo (numpy + Pillow)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def _ruido_tileable(n, celdas, rng):
    """Value noise periodico (se repite sin costuras)."""
    grid = rng.random((celdas, celdas))
    x = np.linspace(0, celdas, n, endpoint=False)
    i0 = np.floor(x).astype(int)
    f = x - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % celdas
    a = grid[np.ix_(i0, i0)]
    b = grid[np.ix_(i0, i1)]
    c = grid[np.ix_(i1, i0)]
    d = grid[np.ix_(i1, i1)]
    fy, fx = f[:, None], f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, rng, octavas=5, base=4):
    out = np.zeros((n, n))
    amp, total = 1.0, 0.0
    for o in range(octavas):
        out += _ruido_tileable(n, base * 2 ** o, rng) * amp
        total += amp
        amp *= 0.5
    return out / total


def _colorear(v, c1, c2):
    v = np.clip(v, 0, 1)[..., None]
    return c1 * (1 - v) + c2 * v


def _ladrillos(n, rng, c_lad, c_junta, filas=8, cols=4):
    y, x = np.mgrid[0:n, 0:n] / n
    fila = np.floor(y * filas)
    xo = (x * cols + 0.5 * (fila % 2)) % 1
    yo = (y * filas) % 1
    junta = (xo < 0.04) | (yo < 0.08)
    var = rng.random((filas, cols + 1))[fila.astype(int) % filas, np.floor(x * cols + 0.5 * (fila % 2)).astype(int) % (cols + 1)]
    ruido = fbm(n, rng, 4, 8)
    base = _colorear(ruido * 0.5 + var * 0.5, c_lad * 0.8, c_lad * 1.15)
    return np.where(junta[..., None], c_junta, base)


def _voronoi(n, celdas, rng):
    """Distancias al 1er y 2do punto mas cercano (tileable)."""
    pts = rng.random((celdas * celdas // 2 + 4, 2))
    y, x = np.mgrid[0:n, 0:n] / n
    d1 = np.full((n, n), 9.0)
    d2 = np.full((n, n), 9.0)
    for px, py in pts:
        dx = np.abs(x - px)
        dy = np.abs(y - py)
        d = np.sqrt(np.minimum(dx, 1 - dx) ** 2 + np.minimum(dy, 1 - dy) ** 2)
        d2 = np.where(d < d1, d1, np.minimum(d2, d))
        d1 = np.minimum(d1, d)
    return d1, d2


RUGOSIDAD = {"metal": 0.35, "hielo": 0.15, "agua": 0.08, "baldosa": 0.45, "panel": 0.4, "lava": 0.7, "nieve": 0.8}
MATERIAL_ROBLOX = {"piedra": "Slate", "roca": "Rock", "madera": "WoodPlanks", "metal": "Metal", "pasto": "Grass", "hojas": "LeafyGrass",
                   "arena": "Sand", "nieve": "Snow", "hielo": "Ice", "ladrillo": "Brick", "baldosa": "Concrete", "panel": "DiamondPlate",
                   "asfalto": "Asphalt", "lava": "CrackedLava", "agua": "Glass", "adoquin": "Cobblestone", "teja": "Slate"}


def material_roblox(nombre: str) -> str:
    return next((v for k, v in MATERIAL_ROBLOX.items() if k in nombre), "Plastic")


def mapas_pbr(ruta_color: Path, nombre: str, fuerza: float = 8.0) -> dict:
    """Normal map (formato OpenGL, el que usa Roblox) y rugosidad desde la textura de color.
    Las derivadas usan np.roll para que los mapas tambien sean tileables."""
    col = np.asarray(Image.open(ruta_color).convert("RGB"), float) / 255
    altura = col @ np.array([0.3, 0.59, 0.11])
    altura = np.asarray(Image.fromarray((altura * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), float) / 255
    dx = (np.roll(altura, -1, 1) - np.roll(altura, 1, 1)) * fuerza
    dy = (np.roll(altura, -1, 0) - np.roll(altura, 1, 0)) * fuerza
    nz = np.ones_like(altura)
    L = np.sqrt(dx ** 2 + dy ** 2 + nz ** 2)
    normal = np.stack([-dx / L, dy / L, nz / L], -1) * 0.5 + 0.5
    base = next((v for k, v in RUGOSIDAD.items() if k in nombre), 0.85)
    rough = np.clip(base + (0.5 - altura) * 0.25, 0.05, 1.0)
    rn = ruta_color.with_name(ruta_color.stem + "_normal.png")
    rr = ruta_color.with_name(ruta_color.stem + "_rugosidad.png")
    Image.fromarray((normal * 255).astype(np.uint8), "RGB").save(rn)
    Image.fromarray((rough * 255).astype(np.uint8), "L").save(rr)
    return {"normal": rn, "rugosidad": rr}


def textura(nombre: str, paleta: list, destino: Path, n: int = 512, semilla: int = 0) -> Path:
    rng = np.random.default_rng(semilla or abs(hash(nombre)) % 2**32)
    P = [hex_rgb(c) for c in paleta]
    oscuro, claro = min(P, key=lambda c: c.sum()), max(P, key=lambda c: c.sum())
    acento = P[2 % len(P)]
    k = nombre.lower()

    if "ladrillo" in k:
        img = _ladrillos(n, rng, np.array([150, 70, 50.]) * 0.6 + acento * 0.4, claro * 0.6)
    elif "baldosa" in k or "panel" in k:
        y, x = np.mgrid[0:n, 0:n] / n
        lado = 4 if "baldosa" in k else 2
        borde = ((x * lado) % 1 < 0.03) | ((y * lado) % 1 < 0.03)
        base = _colorear(fbm(n, rng, 3, 4), oscuro * 0.9 + 40, oscuro * 0.9 + 70)
        img = np.where(borde[..., None], (acento if "panel" in k else oscuro * 0.6), base)
        if "panel" in k:
            remache = (((x * lado) % 1 - 0.08) ** 2 + ((y * lado) % 1 - 0.08) ** 2) < 0.0006
            img = np.where(remache[..., None], claro, img)
    elif "madera" in k:
        y, x = np.mgrid[0:n, 0:n] / n
        vetas = np.sin((y * 14 + fbm(n, rng, 4, 4) * 3) * 2 * np.pi) * 0.5 + 0.5
        tablas = ((x * 4) % 1 < 0.015)
        c1, c2 = np.array([110, 72, 42.]), np.array([165, 115, 70.])
        if "vieja" in k:
            c1, c2 = c1 * 0.6, c2 * 0.65
        img = np.where(tablas[..., None], c1 * 0.4, _colorear(vetas * 0.6 + fbm(n, rng, 5, 8) * 0.4, c1, c2))
    elif "metal" in k:
        y, x = np.mgrid[0:n, 0:n] / n
        cepillado = _ruido_tileable(n, 128, rng)[:, :1].repeat(n, 1) * 0.3
        img = _colorear(fbm(n, rng, 3, 4) * 0.5 + cepillado, np.array([90, 95, 105.]), np.array([170, 175, 185.]))
        if "oxid" in k:
            oxido = np.clip(fbm(n, rng, 5, 4) * 2 - 0.9, 0, 1)[..., None]
            img = img * (1 - oxido) + np.array([130, 60, 30.]) * oxido
    elif "pasto" in k or "hojas" in k:
        verde = next((c for c in P if c[1] > c[0] and c[1] > c[2]), np.array([80, 150, 60.]))
        r = fbm(n, rng, 6, 8)
        img = _colorear(r, verde * 0.55, np.minimum(verde * 1.25, 255))
        if "hojas" in k:
            manchas = (fbm(n, rng, 2, 16) > 0.55)[..., None]
            img = np.where(manchas, verde * 0.4, img)
    elif "arena" in k:
        img = _colorear(fbm(n, rng, 6, 8) * 0.5 + rng.random((n, n)) * 0.5, np.array([200, 165, 110.]), np.array([240, 215, 160.]))
    elif "nieve" in k:
        img = _colorear(fbm(n, rng, 5, 4) * 0.6 + rng.random((n, n)) * 0.4, np.array([205, 220, 238.]), np.array([250, 252, 255.]))
    elif "hielo" in k:
        grietas = np.abs(fbm(n, rng, 5, 4) - 0.5) < 0.012
        img = _colorear(fbm(n, rng, 4, 4), np.array([120, 175, 215.]), np.array([200, 235, 250.]))
        img = np.where(grietas[..., None], 255, img)
    elif "asfalto" in k:
        img = _colorear(rng.random((n, n)) * 0.5 + fbm(n, rng, 4, 8) * 0.5, np.array([35, 35, 40.]), np.array([75, 75, 82.]))
    elif "lava" in k:
        d1, d2 = _voronoi(n, 14, rng)
        grietas = np.clip(1 - (d2 - d1) * 9, 0, 1) ** 2
        roca = _colorear(fbm(n, rng, 5, 6), np.array([30, 22, 20.]), np.array([70, 50, 42.]))
        brillo = _colorear(fbm(n, rng, 3, 4), np.array([255, 70, 0.]), np.array([255, 210, 60.]))
        img = roca * (1 - grietas[..., None]) + brillo * grietas[..., None]
    elif "agua" in k:
        ondas = np.sin((fbm(n, rng, 4, 4) * 6 + np.mgrid[0:n, 0:n][0] / n * 8) * np.pi) * 0.5 + 0.5
        img = _colorear(ondas * 0.6 + fbm(n, rng, 5, 8) * 0.4, np.array([20, 90, 160.]), np.array([90, 190, 230.]))
    elif "adoquin" in k or "empedrado" in k or "cobble" in k:
        d1, d2 = _voronoi(n, 10, rng)
        borde = np.clip((d2 - d1) * 12, 0, 1)
        base = _colorear(fbm(n, rng, 5, 8), np.array([95, 92, 90.]), np.array([150, 145, 138.]))
        img = base * (0.35 + 0.65 * borde[..., None])
    elif "teja" in k or "techo" in k:
        y, x = np.mgrid[0:n, 0:n] / n
        filas = 8
        fila = np.floor(y * filas)
        xo = (x * 6 + 0.5 * (fila % 2)) % 1
        yo = (y * filas) % 1
        curva = np.sqrt(np.clip(1 - (2 * xo - 1) ** 2, 0, 1)) * (0.6 + 0.4 * yo)
        c_teja = acento if acento[0] > acento[2] else np.array([170, 70, 50.])
        img = _colorear(curva * 0.8 + fbm(n, rng, 4, 8) * 0.2, c_teja * 0.45, np.minimum(c_teja * 1.15, 255))
    else:  # piedra / roca / generico
        celdas = np.abs(fbm(n, rng, 5, 6) - 0.5) < 0.02
        img = _colorear(fbm(n, rng, 6, 4), np.array([85, 85, 88.]), np.array([155, 150, 145.]))
        img = img * 0.8 + oscuro * 0.2 + 15
        img = np.where(celdas[..., None], img * 0.55, img)

    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino)
    return destino


# ------------------------------------------------------------- skybox
CARAS = {  # nombre propiedad Roblox -> funcion (u, v) -> direccion (x, y, z)
    "SkyboxFt": lambda u, v: (u, -v, -np.ones_like(u)),
    "SkyboxBk": lambda u, v: (-u, -v, np.ones_like(u)),
    "SkyboxRt": lambda u, v: (np.ones_like(u), -v, u),
    "SkyboxLf": lambda u, v: (-np.ones_like(u), -v, -u),
    "SkyboxUp": lambda u, v: (u, np.ones_like(u), v),
    "SkyboxDn": lambda u, v: (u, -np.ones_like(u), -v),
}


def skybox(cielo: dict, destino_dir: Path, n: int = 512, semilla: int = 0) -> dict:
    """Genera 6 PNG coherentes calculando la direccion 3D de cada pixel."""
    rng = np.random.default_rng(semilla or 11)
    top, hor, bot = (hex_rgb(cielo[k]) for k in ("top", "horizon", "bottom"))
    sol = hex_rgb(cielo["sol"]) if cielo.get("sol") else None
    sol_dir = np.array([0.5, 0.35, -0.8])
    sol_dir /= np.linalg.norm(sol_dir)
    neb = hex_rgb(cielo["nebulosa"]) if cielo.get("nebulosa") else None
    ruido_nubes = fbm(512, rng, 6, 4)
    ruido_neb = fbm(512, rng, 5, 3)
    v, u = np.mgrid[-1:1:complex(0, n), -1:1:complex(0, n)]
    rutas = {}
    destino_dir.mkdir(parents=True, exist_ok=True)
    for cara, fn in CARAS.items():
        x, y, z = fn(u, v)
        L = np.sqrt(x * x + y * y + z * z)
        x, y, z = x / L, y / L, z / L
        elev = y
        t_up = np.clip(elev, 0, 1) ** 0.6
        t_dn = np.clip(-elev, 0, 1) ** 0.5
        col = hor * (1 - t_up)[..., None] + top * t_up[..., None]
        col = col * (1 - t_dn)[..., None] + bot * t_dn[..., None]
        # coordenadas esfericas para muestrear ruido sin costuras visibles
        lon = (np.arctan2(x, z) / (2 * np.pi) + 0.5) * 511
        lat = (np.arcsin(np.clip(y, -1, 1)) / np.pi + 0.5) * 511
        li, la = lon.astype(int) % 512, lat.astype(int) % 512
        if cielo.get("nubes", 0) > 0:
            mascara = np.clip((ruido_nubes[la, li] - (0.68 - cielo["nubes"] * 0.3)) * 5, 0, 1)
            mascara *= np.clip(elev * 5, 0, 1) * np.clip((1 - elev) * 6, 0, 1)
            blanco = np.minimum(hor * 1.3 + 40, 255)
            col = col * (1 - mascara[..., None] * 0.85) + blanco * mascara[..., None] * 0.85
        if neb is not None:
            m = np.clip(ruido_neb[la, li] * 1.6 - 0.6, 0, 1) ** 2
            col = col + neb * m[..., None] * 0.7
        if cielo.get("estrellas", 0) > 0:
            est = rng.random((n, n)) > (1 - 0.0025 * cielo["estrellas"])
            brillo = rng.uniform(150, 255, (n, n))
            col = np.where((est & (elev > -0.05))[..., None], np.maximum(col, brillo[..., None]), col)
        if sol is not None:
            d = x * sol_dir[0] + y * sol_dir[1] + z * sol_dir[2]
            halo = np.clip((d - 0.95) / 0.05, 0, 1) ** 3
            disco = (d > 0.9985).astype(float)
            col = col + sol * (halo * 0.6 + disco)[..., None]
        im = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.SMOOTH)
        ruta = destino_dir / f"{cara}.png"
        im.save(ruta)
        rutas[cara] = ruta
    return rutas
