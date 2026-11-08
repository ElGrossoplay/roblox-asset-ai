"""Iconos de juego procedurales (512x512 PNG con transparencia).

Estilos: "cartoon" (contorno grueso + brillo), "plano" (sin contorno),
"neon" (contorno luminoso), "pixel" (pixelado). Cada icono se dibuja con
mascaras en una grilla 0..1 y se compone con degradado, contorno, sombra y brillo.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .util import ajustar, rgb

S = 1024  # se dibuja al doble y se reduce (antialiasing)

# color por defecto y emoji de respaldo (cuando no hay ID subido en Roblox)
CATALOGO = {
    "moneda": ("#ffc93c", "🪙"), "gema": ("#38d9ff", "💎"), "corazon": ("#ff4d6d", "❤️"),
    "estrella": ("#ffd23f", "⭐"), "rayo": ("#ffe14d", "⚡"), "espada": ("#c9d6e3", "🗡️"),
    "escudo": ("#4d8dff", "🛡️"), "pocion": ("#b45cff", "🧪"), "llave": ("#ffc93c", "🔑"),
    "cofre": ("#c8803a", "🎁"), "trofeo": ("#ffc93c", "🏆"), "engranaje": ("#a7b1c2", "⚙️"),
    "candado": ("#ffc93c", "🔒"), "carrito": ("#3ddc84", "🛒"), "cerrar": ("#ff4d6d", "✖"),
    "mas": ("#3ddc84", "➕"), "calavera": ("#e9e4d8", "💀"), "reloj": ("#5ec8ff", "⏱️"),
    "mochila": ("#e07a3f", "🎒"), "fuego": ("#ff7a1a", "🔥"),
}


def _m():
    return Image.new("L", (S, S), 0)


def _P(pts):
    return [(x * S, y * S) for x, y in pts]


def _poli(pts):
    m = _m()
    ImageDraw.Draw(m).polygon(_P(pts), fill=255)
    return m


def _elipse(x0, y0, x1, y1):
    m = _m()
    ImageDraw.Draw(m).ellipse([x0 * S, y0 * S, x1 * S, y1 * S], fill=255)
    return m


def _rect(x0, y0, x1, y1, r=0.0):
    m = _m()
    ImageDraw.Draw(m).rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=r * S, fill=255)
    return m


def _union(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def _resta(a, b):
    return ImageChops.subtract(a, b)


def _estrella_pts(cx, cy, r1, r2, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = r1 if i % 2 == 0 else r2
        a = rot + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ------------------------------------------------------------- formas
# Cada forma devuelve lista de (mascara, color_hex). Las capas posteriores van encima.
def _formas(nombre, c):
    osc, cla = ajustar(c, -0.18), ajustar(c, 0.15)
    if nombre == "moneda":
        borde = _elipse(.12, .12, .88, .88)
        cara = _elipse(.22, .22, .78, .78)
        simbolo = _poli(_estrella_pts(.5, .52, .2, .09))
        return [(borde, osc), (cara, c), (simbolo, osc)]
    if nombre == "gema":
        cuerpo = _poli([(.2, .38), (.34, .18), (.66, .18), (.8, .38), (.5, .86)])
        top = _poli([(.2, .38), (.34, .18), (.66, .18), (.8, .38)])
        faceta = _poli([(.38, .38), (.62, .38), (.5, .86)])
        return [(cuerpo, osc), (top, cla), (faceta, c)]
    if nombre == "corazon":
        m = _union(_elipse(.13, .2, .53, .6), _elipse(.47, .2, .87, .6), _poli([(.155, .47), (.845, .47), (.5, .87)]))
        return [(m, c)]
    if nombre == "estrella":
        return [(_poli(_estrella_pts(.5, .53, .4, .18)), c)]
    if nombre == "rayo":
        return [(_poli([(.58, .08), (.22, .56), (.46, .56), (.36, .92), (.78, .42), (.54, .42), (.66, .08)]), c)]
    if nombre == "espada":
        hoja = _poli([(.5, .06), (.6, .18), (.6, .62), (.4, .62), (.4, .18)])
        guarda = _rect(.26, .6, .74, .69, .03)
        mango = _rect(.45, .68, .55, .86, .02)
        pomo = _elipse(.42, .84, .58, .96)
        return [(hoja, c), (guarda, "#c8913a"), (mango, "#6b3f22"), (pomo, "#c8913a")]
    if nombre == "escudo":
        m = _poli([(.5, .08), (.86, .2), (.82, .55), (.5, .92), (.18, .55), (.14, .2)])
        franja = _poli([(.5, .08), (.86, .2), (.82, .55), (.5, .92)])
        return [(m, c), (_resta(franja, _m()), osc), (_poli(_estrella_pts(.5, .45, .16, .07)), "#ffd23f")]
    if nombre == "pocion":
        frasco = _union(_elipse(.2, .36, .8, .92), _rect(.4, .16, .6, .44))
        liquido = _resta(_elipse(.24, .46, .76, .88), _rect(0, 0, 1, .58))
        tapon = _rect(.37, .08, .63, .2, .03)
        return [(frasco, "#d8ecf5"), (liquido, c), (tapon, "#8a5a32")]
    if nombre == "llave":
        aro = _resta(_elipse(.1, .1, .5, .5), _elipse(.21, .21, .39, .39))
        vara = _poli([(.38, .32), (.45, .25), (.9, .7), (.83, .77)])
        dientes = _union(_poli([(.66, .62), (.73, .55), (.84, .66), (.77, .73)]), _poli([(.56, .52), (.63, .45), (.72, .54), (.65, .61)]))
        return [(_union(aro, vara, dientes), c)]
    if nombre == "cofre":
        base = _rect(.1, .42, .9, .88, .05)
        tapa = _union(_rect(.1, .22, .9, .46, .12))
        banda = _union(_rect(.1, .42, .9, .5), _rect(.44, .22, .56, .88))
        cerrojo = _rect(.42, .4, .58, .58, .03)
        return [(base, c), (tapa, cla), (banda, "#ffc93c"), (cerrojo, "#7a5a1a")]
    if nombre == "trofeo":
        copa = _union(_poli([(.24, .12), (.76, .12), (.68, .48), (.5, .58), (.32, .48)]),
                      _resta(_elipse(.08, .16, .36, .46), _elipse(.15, .23, .3, .4)),
                      _resta(_elipse(.64, .16, .92, .46), _elipse(.7, .23, .85, .4)))
        pie = _union(_rect(.44, .56, .56, .74), _rect(.28, .74, .72, .88, .03))
        return [(copa, c), (pie, osc)]
    if nombre == "engranaje":
        dientes = _m()
        d = ImageDraw.Draw(dientes)
        for i in range(8):
            a = i * math.pi / 4
            pts = []
            for da, r in ((-.2, .25), (-.13, .44), (.13, .44), (.2, .25)):
                pts.append((.5 + r * math.cos(a + da), .5 + r * math.sin(a + da)))
            d.polygon(_P(pts), fill=255)
        m = _resta(_union(dientes, _elipse(.2, .2, .8, .8)), _elipse(.38, .38, .62, .62))
        return [(m, c)]
    if nombre == "candado":
        arco = _resta(_rect(.27, .1, .73, .6, .23), _rect(.37, .2, .63, .6, .13))
        cuerpo = _rect(.18, .42, .82, .9, .08)
        ojo = _union(_elipse(.44, .56, .56, .68), _rect(.47, .62, .53, .78))
        return [(arco, "#a7b1c2"), (cuerpo, c), (ojo, osc)]
    if nombre == "carrito":
        canasto = _poli([(.18, .26), (.88, .26), (.78, .62), (.28, .62)])
        mango = _union(_rect(.06, .18, .24, .25, .02), _poli([(.18, .2), (.24, .2), (.34, .66), (.28, .66)]))
        ruedas = _union(_elipse(.28, .7, .42, .84), _elipse(.66, .7, .8, .84))
        return [(_union(mango, ruedas), "#5b6474"), (canasto, c)]
    if nombre == "cerrar":
        a = _poli([(.22, .3), (.3, .22), (.78, .7), (.7, .78)])
        b = _poli([(.7, .22), (.78, .3), (.3, .78), (.22, .7)])
        return [(_rect(.08, .08, .92, .92, .2), c), (_union(a, b), "#ffffff")]
    if nombre == "mas":
        return [(_rect(.08, .08, .92, .92, .2), c), (_union(_rect(.42, .22, .58, .78, .03), _rect(.22, .42, .78, .58, .03)), "#ffffff")]
    if nombre == "calavera":
        craneo = _union(_elipse(.16, .1, .84, .7), _rect(.3, .55, .7, .86, .06))
        ojos = _union(_elipse(.27, .36, .45, .54), _elipse(.55, .36, .73, .54))
        nariz = _poli([(.5, .55), (.45, .65), (.55, .65)])
        dientes = _union(*[_rect(.34 + i * .085, .74, .4 + i * .085, .84) for i in range(4)])
        return [(craneo, c), (_union(ojos, nariz, dientes), "#2a2a2e")]
    if nombre == "reloj":
        arriba = _rect(.42, .06, .58, .16, .02)
        cara = _elipse(.12, .14, .88, .9)
        interior = _elipse(.2, .22, .8, .82)
        aguja = _union(_rect(.47, .3, .53, .54), _poli([(.47, .5), (.53, .5), (.68, .62), (.64, .66)]))
        return [(_union(arriba, cara), osc), (interior, "#ffffff"), (aguja, "#2a2a2e")]
    if nombre == "mochila":
        cuerpo = _rect(.2, .2, .8, .9, .18)
        asa = _resta(_rect(.34, .06, .66, .3, .12), _rect(.42, .12, .58, .3, .06))
        bolsillo = _rect(.3, .56, .7, .82, .08)
        return [(_union(cuerpo, asa), c), (bolsillo, osc)]
    if nombre == "fuego":
        ext = _union(_poli([(.5, .06), (.78, .44), (.84, .66), (.5, .94), (.16, .66), (.24, .4), (.36, .52)]),
                     _elipse(.16, .44, .84, .94))
        inte = _union(_poli([(.5, .38), (.66, .62), (.5, .88), (.34, .62)]), _elipse(.32, .58, .68, .9))
        return [(ext, c), (inte, "#ffe14d")]
    return [(_elipse(.12, .12, .88, .88), c)]


def _dilatar(m, px):
    """Dilatacion rapida (desenfoque + umbral) en vez de MaxFilter, que es lento."""
    if px <= 0:
        return m
    return m.filter(ImageFilter.GaussianBlur(px / 2)).point(lambda v: 255 if v > 18 else v * 14)


def _degradado(m, color, fuerza=0.22):
    claro, oscuro = np.array(rgb(ajustar(color, fuerza * .6))), np.array(rgb(ajustar(color, -fuerza)))
    t = np.linspace(0, 1, S)[:, None, None]
    arr = (claro * (1 - t) + oscuro * t).repeat(S, 1)
    im = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    im.putalpha(m)
    return im


def dibujar(nombre: str, color: str | None = None, estilo: str = "cartoon", tam: int = 512,
            contorno: str = "#1b1d24") -> Image.Image:
    color = color or CATALOGO.get(nombre, ("#ffc93c", ""))[0]
    capas = _formas(nombre, color)
    silueta = _union(*[m for m, _ in capas])
    lienzo = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    grosor = {"cartoon": 34, "neon": 22, "pixel": 30, "plano": 0}.get(estilo, 34)
    if estilo != "plano":  # sombra
        sombra = silueta.filter(ImageFilter.GaussianBlur(18))
        sombra = ImageChops.offset(sombra, 0, 22)
        capa = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        capa.putalpha(sombra.point(lambda v: v * 0.45))
        lienzo.alpha_composite(capa)
    if grosor:
        borde = _dilatar(silueta, grosor)
        col = rgb(color if estilo == "neon" else contorno)
        capa = Image.new("RGBA", (S, S), (*col, 0))
        capa.putalpha(borde)
        if estilo == "neon":
            glow = Image.new("RGBA", (S, S), (*col, 0))
            glow.putalpha(borde.filter(ImageFilter.GaussianBlur(30)))
            lienzo.alpha_composite(glow)
            lienzo.alpha_composite(glow)
        lienzo.alpha_composite(capa)
    for m, c in capas:
        lienzo.alpha_composite(_degradado(m, c, 0.0 if estilo == "plano" else 0.22))
    if estilo in ("cartoon", "neon"):  # brillo superior
        brillo = ImageChops.multiply(silueta, _elipse(.1, -.25, .9, .45))
        capa = Image.new("RGBA", (S, S), (255, 255, 255, 0))
        capa.putalpha(brillo.point(lambda v: v * 0.28))
        lienzo.alpha_composite(capa)
    im = lienzo.resize((tam, tam), Image.LANCZOS)
    if estilo == "pixel":
        im = im.resize((32, 32), Image.NEAREST).resize((tam, tam), Image.NEAREST)
    return im


def generar(nombres: list, destino_dir: Path, estilo: str = "cartoon", colores: dict | None = None,
            tam: int = 512) -> dict:
    destino_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for n in nombres:
        ruta = destino_dir / f"{n}.png"
        dibujar(n, (colores or {}).get(n), estilo, tam).save(ruta)
        out[n] = ruta
    return out
