"""Utilidades de imagen para assets generados por IA."""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def hacer_tileable(img: Image.Image, mezcla: float = 0.45) -> Image.Image:
    """Convierte cualquier imagen en textura sin costuras.
    Bordes: se toman de la imagen desplazada media vuelta (sus bordes son el centro original, continuo).
    Centro: se toma la imagen original (ahi la desplazada tiene la costura)."""
    img = img.convert("RGB")
    w, h = img.size
    a = np.asarray(img, float)
    desplazada = np.roll(np.roll(a, w // 2, 1), h // 2, 0)
    y, x = np.mgrid[0:h, 0:w]
    d = np.maximum(np.abs(x - w / 2) / (w / 2), np.abs(y - h / 2) / (h / 2))
    m = np.clip((1 - d) / mezcla, 0, 1)
    m = (m * m * (3 - 2 * m))[..., None]
    out = desplazada * (1 - m) + a * m
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def equirect_a_cubo(pano: Image.Image, destino_dir: Path, tam: int = 1024) -> dict:
    """Panorama 2:1 -> 6 caras de Sky de Roblox (SkyboxBk/Dn/Ft/Lf/Rt/Up)."""
    from ..generators.image_offline import CARAS
    P = np.asarray(pano.convert("RGB"), float)
    H, W = P.shape[:2]
    v, u = np.mgrid[-1:1:complex(0, tam), -1:1:complex(0, tam)]
    destino_dir.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for cara, fn in CARAS.items():
        x, y, z = fn(u, v)
        L = np.sqrt(x * x + y * y + z * z)
        x, y, z = x / L, y / L, z / L
        lon = np.arctan2(x, -z)
        lat = np.arcsin(np.clip(y, -1, 1))
        px = ((lon / (2 * math.pi) + 0.5) * (W - 1)).astype(int) % W
        py = np.clip(((0.5 - lat / math.pi) * (H - 1)).astype(int), 0, H - 1)
        im = Image.fromarray(P[py, px].astype(np.uint8)).filter(ImageFilter.SMOOTH)
        ruta = destino_dir / f"{cara}.png"
        im.save(ruta)
        rutas[cara] = ruta
    return rutas


def nueve_partes(img: Image.Image, ancho: int, alto: int, margen: float = 0.28) -> Image.Image:
    """Escala una imagen de marco/boton sin deformar las esquinas (9-slice), como ScaleType.Slice de Roblox."""
    img = img.convert("RGBA")
    w, h = img.size
    mx, my = int(w * margen), int(h * margen)
    esc = min(1.0, ancho / (2 * mx + 1), alto / (2 * my + 1))
    cx, cy = max(1, int(mx * esc)), max(1, int(my * esc))
    out = Image.new("RGBA", (max(1, ancho), max(1, alto)), (0, 0, 0, 0))
    cols = [(0, mx, 0, cx), (mx, w - mx, cx, ancho - cx), (w - mx, w, ancho - cx, ancho)]
    filas = [(0, my, 0, cy), (my, h - my, cy, alto - cy), (h - my, h, alto - cy, alto)]
    for sx0, sx1, dx0, dx1 in cols:
        for sy0, sy1, dy0, dy1 in filas:
            if dx1 - dx0 < 1 or dy1 - dy0 < 1 or sx1 - sx0 < 1 or sy1 - sy0 < 1:
                continue
            out.alpha_composite(img.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS), (dx0, dy0))
    return out
