"""Quitar fondo de imagenes generadas (sin modelos extra).

Los prompts piden el objeto "aislado sobre fondo blanco/liso". Aqui se estima el color de
fondo desde los bordes, se inunda desde los bordes con tolerancia y se suavizan los bordes
(anti-aliasing + eliminacion del halo del color de fondo).
Si tienes `rembg` instalado, se usa automaticamente (mejor para fondos complejos).
"""
import numpy as np
from PIL import Image, ImageFilter


def _con_rembg(img: Image.Image):
    try:
        from rembg import remove  # opcional
    except ImportError:
        return None
    try:
        return remove(img)
    except Exception:  # noqa: BLE001
        return None


def quitar_fondo(img: Image.Image, tolerancia: float = 0.12, usar_rembg=True) -> Image.Image:
    img = img.convert("RGB")
    if usar_rembg:
        r = _con_rembg(img)
        if r is not None:
            return r.convert("RGBA")
    a = np.asarray(img, float) / 255
    h, w, _ = a.shape
    borde = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    fondo = np.median(borde, 0)
    dist = np.sqrt(((a - fondo) ** 2).sum(-1)) / np.sqrt(3)
    parecido = dist < tolerancia
    # inundacion desde los bordes (solo el fondo conectado, no zonas claras del objeto).
    # Se calcula a baja resolucion (rapido) y luego se escala.
    esc = max(1, max(h, w) // 320)
    peq = parecido[::esc, ::esc]
    mascara = np.zeros_like(peq)
    mascara[0, :], mascara[-1, :], mascara[:, 0], mascara[:, -1] = peq[0, :], peq[-1, :], peq[:, 0], peq[:, -1]
    for _ in range(max(peq.shape) * 2):
        nueva = mascara.copy()
        nueva[1:] |= mascara[:-1]
        nueva[:-1] |= mascara[1:]
        nueva[:, 1:] |= mascara[:, :-1]
        nueva[:, :-1] |= mascara[:, 1:]
        nueva &= peq
        if np.array_equal(nueva, mascara):
            break
        mascara = nueva
    mascara = np.asarray(Image.fromarray(mascara.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 127
    mascara &= parecido | (dist < tolerancia * 1.6)
    alfa = (~mascara).astype(float)
    # borde suave: alfa proporcional a la distancia al color de fondo cerca del contorno
    suave = np.clip((dist - tolerancia * 0.4) / (tolerancia * 1.2), 0, 1)
    cerca = np.asarray(Image.fromarray((alfa * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)), float) / 255
    alfa = np.where((cerca > 0) & (alfa < 1), suave, alfa)
    alfa = np.asarray(Image.fromarray((alfa * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), float) / 255
    # quitar el halo del color de fondo (des-mezcla)
    al = np.clip(alfa, 1e-3, 1)[..., None]
    rgb = np.clip((a - fondo * (1 - al)) / al, 0, 1)
    out = np.dstack([rgb, alfa])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def recortar(img: Image.Image, margen: float = 0.06, cuadrado=True) -> Image.Image:
    caja = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    if not caja:
        return img
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    lado = max(w, h) if cuadrado else None
    m = int((lado or max(w, h)) * margen)
    if cuadrado:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        lado += 2 * m
        lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        lienzo.alpha_composite(img.crop(caja), (int(lado / 2 - w / 2), int(lado / 2 - h / 2)))
        return lienzo
    return img.crop((max(0, x0 - m), max(0, y0 - m), x1 + m, y1 + m))
