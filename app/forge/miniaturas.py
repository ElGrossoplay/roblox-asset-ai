"""Miniaturas (1920x1080) e icono de juego (512x512) estilo Roblox, con titulo grande.

Fondo: "rayos" (sunburst), "escena" (cielo + colinas), "degradado", o una imagen
propia/generada por IA (fondo_ruta). Encima: titulo con contorno, cinta de
subtitulo e iconos flotantes.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import iconos
from .util import ajustar, fuente, luminancia, mezclar, rgb, roles_ui


def _degradado(w, h, c1, c2, vertical=True):
    t = np.linspace(0, 1, h if vertical else w)
    a, b = np.array(rgb(c1), float), np.array(rgb(c2), float)
    fila = (a[None] * (1 - t[:, None]) + b[None] * t[:, None])
    arr = np.repeat(fila[:, None, :], w, 1) if vertical else np.repeat(fila[None, :, :], h, 0)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def _rayos(w, h, c1, c2, n=18):
    img = Image.new("RGB", (w, h), rgb(c1))
    d = ImageDraw.Draw(img)
    cx, cy, R = w / 2, h * 0.55, max(w, h) * 1.2
    for i in range(n):
        if i % 2:
            continue
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=rgb(c2))
    brillo = Image.new("L", (w, h), 0)
    ImageDraw.Draw(brillo).ellipse([cx - w * 0.35, cy - h * 0.45, cx + w * 0.35, cy + h * 0.45], fill=150)
    img = Image.composite(Image.new("RGB", (w, h), rgb(ajustar(c2, 0.25))), img, brillo.filter(ImageFilter.GaussianBlur(w * 0.08)))
    return img


def _escena(w, h, r, rng):
    img = _degradado(w, h, mezclar(r["fondo"], r["primario"], 0.45), mezclar(r["acento"], r["panel"], 0.4))
    d = ImageDraw.Draw(img)
    for capa in range(3):
        base = h * (0.62 + capa * 0.11)
        color = rgb(ajustar(mezclar(r["fondo"], r["primario"], 0.35 - capa * 0.1), 0.06 - capa * 0.06))
        pts = [(0, h)]
        fase = rng.uniform(0, 6)
        for x in range(0, w + 40, 40):
            pts.append((x, base - h * 0.08 * math.sin(x / w * (3 + capa) + fase) - h * 0.03 * math.sin(x / w * 11 + fase)))
        pts.append((w, h))
        d.polygon(pts, fill=color)
    return img


def _viñeta(img, fuerza=0.55):
    w, h = img.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([-w * 0.15, -h * 0.25, w * 1.15, h * 1.25], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w * 0.08))
    oscuro = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, Image.blend(img, oscuro, fuerza), m)


def _texto_grande(lienzo, txt, caja, color, contorno, nombre_fuente=None, rot=-3):
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    lineas = txt.upper().split("\n")
    tam = int(h / len(lineas) * 0.9)
    f = fuente(tam, nombre_fuente)
    while tam > 20 and max(f.getlength(l) for l in lineas) > w * 0.92:
        tam -= 4
        f = fuente(tam, nombre_fuente)
    borde = max(4, tam // 9)
    capa = Image.new("RGBA", (int(w + borde * 6), int(h + borde * 6)), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    alto_linea = tam * 1.02
    total = alto_linea * len(lineas)
    y = (capa.height - total) / 2
    for l in lineas:
        tw = f.getlength(l)
        x = (capa.width - tw) / 2
        d.text((x, y + borde * 0.9), l, font=f, fill=(0, 0, 0, 120), stroke_width=borde, stroke_fill=(0, 0, 0, 120))
        d.text((x, y), l, font=f, fill=(*rgb(color), 255), stroke_width=borde, stroke_fill=(*rgb(contorno), 255))
        y += alto_linea
    # degradado dentro de las letras (brillo arriba)
    mascara_txt = Image.new("L", capa.size, 0)
    dm = ImageDraw.Draw(mascara_txt)
    y = (capa.height - total) / 2
    for l in lineas:
        dm.text(((capa.width - f.getlength(l)) / 2, y), l, font=f, fill=255)
        y += alto_linea
    brillo = _degradado(capa.width, capa.height, ajustar(color, 0.25), ajustar(color, -0.15)).convert("RGBA")
    brillo.putalpha(mascara_txt)
    capa.alpha_composite(brillo)
    capa = capa.rotate(rot, resample=Image.BICUBIC, expand=True)
    lienzo.alpha_composite(capa, (int(x0 + (w - capa.width) / 2), int(y0 + (h - capa.height) / 2)))


def _cinta(lienzo, txt, cy, color, nombre_fuente=None):
    W = lienzo.width
    f = fuente(int(lienzo.height * 0.055), nombre_fuente)
    tw = f.getlength(txt.upper())
    ancho, alto = tw + lienzo.height * 0.12, lienzo.height * 0.085
    x0 = (W - ancho) / 2
    d = ImageDraw.Draw(lienzo)
    d.rounded_rectangle([x0, cy, x0 + ancho, cy + alto], radius=alto / 2, fill=(*rgb(color), 255),
                        outline=(*rgb(ajustar(color, -0.3)), 255), width=max(3, int(alto * 0.08)))
    texto_color = (255, 255, 255, 255) if luminancia(color) < 0.75 else (20, 20, 24, 255)
    asc, desc = f.getmetrics()
    d.text(((W - tw) / 2, cy + (alto - asc - desc) / 2), txt.upper(), font=f, fill=texto_color)


def generar(titulo: str, destino_dir: Path, paleta: list, subtitulo: str = "", lista_iconos=None,
            fondo: str = "rayos", fondo_ruta: Path | None = None, estilo_icono: str = "cartoon",
            nombre_fuente: str | None = None, semilla: int = 0, icono_png: Path | None = None) -> dict:
    rng = np.random.default_rng(semilla or abs(hash(titulo)) % 2**32)
    r = roles_ui(paleta)
    lista_iconos = lista_iconos or ["moneda", "gema", "estrella"]
    destino_dir.mkdir(parents=True, exist_ok=True)
    salidas = {}
    for nombre, (W, H) in {"miniatura": (1920, 1080), "icono_juego": (512, 512)}.items():
        if fondo_ruta and Path(fondo_ruta).exists():
            base = ImageOps.fit(Image.open(fondo_ruta).convert("RGB"), (W, H), Image.LANCZOS)
        elif fondo == "escena":
            base = _escena(W, H, r, rng)
        elif fondo == "degradado":
            base = _degradado(W, H, ajustar(r["primario"], 0.1), ajustar(r["fondo"], 0.05))
        else:
            base = _rayos(W, H, ajustar(r["primario"], -0.08), ajustar(r["primario"], 0.06))
        base = _viñeta(base, 0.45).convert("RGBA")

        if nombre == "miniatura" and not (fondo_ruta and Path(fondo_ruta).exists()):
            # iconos flotantes a los costados (solo con fondo procedural; el arte IA ya trae su escena)
            posiciones = [(0.1, 0.25, 0.24, -18), (0.88, 0.22, 0.2, 15), (0.12, 0.78, 0.2, 12),
                          (0.9, 0.76, 0.24, -12), (0.78, 0.05, 0.12, 25), (0.2, 0.05, 0.11, -25)]
            for i, (px, py, esc, rot) in enumerate(posiciones):
                ic = iconos.dibujar(lista_iconos[i % len(lista_iconos)], estilo=estilo_icono, tam=int(H * esc)).rotate(rot, expand=True, resample=Image.BICUBIC)
                base.alpha_composite(ic, (int(W * px - ic.width / 2), int(H * py - ic.height / 2 + H * 0.1)))
        if nombre == "miniatura":
            _texto_grande(base, titulo, (W * 0.12, H * 0.2, W * 0.88, H * 0.66), "#ffffff" if luminancia(r["primario"]) < 0.8 else r["acento"],
                          ajustar(r["fondo"], -0.15), nombre_fuente)
            if subtitulo:
                _cinta(base, subtitulo, H * 0.72, r["acento"], nombre_fuente)
        else:
            ic = (Image.open(icono_png).convert("RGBA").resize((int(H * 0.62),) * 2, Image.LANCZOS) if icono_png
                  else iconos.dibujar(lista_iconos[0], estilo=estilo_icono, tam=int(H * 0.62)))
            base.alpha_composite(ic, (int((W - ic.width) / 2), int(H * 0.06)))
            corto = ""
            for palabra in titulo.replace("\n", " ").split():
                if len((corto + " " + palabra).strip()) > 12:
                    break
                corto = (corto + " " + palabra).strip()
            corto = corto or titulo[:12]
            _texto_grande(base, corto, (W * 0.04, H * 0.66, W * 0.96, H * 0.96), "#ffffff", ajustar(r["fondo"], -0.15), nombre_fuente, rot=0)
        ruta = destino_dir / f"{nombre}.png"
        base.convert("RGB").save(ruta)
        salidas[nombre] = ruta
    return salidas
