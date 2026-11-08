"""Utilidades compartidas: fuentes, colores y paletas (incluye 'copiar estilo' de una imagen)."""
import base64
import colorsys
import io
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

from ..paths import ROOT

FONT_DIR = ROOT / "assets" / "fonts"
_FUENTES_SISTEMA = [
    r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def fuentes_disponibles() -> dict:
    out = {p.stem: str(p) for p in sorted(FONT_DIR.glob("*.[ot]tf"))}
    for p in _FUENTES_SISTEMA:
        if os.path.exists(p):
            out.setdefault(Path(p).stem, p)
    return out


def fuente(tam: int, nombre: str | None = None) -> ImageFont.FreeTypeFont:
    fs = fuentes_disponibles()
    ruta = fs.get(nombre or "") or fs.get("Poppins-Bold") or next(iter(fs.values()), None)
    if ruta:
        return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default(tam)


# ------------------------------------------------------------- color
def rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c[:3])


def luminancia(h: str) -> float:
    r, g, b = (v / 255 for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ajustar(h: str, luz: float = 0.0, sat: float = 0.0) -> str:
    r, g, b = (v / 255 for v in rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0, min(1, l + luz))
    s = max(0, min(1, s + sat))
    return hexc([v * 255 for v in colorsys.hls_to_rgb(hh, l, s)])


def mezclar(a: str, b: str, t: float) -> str:
    ca, cb = np.array(rgb(a), float), np.array(rgb(b), float)
    return hexc(ca * (1 - t) + cb * t)


def saturacion(h: str) -> float:
    r, g, b = (v / 255 for v in rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[2]


# ------------------------------------------------------------- paletas
def paleta_desde_imagen(datos: bytes, k: int = 6) -> list:
    """K-means simple sobre los pixeles: devuelve k colores ordenados por presencia."""
    im = Image.open(io.BytesIO(datos)).convert("RGB")
    im.thumbnail((160, 160))
    px = np.asarray(im, float).reshape(-1, 3)
    rng = np.random.default_rng(0)
    centros = px[rng.choice(len(px), k, replace=False)]
    for _ in range(20):
        d = ((px[:, None, :] - centros[None]) ** 2).sum(-1)
        etiqueta = d.argmin(1)
        nuevos = np.array([px[etiqueta == i].mean(0) if np.any(etiqueta == i) else centros[i] for i in range(k)])
        if np.allclose(nuevos, centros, atol=0.5):
            break
        centros = nuevos
    cuenta = np.bincount(etiqueta, minlength=k)
    return [hexc(centros[i]) for i in np.argsort(-cuenta)]


def paleta_desde_base64(b64: str) -> list:
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return paleta_desde_imagen(base64.b64decode(b64))


def roles_ui(paleta: list) -> dict:
    """Asigna roles de interfaz (fondo, panel, primario, acento, texto) a una paleta cualquiera."""
    p = list(dict.fromkeys(paleta)) or ["#1e2230", "#00a2ff", "#ffcc00"]
    oscuros = sorted(p, key=luminancia)
    vivos = sorted(p, key=lambda c: -(saturacion(c) * 0.7 + (0.3 if 0.25 < luminancia(c) < 0.85 else 0)))
    fondo = oscuros[0] if luminancia(oscuros[0]) < 0.3 else ajustar(oscuros[0], -0.3)
    primario = vivos[0]
    acento = vivos[1] if len(vivos) > 1 else primario
    if acento == primario or acento == fondo:
        acento = ajustar(primario, 0.25, 0.1)
    panel = ajustar(mezclar(fondo, primario, 0.2), 0.1 if luminancia(fondo) < 0.12 else 0.04)
    texto = "#ffffff" if luminancia(panel) < 0.55 else "#15171c"
    return {"fondo": fondo, "panel": panel, "primario": primario, "acento": acento,
            "texto": texto, "borde": ajustar(fondo, -0.12), "peligro": "#e5484d", "exito": "#3ddc84"}
