"""GUI kits para Roblox: genera una interfaz REAL (ScreenGui editable), no solo imagenes.

Salidas:
  gui.json          especificacion (arbol de nodos) que lee el plugin / el script
  CrearGUI.lua      script para la Command Bar de Studio que construye el ScreenGui
  vista_previa.png  render de como se ve
  elementos/*.png   cada componente por separado (con transparencia)
  iconos/*.png      iconos usados (para subir y reemplazar los emoji de respaldo)

Formato de nodo:  {"c": clase, "n": nombre, "p": {props}, "d": {decoracion}, "i": icono, "h": [hijos]}
  Position/Size = [escalaX, offsetX, escalaY, offsetY]   AnchorPoint = [x, y]
  colores = "#rrggbb"   Font/TextXAlignment = nombre del Enum
"""
import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw

from . import iconos
from .util import ajustar, fuente, luminancia, mezclar, rgb, roles_ui

ESTILOS = {
    "cartoon":  {"fuente": "FredokaOne", "radio": 14, "borde": 3, "borde_rol": "contorno", "gradiente": True, "brillo": True, "icono": "cartoon", "texto_borde": True, "transp": 0.0},
    "scifi":    {"fuente": "Michroma", "radio": 3, "borde": 1.5, "borde_rol": "primario", "gradiente": True, "brillo": False, "icono": "neon", "texto_borde": False, "transp": 0.12},
    "fantasia": {"fuente": "Fantasy", "radio": 8, "borde": 2.5, "borde_rol": "oro", "gradiente": True, "brillo": True, "icono": "cartoon", "texto_borde": True, "transp": 0.0},
    "minimal":  {"fuente": "BuilderSansBold", "radio": 12, "borde": 0, "borde_rol": "contorno", "gradiente": False, "brillo": False, "icono": "plano", "texto_borde": False, "transp": 0.08},
    "terror":   {"fuente": "SpecialElite", "radio": 2, "borde": 2, "borde_rol": "peligro", "gradiente": True, "brillo": False, "icono": "plano", "texto_borde": False, "transp": 0.1},
    "pixel":    {"fuente": "Arcade", "radio": 0, "borde": 3, "borde_rol": "contorno", "gradiente": False, "brillo": False, "icono": "pixel", "texto_borde": True, "transp": 0.0},
}
ESTILO_POR_PRESET = {"terror": "terror", "espacio": "scifi", "cyberpunk": "scifi", "fantasia": "fantasia",
                     "desierto": "fantasia", "tropical": "cartoon", "bosque": "cartoon", "invierno": "cartoon"}


# ------------------------------------------------------------- construccion del spec
def _n(c, n, p=None, d=None, h=None, i=None):
    nodo = {"c": c, "n": n, "p": p or {}, "d": d or {}, "h": h or []}
    if i:
        nodo["i"] = i
        nodo["e"] = iconos.CATALOGO.get(i, ("", "?"))[1]
    return nodo


class Kit:
    def __init__(self, paleta, estilo="cartoon", ajustes=None):
        self.e = {**ESTILOS.get(estilo, ESTILOS["cartoon"]), **(ajustes or {})}
        self.estilo = estilo
        self.r = roles_ui(paleta)
        if ajustes:
            for k in ("primario", "acento", "panel", "fondo", "texto"):
                if ajustes.get(k):
                    self.r[k] = ajustes[k]
        self.r["contorno"] = ajustar(self.r["fondo"], -0.2)
        self.r["oro"] = "#d9a84a"

    # decoraciones
    def deco(self, color, radio=None, borde=True, brillo=None):
        e, r = self.e, self.r
        d = {"radio": e["radio"] if radio is None else radio}
        if borde and e["borde"]:
            d["borde"] = e["borde"]
            d["borde_color"] = r.get(e["borde_rol"], e["borde_rol"])
        if e["gradiente"]:
            d["grad"] = [ajustar(color, 0.08), ajustar(color, -0.1)]
        if (e["brillo"] if brillo is None else brillo):
            d["brillo"] = True
        return d

    def texto(self, n, txt, pos, tam, color=None, align="Center", ancla=(0, 0), maxsize=48):
        p = {"Position": pos, "Size": tam, "AnchorPoint": list(ancla), "BackgroundTransparency": 1,
             "Text": txt, "TextColor3": color or self.r["texto"], "Font": self.e["fuente"], "TextScaled": True,
             "TextXAlignment": align}
        if self.e["texto_borde"]:
            p["TextStrokeTransparency"] = 0.2
            p["TextStrokeColor3"] = self.r["contorno"]
        return _n("TextLabel", n, p, {"max_texto": maxsize})

    def panel(self, n, pos, tam, color=None, ancla=(0, 0), h=None, aspecto=None, visible=True, radio=None):
        color = color or self.r["panel"]
        d = self.deco(color, radio=radio, brillo=False)
        if aspecto:
            d["aspecto"] = aspecto
        return _n("Frame", n, {"Position": pos, "Size": tam, "AnchorPoint": list(ancla), "BackgroundColor3": color,
                               "BackgroundTransparency": self.e["transp"], "Visible": visible}, d, h)

    def boton(self, n, txt, pos, tam, color=None, icono=None, ancla=(0, 0), aspecto=None):
        color = color or self.r["primario"]
        txt_color = "#ffffff" if luminancia(color) < 0.78 else "#15171c"
        hijos = []
        if icono and txt:
            hijos.append(_n("Icono", "Icono", {"Position": [0.06, 0, 0.5, 0], "Size": [0.3, 0, 0.75, 0], "AnchorPoint": [0, 0.5]}, {"aspecto": 1}, i=icono))
            hijos.append(self.texto("Texto", txt, [0.38, 0, 0.5, 0], [0.56, 0, 0.6, 0], txt_color, "Left", (0, 0.5)))
        elif icono:
            hijos.append(_n("Icono", "Icono", {"Position": [0.5, 0, 0.5, 0], "Size": [0.72, 0, 0.72, 0], "AnchorPoint": [0.5, 0.5]}, {"aspecto": 1}, i=icono))
        else:
            hijos.append(self.texto("Texto", txt, [0.5, 0, 0.5, 0], [0.86, 0, 0.62, 0], txt_color, "Center", (0.5, 0.5)))
        d = self.deco(color)
        if aspecto:
            d["aspecto"] = aspecto
        p = {"Position": pos, "Size": tam, "AnchorPoint": list(ancla), "BackgroundColor3": color, "Text": "", "AutoButtonColor": True}
        return _n("TextButton", n, p, d, hijos)

    def barra(self, n, pos, tam, color, valor, texto, icono=None):
        fondo_barra = ajustar(self.r["fondo"], -0.05)
        relleno = _n("Frame", "Relleno", {"Size": [valor, 0, 1, 0], "BackgroundColor3": color},
                     self.deco(color, borde=False))
        hijos = [relleno, self.texto("Texto", texto, [0.5, 0, 0.5, 0], [0.9, 0, 0.7, 0], "#ffffff", "Center", (0.5, 0.5))]
        cont = _n("Frame", "Barra", {"Position": [0.17 if icono else 0, 0, 0.5, 0], "Size": [0.83 if icono else 1, 0, 0.62, 0],
                                     "AnchorPoint": [0, 0.5], "BackgroundColor3": fondo_barra}, self.deco(fondo_barra, brillo=False), hijos)
        cont["d"].pop("grad", None)
        items = [cont]
        if icono:
            items.insert(0, _n("Icono", "Icono", {"Position": [0, 0, 0.5, 0], "Size": [0.16, 0, 1, 0], "AnchorPoint": [0, 0.5]}, {"aspecto": 1}, i=icono))
        return _n("Frame", n, {"Position": pos, "Size": tam, "BackgroundTransparency": 1}, {}, items)

    def contador(self, n, icono, valor, pos, color):
        hijos = [_n("Icono", "Icono", {"Position": [0, -6, 0.5, 0], "Size": [0.3, 0, 1.25, 0], "AnchorPoint": [0, 0.5]}, {"aspecto": 1}, i=icono),
                 self.texto("Valor", valor, [0.33, 0, 0.5, 0], [0.48, 0, 0.66, 0], None, "Left", (0, 0.5)),
                 self.boton("Mas", "", [0.97, 0, 0.5, 0], [0.18, 0, 0.8, 0], self.r["exito"], "mas", (1, 0.5), 1)]
        hijos[2]["h"][0]["p"]["Size"] = [0.9, 0, 0.9, 0]
        return _n("Frame", n, {"Position": pos, "Size": [0.15, 0, 0.065, 0], "AnchorPoint": [1, 0], "BackgroundColor3": self.r["panel"],
                               "BackgroundTransparency": self.e["transp"]}, self.deco(self.r["panel"], radio=99, brillo=False), hijos)

    def titulo_panel(self, txt):
        r = self.r
        return [
            _n("Frame", "Encabezado", {"Size": [1, 0, 0.14, 0], "BackgroundColor3": r["primario"]},
               {**self.deco(r["primario"], borde=False), "radio": self.e["radio"]},
               [self.texto("Titulo", txt, [0.5, 0, 0.5, 0], [0.6, 0, 0.7, 0], "#ffffff" if luminancia(r["primario"]) < 0.78 else "#15171c", "Center", (0.5, 0.5))]),
            self.boton("Cerrar", "", [1, 8, 0, -8], [0, 54, 0, 54], r["peligro"], "cerrar", (0.5, 0.5), 1),
        ]


def construir(paleta: list, estilo: str = "cartoon", textos: dict | None = None, ajustes: dict | None = None) -> dict:
    k = Kit(paleta, estilo, ajustes)
    r = k.r
    t = {"tienda": "TIENDA", "inventario": "INVENTARIO", "monedas": "1,250", "gemas": "85", "nivel": "Nv 12",
         "aviso": "¡Conseguiste 50 monedas!", "jugar": "JUGAR", **(textos or {})}

    hud = _n("Frame", "HUD", {"Size": [1, 0, 1, 0], "BackgroundTransparency": 1}, {}, [
        k.contador("Monedas", "moneda", t["monedas"], [0.985, 0, 0.03, 0], r["primario"]),
        k.contador("Gemas", "gema", t["gemas"], [0.985, 0, 0.115, 0], r["acento"]),
        k.barra("BarraVida", [0.015, 0, 0.03, 0], [0.24, 0, 0.06, 0], r["exito"], 0.78, "78 / 100", "corazon"),
        _n("Frame", "Nivel", {"Position": [0.015, 0, 0.105, 0], "Size": [0.24, 0, 0.045, 0], "BackgroundTransparency": 1}, {}, [
            k.boton("Insignia", t["nivel"], [0, 0, 0.5, 0], [0.22, 0, 1.1, 0], r["acento"], None, (0, 0.5)),
            k.barra("BarraXP", [0.25, 0, 0, 0], [0.75, 0, 1, 0], r["acento"], 0.45, "450 / 1000"),
        ]),
    ])
    menu = _n("Frame", "MenuLateral", {"Position": [0.015, 0, 0.5, 0], "Size": [0.07, 0, 0.42, 0], "AnchorPoint": [0, 0.5],
                                       "BackgroundTransparency": 1}, {}, [
        k.boton("BotonTienda", "", [0, 0, 0, 0], [1, 0, 0.3, 0], r["primario"], "carrito", aspecto=1),
        k.boton("BotonInventario", "", [0, 0, 0.35, 0], [1, 0, 0.3, 0], r["acento"], "mochila", aspecto=1),
        k.boton("BotonAjustes", "", [0, 0, 0.7, 0], [1, 0, 0.3, 0], ajustar(r["panel"], 0.12), "engranaje", aspecto=1),
    ])
    for b, etiqueta in zip(menu["h"], ("Tienda", "Inventario", "Ajustes")):
        b["h"].append(k.texto("Etiqueta", etiqueta, [0.5, 0, 1, -2], [1.2, 0, 0.28, 0], None, "Center", (0.5, 0.5), 22))

    def carta(i, icono, nombre, precio):
        x = 0.05 + i * 0.315
        color_carta = ajustar(r["panel"], 0.06)
        return _n("Frame", f"Item{i + 1}", {"Position": [x, 0, 0.21, 0], "Size": [0.28, 0, 0.72, 0], "BackgroundColor3": color_carta},
                  k.deco(color_carta, brillo=False), [
            _n("Icono", "Icono", {"Position": [0.5, 0, 0.08, 0], "Size": [0.68, 0, 0.45, 0], "AnchorPoint": [0.5, 0]}, {"aspecto": 1}, i=icono),
            k.texto("Nombre", nombre, [0.5, 0, 0.6, 0], [0.9, 0, 0.12, 0], None, "Center", (0.5, 0)),
            k.boton("Comprar", precio, [0.5, 0, 0.94, 0], [0.82, 0, 0.17, 0], r["exito"], "moneda", (0.5, 1)),
        ])

    tienda = k.panel("PanelTienda", [0.5, 0, 0.53, 0], [0.46, 0, 0.6, 0], ancla=(0.5, 0.5), aspecto=1.42, h=[
        *k.titulo_panel(t["tienda"]),
        carta(0, "espada", "Espada", "250"), carta(1, "pocion", "Poción", "80"), carta(2, "escudo", "Escudo", "400"),
    ])
    slots = []
    llenos = ["espada", "pocion", "llave", "gema", "", "estrella", "", "", "cofre", "", "", "", "", "", ""]
    for i in range(15):
        fila, col = divmod(i, 5)
        color_slot = ajustar(r["panel"], 0.07)
        hijos = [_n("Icono", "Icono", {"Position": [0.5, 0, 0.5, 0], "Size": [0.72, 0, 0.72, 0], "AnchorPoint": [0.5, 0.5]}, {"aspecto": 1}, i=llenos[i])] if llenos[i] else []
        slots.append(_n("Frame", f"Slot{i + 1}", {"Position": [0.05 + col * 0.182, 0, 0.21 + fila * 0.255, 0], "Size": [0.16, 0, 0.23, 0],
                                                  "BackgroundColor3": color_slot}, {**k.deco(color_slot, brillo=False), "aspecto": 1}, hijos))
    inventario = k.panel("PanelInventario", [0.5, 0, 0.53, 0], [0.42, 0, 0.6, 0], ancla=(0.5, 0.5), aspecto=1.3, visible=False,
                         h=[*k.titulo_panel(t["inventario"]), *slots])
    aviso = k.panel("Aviso", [0.5, 0, 0.03, 0], [0.3, 0, 0.065, 0], ancla=(0.5, 0), radio=99, h=[
        _n("Icono", "Icono", {"Position": [0.03, 0, 0.5, 0], "Size": [0.16, 0, 0.9, 0], "AnchorPoint": [0, 0.5]}, {"aspecto": 1}, i="moneda"),
        k.texto("Texto", t["aviso"], [0.2, 0, 0.5, 0], [0.76, 0, 0.55, 0], None, "Left", (0, 0.5)),
    ])
    jugar = k.boton("BotonJugar", t["jugar"], [0.5, 0, 0.955, 0], [0.18, 0, 0.09, 0], r["primario"], None, (0.5, 1))
    return {
        "version": 1, "estilo": estilo, "roles": r, "fuente": k.e["fuente"],
        "raiz": _n("ScreenGui", "GUI_Kit", {"ResetOnSpawn": False, "IgnoreGuiInset": True, "ZIndexBehavior": "Sibling"}, {},
                   [hud, menu, tienda, inventario, aviso, jugar]),
    }


ARTE_POR_NOMBRE = {"PanelTienda": "panel", "PanelInventario": "panel", "Encabezado": "titulo", "Aviso": "titulo",
                   "Monedas": "titulo", "Gemas": "titulo", "Barra": "barra", "BotonJugar": "boton", "Comprar": "boton",
                   "BotonTienda": "boton", "Insignia": "boton", "BotonInventario": "boton2", "BotonAjustes": "boton2", "Mas": "boton2"}


def asignar_arte(spec: dict, arte: dict) -> dict:
    """Marca los nodos que usaran arte IA (9-slice). arte = {clave: ruta_png}."""
    from PIL import Image as _I
    spec["arte_tam"] = {k: list(_I.open(v).size) for k, v in arte.items()}

    def rec(n):
        clave = ARTE_POR_NOMBRE.get(n["n"]) or ("slot" if n["n"].startswith(("Item", "Slot")) else None)
        if clave and clave in arte:
            n["d"]["arte"] = clave
        for h in n.get("h", []):
            rec(h)
    rec(spec["raiz"])
    return spec


def iconos_usados(spec: dict) -> list:
    vistos = []

    def rec(n):
        if n.get("i") and n["i"] not in vistos:
            vistos.append(n["i"])
        for h in n.get("h", []):
            rec(h)
    rec(spec["raiz"])
    return vistos


# ------------------------------------------------------------- render (vista previa)
class Render:
    def __init__(self, w, h, estilo_icono, escala=2, arte=None, iconos_png=None):
        self.k = escala
        self.W, self.H = w * escala, h * escala
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.estilo_icono = estilo_icono
        self.cache = {}
        self.bbox = None
        self.arte = {k: Image.open(v).convert("RGBA") for k, v in (arte or {}).items()}
        self.iconos_png = iconos_png or {}

    def _rect(self, nodo, padre):
        px, py, pw, ph = padre
        p = nodo["p"]
        sx, ox, sy, oy = p.get("Size", [1, 0, 1, 0])
        w, h = pw * sx + ox * self.k, ph * sy + oy * self.k
        asp = nodo["d"].get("aspecto")
        if asp:
            if w / max(h, 1) > asp:
                w = h * asp
            else:
                h = w / asp
        x0, xo, y0, yo = p.get("Position", [0, 0, 0, 0])
        ax, ay = p.get("AnchorPoint", [0, 0])
        x = px + pw * x0 + xo * self.k - ax * w
        y = py + ph * y0 + yo * self.k - ay * h
        return x, y, w, h

    def _marcar(self, x, y, w, h):
        b = (x, y, x + w, y + h)
        self.bbox = b if self.bbox is None else (min(self.bbox[0], b[0]), min(self.bbox[1], b[1]), max(self.bbox[2], b[2]), max(self.bbox[3], b[3]))

    def _caja(self, x, y, w, h, d, color, transp):
        k = self.k
        rad = min(d.get("radio", 0) * k, w / 2, h / 2)
        capa = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(capa)
        alfa = int(255 * (1 - transp))
        if d.get("borde"):
            b = d["borde"] * k
            dr.rounded_rectangle([x - b, y - b, x + w + b, y + h + b], radius=rad + b, fill=(*rgb(d["borde_color"]), 255))
        mascara = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(mascara).rounded_rectangle([x, y, x + w, y + h], radius=rad, fill=alfa)
        if d.get("grad"):
            c1, c2 = (rgb(c) for c in d["grad"])
            grad = Image.new("RGBA", (1, 256))
            for i in range(256):
                t = i / 255
                grad.putpixel((0, i), tuple(int(a * (1 - t) + b * t) for a, b in zip(c1, c2)) + (255,))
            relleno = grad.resize((max(1, int(w)), max(1, int(h))))
            fondo = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            fondo.paste(relleno, (int(x), int(y)))
        else:
            fondo = Image.new("RGBA", self.img.size, (*rgb(color), 255))
        fondo.putalpha(mascara)
        capa.alpha_composite(fondo)
        if d.get("brillo"):
            brillo = Image.new("L", self.img.size, 0)
            ImageDraw.Draw(brillo).rounded_rectangle([x, y, x + w, y + h * 0.45], radius=rad, fill=50)
            blanco = Image.new("RGBA", self.img.size, (255, 255, 255, 0))
            blanco.putalpha(brillo)
            capa.alpha_composite(blanco)
        self.img.alpha_composite(capa)

    def _texto(self, x, y, w, h, p, d):
        txt = p.get("Text", "")
        if not txt:
            return
        maxsize = d.get("max_texto", 48) * self.k
        tam = int(min(h * 0.92, maxsize))
        f = fuente(tam)
        while tam > 8 and f.getlength(txt) > w:
            tam -= 2
            f = fuente(tam)
        dr = ImageDraw.Draw(self.img)
        tw = f.getlength(txt)
        align = p.get("TextXAlignment", "Center")
        tx = x if align == "Left" else (x + w - tw if align == "Right" else x + (w - tw) / 2)
        asc, desc = f.getmetrics()
        ty = y + (h - (asc + desc)) / 2
        borde = int(min(tam * 0.045, 3 * self.k)) if p.get("TextStrokeTransparency", 1) < 1 else 0
        dr.text((tx, ty), txt, font=f, fill=(*rgb(p.get("TextColor3", "#ffffff")), 255),
                stroke_width=borde, stroke_fill=(*rgb(p.get("TextStrokeColor3", "#000000")), 255))

    def _icono(self, x, y, w, h, nombre):
        lado = int(min(w, h))
        if lado < 4:
            return
        if nombre not in self.cache:
            ruta = self.iconos_png.get(nombre)
            self.cache[nombre] = Image.open(ruta).convert("RGBA").resize((256, 256)) if ruta else \
                iconos.dibujar(nombre, estilo=self.estilo_icono, tam=256)
        ic = self.cache[nombre].resize((lado, lado), Image.LANCZOS)
        self.img.alpha_composite(ic, (int(x + (w - lado) / 2), int(y + (h - lado) / 2)))

    def nodo(self, n, padre, forzar_visible=True):
        p, d = n["p"], n["d"]
        if not forzar_visible and p.get("Visible") is False:
            return
        if n["c"] == "ScreenGui":
            rect = padre
        else:
            rect = self._rect(n, padre)
            x, y, w, h = rect
            self._marcar(x - 6, y - 6, w + 12, h + 12)
            transp = p.get("BackgroundTransparency", 0)
            if d.get("arte") in self.arte:
                from ..ia.imagenes import nueve_partes
                pieza = nueve_partes(self.arte[d["arte"]], int(w), int(h))
                self.img.alpha_composite(pieza, (int(x), int(y)))
            elif n["c"] in ("Frame", "TextButton") and transp < 1:
                self._caja(x, y, w, h, d, p.get("BackgroundColor3", "#ffffff"), transp)
            if n["c"] == "Icono":
                self._icono(x, y, w, h, n["i"])
            elif n["c"] in ("TextLabel", "TextButton"):
                self._texto(x, y, w, h, p, d)
        for hijo in n.get("h", []):
            self.nodo(hijo, rect, True)


def _fondo_demo(w, h, roles):
    """Fondo tipo escena de juego para que la vista previa se lea bien."""
    arriba, abajo = rgb(mezclar(roles["primario"], "#87b8ff", 0.6)), rgb(mezclar(roles["fondo"], "#3a6b3a", 0.5))
    img = Image.new("RGB", (w, h))
    dr = ImageDraw.Draw(img)
    for yy in range(h):
        t = yy / h
        dr.line([(0, yy), (w, yy)], fill=tuple(int(a * (1 - t) + b * t) for a, b in zip(arriba, abajo)))
    return img.convert("RGBA")


def renderizar(spec: dict, destino: Path, w=1600, h=900, arte=None, iconos_png=None) -> Path:
    estilo_icono = ESTILOS.get(spec["estilo"], ESTILOS["cartoon"])["icono"]
    R = Render(w, h, estilo_icono, arte=arte, iconos_png=iconos_png)
    raiz = copy.deepcopy(spec["raiz"])
    for hijo in raiz["h"]:  # en la vista previa: inventario oculto, tienda visible
        if hijo["n"] == "PanelInventario":
            hijo["p"]["Visible"] = False
    for hijo in raiz["h"]:
        R.nodo(hijo, (0, 0, R.W, R.H), forzar_visible=False)
    final = _fondo_demo(R.W, R.H, spec["roles"])
    final.alpha_composite(R.img)
    final = final.resize((w, h), Image.LANCZOS).convert("RGB")
    destino.parent.mkdir(parents=True, exist_ok=True)
    final.save(destino)
    return destino


def exportar_elementos(spec: dict, destino_dir: Path, w=1600, h=900, arte=None, iconos_png=None) -> list:
    """Cada componente de primer nivel (y cada boton) como PNG transparente recortado."""
    estilo_icono = ESTILOS.get(spec["estilo"], ESTILOS["cartoon"])["icono"]
    destino_dir.mkdir(parents=True, exist_ok=True)
    rutas = []
    componentes = []
    for hijo in spec["raiz"]["h"]:
        if hijo["n"] in ("HUD", "MenuLateral"):
            componentes += [(c, hijo) for c in hijo["h"]]
        else:
            componentes.append((hijo, None))
    for nodo, padre in componentes:
        R = Render(w, h, estilo_icono, arte=arte, iconos_png=iconos_png)
        rect_padre = (0, 0, R.W, R.H)
        if padre is not None:
            rect_padre = R._rect(padre, rect_padre)
            R.bbox = None
        R.nodo(nodo, rect_padre, True)
        if not R.bbox:
            continue
        x0, y0, x1, y1 = (int(v) for v in R.bbox)
        recorte = R.img.crop((max(0, x0), max(0, y0), min(R.W, x1), min(R.H, y1)))
        recorte = recorte.resize((max(1, recorte.width // 2), max(1, recorte.height // 2)), Image.LANCZOS)
        ruta = destino_dir / f"{nodo['n']}.png"
        recorte.save(ruta)
        rutas.append(ruta)
    return rutas


# ------------------------------------------------------------- Luau
CONSTRUCTOR_LUAU = r'''
-- =====================================================================
--  GUI generada por Roblox Asset AI (estilo: __ESTILO__)
--  USO: View > Command Bar, pega TODO este script y presiona Enter.
--  Crea StarterGui.GUI_Kit con Frames, botones, UICorner, UIStroke y
--  UIGradient REALES: puedes editarlos como cualquier GUI de Roblox.
--  Los iconos usan emoji hasta que subas los PNG (la app rellena ICONOS).
-- =====================================================================
local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")

local ICONOS = __ICONOS__
local ARTE = __ARTE__  -- imagenes IA de botones/paneles (se activan al subir el kit)
local SPEC = HttpService:JSONDecode([==[__SPEC__]==])

local ENUMS = { Font = Enum.Font, TextXAlignment = Enum.TextXAlignment, TextYAlignment = Enum.TextYAlignment,
	ZIndexBehavior = Enum.ZIndexBehavior }

local function valor(k, v)
	if k == "Position" or k == "Size" then return UDim2.new(v[1], v[2], v[3], v[4]) end
	if k == "AnchorPoint" then return Vector2.new(v[1], v[2]) end
	if type(v) == "string" and string.sub(k, -6) == "Color3" then return Color3.fromHex(v) end
	if ENUMS[k] then
		local ok, item = pcall(function() return ENUMS[k][v] end)  -- un nombre invalido lanza error en Luau
		if ok and item then return item end
		return k == "Font" and Enum.Font.GothamBold or nil
	end
	return v
end

local function decorar(obj, d)
	if d.arte and ARTE[d.arte] and ARTE[d.arte] ~= "" then
		local tam = SPEC.arte_tam and SPEC.arte_tam[d.arte] or { 512, 512 }
		local mx, my = math.floor(tam[1] * 0.28), math.floor(tam[2] * 0.28)
		obj.BackgroundTransparency = 1
		local im = Instance.new("ImageLabel")
		im.Name = "Arte"
		im.BackgroundTransparency = 1
		im.Size = UDim2.fromScale(1, 1)
		im.Image = ARTE[d.arte]
		im.ScaleType = Enum.ScaleType.Slice
		im.SliceCenter = Rect.new(mx, my, tam[1] - mx, tam[2] - my)
		im.ZIndex = 0
		im.Parent = obj
		if d.aspecto then
			local a = Instance.new("UIAspectRatioConstraint")
			a.AspectRatio = d.aspecto
			a.Parent = obj
		end
		if d.max_texto then
			local t = Instance.new("UITextSizeConstraint")
			t.MaxTextSize = d.max_texto
			t.Parent = obj
		end
		return
	end
	if d.radio and d.radio > 0 then
		local c = Instance.new("UICorner")
		c.CornerRadius = d.radio >= 99 and UDim.new(0.5, 0) or UDim.new(0, d.radio)
		c.Parent = obj
	end
	if d.borde then
		local s = Instance.new("UIStroke")
		s.Thickness = d.borde
		s.Color = Color3.fromHex(d.borde_color)
		s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
		s.Parent = obj
	end
	if d.grad then
		obj.BackgroundColor3 = Color3.new(1, 1, 1)
		local g = Instance.new("UIGradient")
		g.Color = ColorSequence.new(Color3.fromHex(d.grad[1]), Color3.fromHex(d.grad[2]))
		g.Rotation = 90
		g.Parent = obj
	end
	if d.aspecto then
		local a = Instance.new("UIAspectRatioConstraint")
		a.AspectRatio = d.aspecto
		a.Parent = obj
	end
	if d.max_texto then
		local t = Instance.new("UITextSizeConstraint")
		t.MaxTextSize = d.max_texto
		t.Parent = obj
	end
	if d.brillo then
		local b = Instance.new("Frame")
		b.Name = "Brillo"
		b.BackgroundColor3 = Color3.new(1, 1, 1)
		b.BackgroundTransparency = 0.8
		b.BorderSizePixel = 0
		b.Size = UDim2.fromScale(1, 0.45)
		b.Active = false
		b.Parent = obj
		if d.radio and d.radio > 0 then
			local c = Instance.new("UICorner")
			c.CornerRadius = d.radio >= 99 and UDim.new(0.5, 0) or UDim.new(0, d.radio)
			c.Parent = b
		end
	end
end

local function construir(n, padre)
	local obj
	if n.c == "Icono" then
		local id = ICONOS[n.i]
		if id and id ~= "" then
			obj = Instance.new("ImageLabel")
			obj.Image = id
			obj.ScaleType = Enum.ScaleType.Fit
		else
			obj = Instance.new("TextLabel")
			obj.Text = n.e or "?"
			obj.TextScaled = true
			obj.Font = Enum.Font.GothamBold
		end
		obj.BackgroundTransparency = 1
	else
		obj = Instance.new(n.c)
	end
	obj.Name = n.n
	if obj:IsA("GuiObject") then obj.BorderSizePixel = 0 end
	for k, v in n.p do
		local ok, err = pcall(function() obj[k] = valor(k, v) end)
		if not ok then warn("[GUI_Kit] " .. n.n .. "." .. k .. ": " .. tostring(err)) end
	end
	decorar(obj, n.d or {})
	for _, h in n.h or {} do construir(h, obj) end
	obj.Parent = padre
	return obj
end

local viejo = StarterGui:FindFirstChild(SPEC.raiz.n)
if viejo then viejo:Destroy() end
local gui = construir(SPEC.raiz, StarterGui)

-- Control basico: abrir/cerrar paneles con los botones del menu
local control = Instance.new("LocalScript")
control.Name = "ControlPaneles"
local ok = pcall(function()
	control.Source = [==[
local gui = script.Parent
local function alternar(panel)
	for _, p in { gui.PanelTienda, gui.PanelInventario } do
		p.Visible = (p == panel) and not p.Visible
	end
end
gui.MenuLateral.BotonTienda.Activated:Connect(function() alternar(gui.PanelTienda) end)
gui.MenuLateral.BotonInventario.Activated:Connect(function() alternar(gui.PanelInventario) end)
gui.PanelTienda.Cerrar.Activated:Connect(function() gui.PanelTienda.Visible = false end)
gui.PanelInventario.Cerrar.Activated:Connect(function() gui.PanelInventario.Visible = false end)
gui.BotonJugar.Activated:Connect(function() gui.BotonJugar.Visible = false end)
task.delay(4, function() if gui:FindFirstChild("Aviso") then gui.Aviso.Visible = false end end)
]==]
end)
if ok then control.Parent = gui else control:Destroy() end
print("[GUI_Kit] Creada en StarterGui. Presiona Play para probarla.")
'''


def script_luau(spec: dict, ids: dict | None = None, ids_arte: dict | None = None) -> str:
    ids, ids_arte = ids or {}, ids_arte or {}
    tabla = "{\n" + "".join(f'\t["{n}"] = "{("rbxassetid://" + ids[n]) if ids.get(n) else ""}",\n'
                            for n in iconos_usados(spec)) + "}"
    tabla_arte = "{\n" + "".join(f'\t["{k}"] = "{("rbxassetid://" + ids_arte[k]) if ids_arte.get(k) else ""}",\n'
                                  for k in spec.get("arte_tam", {})) + "}"
    return (CONSTRUCTOR_LUAU.replace("__ESTILO__", spec["estilo"]).replace("__ICONOS__", tabla).replace("__ARTE__", tabla_arte)
            .replace("__SPEC__", json.dumps(spec, ensure_ascii=False)))
