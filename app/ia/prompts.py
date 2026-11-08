"""Plantillas de prompt por tipo de asset (en ingles: los modelos de imagen/3D/audio rinden mejor),
traduccion ES->EN y division de pedidos en elementos ("moneda, gema y cofre" -> 3 elementos)."""
import re

from . import motor

ESTILOS_ARTE = {
    "cartoon": "glossy cartoon style, bold dark outline, vibrant saturated colors, soft shading, roblox simulator game style",
    "plano": "flat vector style, clean shapes, minimal shading, modern mobile game style",
    "neon": "neon glowing edges, sci-fi, dark outline, cyan and magenta glow",
    "pixel": "pixel art, 32x32 sprite, crisp pixels, limited palette, retro game",
    "realista": "highly detailed 3d render, PBR materials, studio lighting, octane render",
    "anime": "anime cel-shaded style, clean lineart, vibrant colors",
    "fantasia": "fantasy rpg style, ornate gold details, painterly, hand-painted",
    "terror": "dark horror style, grungy, desaturated, eerie",
    "low_poly": "low poly 3d render, flat shaded facets, stylized",
}

PALABRAS_ESTILO = {"cartoon": ["cartoon", "caricatura", "simulador", "tierno", "cute"], "plano": ["plano", "flat", "minimal"],
                   "neon": ["neon", "neón", "cyber"], "pixel": ["pixel", "8bit", "8-bit", "retro"], "realista": ["realista", "realistic", "hd"],
                   "anime": ["anime", "manga"], "fantasia": ["fantasia", "fantasía", "medieval", "rpg"], "terror": ["terror", "horror", "miedo"],
                   "low_poly": ["low poly", "lowpoly", "low-poly"]}

DICCIONARIO = {
    "moneda": "gold coin", "monedas": "gold coins", "gema": "gem", "diamante": "diamond", "corazon": "heart", "corazón": "heart",
    "estrella": "star", "rayo": "lightning bolt", "espada": "sword", "escudo": "shield", "pocion": "potion", "poción": "potion",
    "llave": "key", "cofre": "treasure chest", "trofeo": "trophy", "engranaje": "gear", "candado": "padlock", "carrito": "shopping cart",
    "mochila": "backpack", "fuego": "fire", "calavera": "skull", "reloj": "clock", "mascota": "pet", "huevo": "egg", "perro": "dog",
    "gato": "cat", "dragon": "dragon", "dragón": "dragon", "pizza": "pizza", "hamburguesa": "burger", "arbol": "tree", "árbol": "tree",
    "casa": "house", "castillo": "castle", "torre": "tower", "roca": "rock", "piedra": "stone", "auto": "car", "coche": "car",
    "nave": "spaceship", "cohete": "rocket", "planeta": "planet", "pistola": "pistol", "arco": "bow", "flecha": "arrow",
    "hacha": "axe", "pico": "pickaxe", "martillo": "hammer", "varita": "magic wand", "libro": "book", "mapa": "map", "bomba": "bomb",
    "pez": "fish", "caña de pescar": "fishing rod", "barco": "boat", "isla": "island", "pueblo": "village", "bosque": "forest",
    "espacio": "space", "terror": "horror", "tienda": "shop", "dulces": "candy", "helado": "ice cream", "fruta": "fruit",
    "manzana": "apple", "banana": "banana", "rojo": "red", "roja": "red", "azul": "blue", "verde": "green", "amarillo": "yellow",
    "amarilla": "yellow", "morado": "purple", "morada": "purple", "dorado": "golden", "dorada": "golden", "negro": "black",
    "negra": "black", "blanco": "white", "blanca": "white", "rosa": "pink", "naranja": "orange", "grande": "big", "pequeño": "small",
    "explosion": "explosion", "explosión": "explosion", "salto": "jump", "pasos": "footsteps", "lluvia": "rain", "viento": "wind",
    "golpe": "punch impact", "disparo": "gunshot", "puerta": "door", "magia": "magic", "hechizo": "magic spell", "agua": "water",
    "musica": "music", "música": "music", "epica": "epic", "épica": "epic", "alegre": "happy", "triste": "sad", "tranquila": "calm",
    "personaje": "character", "guerrero": "warrior", "mago": "wizard", "robot": "robot", "zombie": "zombie", "ninja": "ninja",
    "pirata": "pirate", "caballero": "knight", "princesa": "princess", "chico": "boy", "chica": "girl", "con": "with", "de": "of",
    "y": "and", "el": "the", "la": "the", "un": "a", "una": "a", "madera": "wooden", "metal": "metal", "hielo": "ice", "lava": "lava",
}


_cache_tr = {}


def traducir(texto: str, log=print) -> str:
    """ES -> EN. Usa el LLM gratis si esta disponible; si no, un diccionario basico."""
    t = (texto or "").strip()
    if not t:
        return t
    if t in _cache_tr:
        return _cache_tr[t]
    _cache_tr[t] = _traducir(t)
    return _cache_tr[t]


def _traducir(t: str) -> str:
    if motor.disponible():
        try:
            r = motor.texto("Translate the user's text to natural English for an AI image/audio generator. "
                            "Reply ONLY with the translation, no quotes.", t, lambda *_: None, max_tokens=200)
            r = r.strip().strip('"').splitlines()[0] if r.strip() else ""
            if r and len(r) < len(t) * 4 + 40 and not r.lower().startswith(("sorry", "i can", "i'm")):
                return r
        except Exception:  # noqa: BLE001
            pass
    frases = sorted(DICCIONARIO, key=len, reverse=True)
    out = " " + t.lower() + " "
    for es in frases:
        out = re.sub(rf"(?<![\wáéíóúñ]){re.escape(es)}(?![\wáéíóúñ])", DICCIONARIO[es], out)
    return re.sub(r"\s+", " ", out).strip()


def estilo_de(prompt: str, defecto="cartoon") -> str:
    t = prompt.lower()
    for e, ws in PALABRAS_ESTILO.items():
        if any(w in t for w in ws):
            return e
    return defecto


RELLENO = r"^(haz(me)?|crea(me)?|genera(me)?|quiero|dame|unos?|unas?|el|la|los|las|de|del|para|mi|mis|un set de|set de|pack de|" \
          r"iconos?|íconos?|icons?|efectos?( de sonido)?|sonidos?|sfx|modelos?( 3d)?|props?|3d|objetos?|estilo \w+)\s+"


def elementos(prompt: str, maximo=12) -> list:
    """'iconos de moneda, gema y cofre estilo neon' -> ['moneda', 'gema', 'cofre']"""
    t = prompt.strip()
    t = re.sub(r"\b(estilo|style|tipo)\s+[\wáéíóú\-]+", "", t, flags=re.I)
    for _ in range(6):
        t = re.sub(RELLENO, "", t, flags=re.I).strip()
    partes = re.split(r",|;|\s+y\s+|\s+e\s+|\s+and\s+|\n", t)
    partes = [p.strip(" .:-") for p in partes if p.strip(" .:-")]
    return partes[:maximo] or [prompt]


# ------------------------------------------------------------- plantillas
FONDO = "isolated on a plain pure white background, centered, no text, no letters, no watermark"


def p_icono(objeto_en, estilo, extra=""):
    return f"{objeto_en}, single game icon, {ESTILOS_ARTE.get(estilo, ESTILOS_ARTE['cartoon'])}, {extra} {FONDO}, high quality"


def p_gui(elemento_en, tema_en, estilo):
    return (f"{elemento_en}, game user interface asset, {tema_en} theme, {ESTILOS_ARTE.get(estilo, ESTILOS_ARTE['cartoon'])}, "
            f"front orthographic view, flat, symmetrical, empty center, {FONDO}")


def p_miniatura(titulo_en, tema_en, estilo):
    return (f"Roblox game thumbnail key art for a game about {tema_en}, blocky roblox avatar characters in a dynamic pose, "
            f"{ESTILOS_ARTE.get(estilo, ESTILOS_ARTE['cartoon'])}, vibrant saturated colors, cinematic lighting, depth of field, "
            f"action scene, empty space in the center for a title, no text, no letters, no logo")


def p_textura(material_en, tema_en):
    return (f"seamless tileable texture of {material_en}, {tema_en} game environment, top-down orthographic view, stylized hand-painted "
            f"game texture, even flat lighting, no shadows, no objects, fills the whole frame")


def p_skybox(tema_en, mood_en):
    return (f"360 degree equirectangular panorama of the sky, {tema_en}, {mood_en}, game skybox, horizon in the middle, "
            f"no ground objects, seamless left and right edges, high detail")


def p_objeto3d(objeto_en, tema_en, estilo):
    return (f"{objeto_en}, single 3d game asset, {ESTILOS_ARTE.get(estilo, ESTILOS_ARTE['low_poly'])}, {tema_en}, full object visible, "
            f"three-quarter view, soft even lighting, {FONDO}")


def p_personaje(desc_en, estilo):
    return (f"full body {desc_en}, stylized roblox avatar game character, standing in T-pose, arms straight out, front view, "
            f"{ESTILOS_ARTE.get(estilo, ESTILOS_ARTE['cartoon'])}, symmetrical, {FONDO}")


def p_sfx(desc_en):
    return f"{desc_en}, high quality video game sound effect, clean recording, no music, no voice"


def p_musica(desc_en, genero, bpm=None):
    return f"{genero}, {desc_en}, video game soundtrack, loopable, instrumental, high quality" + (f", {bpm} bpm" if bpm else "")
