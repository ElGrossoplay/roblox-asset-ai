"""Herramientas del estudio (Chat, Iconos, Miniaturas, Codigo, Sonido, GUI, 3D, Mundo).

Cada herramienta crea una carpeta en output/ con manifest.json:
  {"tipo", "tema", "creado", "preview", "imagenes", "audios", "modelos", "scripts", "asset_ids", ...}
"""
import json
import re
import time
from pathlib import Path

from .. import config, director, pipeline, presets
from ..generators import audio_offline, mesh_offline
from ..paths import OUTPUT_DIR
from ..roblox import opencloud
from . import gui_kit, iconos, miniaturas, scripts_lib
from .util import paleta_desde_base64

# palabras -> icono
SINONIMOS_ICONOS = {
    "moneda": ["moneda", "coin", "dinero", "oro", "gold", "cash"], "gema": ["gema", "diamante", "gem", "diamond", "cristal"],
    "corazon": ["corazon", "corazón", "vida", "heart", "health"], "estrella": ["estrella", "star", "favorito"],
    "rayo": ["rayo", "energia", "energía", "lightning", "bolt", "velocidad"], "espada": ["espada", "sword", "arma", "ataque"],
    "escudo": ["escudo", "shield", "defensa"], "pocion": ["pocion", "poción", "potion", "elixir"],
    "llave": ["llave", "key"], "cofre": ["cofre", "chest", "tesoro", "caja", "recompensa"],
    "trofeo": ["trofeo", "trophy", "premio", "ganador", "copa"], "engranaje": ["engranaje", "ajustes", "settings", "config", "gear"],
    "candado": ["candado", "bloqueado", "lock"], "carrito": ["carrito", "tienda", "shop", "comprar", "cart"],
    "cerrar": ["cerrar", "close", "salir", "x"], "mas": ["mas", "más", "plus", "agregar"],
    "calavera": ["calavera", "craneo", "skull", "muerte", "terror"], "reloj": ["reloj", "tiempo", "timer", "clock"],
    "mochila": ["mochila", "inventario", "backpack", "bag"], "fuego": ["fuego", "fire", "llama", "lava"],
}
COLORES_NOMBRE = {"rojo": "#ff4d6d", "azul": "#4d8dff", "verde": "#3ddc84", "amarillo": "#ffd23f", "morado": "#b45cff",
                  "violeta": "#b45cff", "naranja": "#ff8a3d", "rosa": "#ff7ac8", "celeste": "#5ec8ff", "dorado": "#ffc93c",
                  "blanco": "#f2f2f2", "negro": "#2a2a2e", "gris": "#a7b1c2", "cyan": "#38e1ff"}
SINONIMOS_SFX = {
    "moneda": ["moneda", "coin", "recoger"], "gema": ["gema", "diamante", "gem"], "compra": ["compra", "comprar", "caja registradora", "purchase", "venta"],
    "salto": ["salto", "saltar", "jump"], "aterrizaje": ["aterrizaje", "aterrizar", "caida", "caída", "land"],
    "click": ["click", "clic", "boton", "botón"], "hover": ["hover", "pasar el mouse"], "confirmar": ["confirmar", "aceptar", "ok", "seleccionar"],
    "error": ["error", "incorrecto", "denegado", "fallo"], "notificacion": ["notificacion", "notificación", "aviso", "alerta", "mensaje"],
    "abrir_menu": ["abrir menu", "abrir menú", "menu", "menú", "whoosh"], "cerrar_menu": ["cerrar menu", "cerrar menú", "cerrar"],
    "powerup": ["powerup", "power up", "potenciador", "mejora", "boost"], "subir_nivel": ["subir de nivel", "level up", "nivel", "rango"],
    "victoria": ["victoria", "ganar", "win", "ganaste"], "derrota": ["derrota", "perder", "perdiste", "game over", "lose"],
    "explosion": ["explosion", "explosión", "boom", "bomba"], "laser": ["laser", "láser", "blaster"], "disparo": ["disparo", "bala", "gun", "tiro", "pistola"],
    "recarga": ["recarga", "recargar", "reload"], "golpe": ["golpe", "puño", "punch", "impacto", "hit"], "golpe_sordo": ["golpe sordo", "thud"],
    "espada": ["espada", "sword", "corte", "slash"], "hechizo": ["hechizo", "magia", "spell", "mago"], "curar": ["curar", "curacion", "curación", "heal", "vida"],
    "dano": ["daño", "dano", "herido", "hurt", "dolor"], "teletransporte": ["teletransporte", "teleport"], "portal": ["portal", "vortice", "vórtice"],
    "cofre_abrir": ["cofre", "abrir cofre", "tesoro", "loot"], "puerta_crujido": ["puerta", "crujido", "door"], "latido": ["latido", "heartbeat"],
    "alarma": ["alarma", "sirena", "alarm"], "campana": ["campana", "bell"], "hielo_romper": ["hielo", "romper", "vidrio", "cristal roto"],
    "glitch": ["glitch", "digital", "falla"], "chapuzon": ["chapuzon", "chapuzón", "splash", "caer al agua"], "grito_lejano": ["grito", "scream"],
    "trueno": ["trueno", "tormenta", "thunder", "rayo"],
    "viento": ["viento", "wind"], "lluvia": ["lluvia", "rain", "llover"], "fuego": ["fuego", "fogata", "fire", "llamas"],
    "olas": ["olas", "mar", "oceano", "océano", "playa"], "rio": ["rio", "río", "arroyo", "agua corriendo"], "pajaros": ["pajaros", "pájaros", "aves", "bosque"],
    "noche": ["noche", "grillos", "night"], "cueva": ["cueva", "cave", "goteo", "mazmorra"],
    "pasos_madera": ["pasos madera", "pasos en madera"], "pasos_piedra": ["pasos piedra", "pasos en piedra"], "pasos_pasto": ["pasos pasto", "pasos en pasto"],
    "pasos_nieve": ["pasos nieve", "pasos en nieve"], "pasos_metal": ["pasos metal", "pasos en metal"], "pasos_arena": ["pasos arena", "pasos en arena"],
    "pasos_tierra": ["pasos", "caminar", "footstep"],
}


def _nueva_carpeta(tipo: str, tema: str) -> Path:
    c = OUTPUT_DIR / f"{tipo}_{director.slug(tema)[:30]}_{time.strftime('%Y%m%d_%H%M%S')}"
    c.mkdir(parents=True)
    return c


def _manifest(carpeta: Path, tipo: str, tema: str, **extra) -> dict:
    m = {"tipo": tipo, "tema": tema, "nombre": carpeta.name, "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
         "preview": None, "imagenes": [], "audios": [], "modelos": [], "scripts": [], "asset_ids": {}, **extra}
    return m


def _guardar(carpeta: Path, m: dict) -> Path:
    (carpeta / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return carpeta


def _rel(carpeta, ruta):
    return str(Path(ruta).relative_to(carpeta)).replace("\\", "/")


def _paleta(prompt: str, op: dict) -> list:
    if op.get("referencia"):
        return paleta_desde_base64(op["referencia"])
    if op.get("paleta"):
        return op["paleta"]
    return presets.PRESETS[presets.elegir(prompt)]["paleta"]


def _detectar(prompt: str, tabla: dict) -> list:
    t = " " + re.sub(r"[^\wáéíóúñ ]", " ", prompt.lower()) + " "
    return [k for k, ws in tabla.items() if any(f" {w}" in t for w in ws)]


def imagen_ia(prompt: str, destino: Path, ancho=1024, alto=1024) -> Path:
    c = config.get()["imagen"]
    from ..generators import cloud
    if c["backend"] == "pollinations":
        return cloud.imagen_pollinations(prompt, destino, ancho, alto)
    if c["backend"] == "cloud":
        return cloud.imagen(c["cloud_model"], prompt, destino, "16:9" if ancho > alto else "1:1")
    if c["backend"] == "local":
        from ..generators import local
        return local.imagen(c["local_model"], prompt, destino, c.get("tamano", 1024))
    raise RuntimeError("offline")


# ------------------------------------------------------------- herramientas
def iconos_tool(prompt: str, op: dict, log=print) -> Path:
    nombres = op.get("iconos") or _detectar(prompt, SINONIMOS_ICONOS) or ["moneda", "gema", "corazon", "estrella", "cofre", "trofeo"]
    estilo = op.get("estilo_icono") or next((e for e in ("neon", "pixel", "plano") if e in prompt.lower()), "cartoon")
    color = op.get("color") or next((v for k, v in COLORES_NOMBRE.items() if k in prompt.lower()), None)
    tam = int(op.get("tam", 512))
    carpeta = _nueva_carpeta("iconos", prompt)
    log(f"Iconos ({estilo}): {', '.join(nombres)}")
    rutas = iconos.generar(nombres, carpeta / "iconos", estilo, {n: color for n in nombres} if color else None, tam)
    from PIL import Image
    hoja = Image.new("RGBA", (256 * min(4, len(rutas)), 256 * ((len(rutas) + 3) // 4)), (0, 0, 0, 0))
    for i, r in enumerate(rutas.values()):
        hoja.alpha_composite(Image.open(r).resize((256, 256)), ((i % 4) * 256, (i // 4) * 256))
    hoja.save(carpeta / "hoja.png")
    m = _manifest(carpeta, "iconos", prompt, preview="hoja.png", imagenes=[_rel(carpeta, r) for r in rutas.values()],
                  estilo=estilo)
    return _guardar(carpeta, m)


def gui_tool(prompt: str, op: dict, log=print) -> Path:
    preset = presets.elegir(prompt)
    estilo = op.get("estilo_gui") or next((e for e in gui_kit.ESTILOS if e in prompt.lower()), None) \
        or gui_kit.ESTILO_POR_PRESET.get(preset, "cartoon")
    paleta = _paleta(prompt, op)
    ajustes = {k: op[k] for k in ("radio", "borde", "primario", "acento", "panel", "fuente") if op.get(k) not in (None, "")}
    if "radio" in ajustes:
        ajustes["radio"] = float(ajustes["radio"])
    if "borde" in ajustes:
        ajustes["borde"] = float(ajustes["borde"])
    textos = op.get("textos") or {}
    carpeta = _nueva_carpeta("gui", prompt)
    log(f"GUI kit estilo '{estilo}' con paleta {', '.join(paleta[:5])}")
    spec = gui_kit.construir(paleta, estilo, textos, ajustes)
    (carpeta / "gui.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    log("Renderizando vista previa y elementos...")
    gui_kit.renderizar(spec, carpeta / "vista_previa.png")
    elementos = gui_kit.exportar_elementos(spec, carpeta / "elementos")
    usados = gui_kit.iconos_usados(spec)
    rutas_ic = iconos.generar(usados, carpeta / "iconos", gui_kit.ESTILOS[estilo]["icono"])
    (carpeta / "CrearGUI.lua").write_text(gui_kit.script_luau(spec), encoding="utf-8")
    m = _manifest(carpeta, "gui", prompt, preview="vista_previa.png", estilo=estilo, paleta=paleta,
                  imagenes=[_rel(carpeta, r) for r in elementos], iconos=[_rel(carpeta, r) for r in rutas_ic.values()],
                  scripts=["CrearGUI.lua"], gui="gui.json")
    return _guardar(carpeta, m)


def miniatura_tool(prompt: str, op: dict, log=print) -> Path:
    titulo = op.get("titulo") or re.sub(r"^(haz|crea|genera|hazme|una?|miniatura|thumbnail|portada|de|para|mi|juego)\s+", "", prompt.strip(), flags=re.I)
    for _ in range(4):
        titulo = re.sub(r"^(haz|crea|genera|hazme|una?|miniatura|thumbnail|portada|de|para|mi|juego|el|la)\s+", "", titulo, flags=re.I)
    titulo = titulo[:40] or "Mi Juego"
    paleta = _paleta(prompt, op)
    preset = presets.elegir(prompt)
    lista = op.get("iconos") or _detectar(prompt, SINONIMOS_ICONOS) or {
        "terror": ["calavera", "llave", "reloj"], "espacio": ["rayo", "gema", "estrella"], "fantasia": ["espada", "escudo", "cofre"],
        "cyberpunk": ["rayo", "gema", "moneda"], "invierno": ["estrella", "cofre", "gema"], "desierto": ["moneda", "cofre", "llave"],
    }.get(preset, ["moneda", "estrella", "trofeo"])
    carpeta = _nueva_carpeta("miniatura", titulo)
    fondo_ruta = None
    if op.get("fondo_ia", True) and config.get()["imagen"]["backend"] != "offline":
        try:
            log("Generando fondo con IA...")
            fondo_ruta = imagen_ia(f"{prompt}, roblox game thumbnail background, vibrant, 3d render, no text",
                                   carpeta / "fondo_ia.png", 1344, 768)
        except Exception as e:  # noqa: BLE001
            log(f"Fondo IA no disponible ({e}); uso fondo procedural.")
    estilo_icono = gui_kit.ESTILOS[gui_kit.ESTILO_POR_PRESET.get(preset, "cartoon")]["icono"]
    log(f"Miniatura: '{titulo}'")
    sal = miniaturas.generar(titulo.replace("\\n", "\n"), carpeta, paleta, op.get("subtitulo", ""), lista,
                             op.get("fondo", "rayos"), fondo_ruta, estilo_icono, op.get("fuente"))
    m = _manifest(carpeta, "miniatura", prompt, preview="miniatura.png", imagenes=[_rel(carpeta, r) for r in sal.values()])
    return _guardar(carpeta, m)


def sonido_tool(prompt: str, op: dict, log=print) -> Path:
    from ..generators import musica_pro, sfx_pro
    t = prompt.lower()
    es_musica = op.get("tipo") == "musica" or (op.get("tipo") != "sfx" and any(
        w in t for w in ("musica", "música", "cancion", "canción", "soundtrack", "melodia", "melodía", "beat", "tema musical", "ost")))
    carpeta = _nueva_carpeta("sonido", prompt)
    audios, extra = [], {}
    cfg = config.get()
    if es_musica:
        estilo = director.crear_style_pack(prompt, log)
        genero = op.get("genero") or musica_pro.detectar_genero(prompt, "") or musica_pro.detectar_genero(estilo["musica"]["prompt"])
        mcfg = {**estilo["musica"], "prompt": f"{prompt} {estilo['musica']['prompt']}", "genero": genero,
                "bpm_forzado": int(op["bpm"]) if op.get("bpm") else None}
        dur = float(op.get("duracion") or cfg["musica"].get("duracion_seg", 40))
        destino = carpeta / "musica.wav"
        stems = carpeta / "stems" if str(op.get("stems", "")).lower() in ("1", "true", "si", "sí", "on") else None
        log(f"Componiendo musica: genero {genero}")

        def ia():
            c = cfg["musica"]
            if c["backend"] == "cloud":
                from ..generators import cloud
                return cloud.audio(c["cloud_model"], f"{prompt}, {genero}, {estilo['musica']['prompt']}", destino, dur)
            from ..generators import local
            return local.musica(c["local_model"], f"{prompt}, {genero}, {estilo['musica']['prompt']}", destino, dur)
        ruta, usado = pipeline._con_respaldo("Musica", cfg["musica"]["backend"], ia,
                                             lambda: audio_offline.generar_musica(mcfg, destino, dur, int(op.get("semilla", 0)), genero, stems), log)
        audios.append(ruta)
        if mcfg.get("_info"):
            extra["musica_info"] = mcfg["_info"]
            log("{genero} · {bpm} BPM · {escala} · {compases} compases ({segundos}s, loop perfecto)".format(**mcfg["_info"]))
        if stems and stems.exists():
            audios += sorted(stems.glob("*.wav"))
    else:
        nombres = op.get("sfx") or _detectar(prompt, SINONIMOS_SFX) or ["click", "confirmar", "moneda", "salto", "powerup", "error"]
        # "pasos" generico solo si no se pidio una superficie
        if any(n.startswith("pasos_") and n != "pasos_tierra" for n in nombres):
            nombres = [n for n in nombres if n != "pasos_tierra"]
        mods = sfx_pro.modificadores(prompt)
        variaciones = int(op.get("variaciones") or (3 if len(nombres) <= 2 else 1))
        for n in nombres[:12]:
            for v in range(variaciones):
                sufijo = f"_{v + 1}" if variaciones > 1 else ""
                destino = carpeta / f"{n}{sufijo}.wav"
                if v == 0:
                    log(f"Efecto: {n}" + (f" x{variaciones}" if variaciones > 1 else ""))

                def ia(n=n, destino=destino):
                    c = cfg["sfx"]
                    if c["backend"] == "cloud":
                        from ..generators import cloud
                        return cloud.audio(c["cloud_model"], f"{prompt}, {n}", destino, c.get("duracion_seg", 2))
                    from ..generators import local
                    return local.sfx(c["local_model"], f"{prompt}, {n}", destino, c.get("duracion_seg", 2))
                ruta, _ = pipeline._con_respaldo("SFX", cfg["sfx"]["backend"], ia,
                                                 lambda n=n, destino=destino, v=v: audio_offline.generar_sfx(n, destino, int(op.get("semilla", 0)) * 100 + v + 1, mods), log)
                audios.append(ruta)
        extra["modificadores"] = {k: v for k, v in mods.items() if v not in (1.0, False)}
    m = _manifest(carpeta, "sonido", prompt, audios=[_rel(carpeta, r) for r in audios], **extra)
    return _guardar(carpeta, m)


def codigo_tool(prompt: str, op: dict, log=print) -> Path:
    res = scripts_lib.generar(prompt, log)
    carpeta = _nueva_carpeta("codigo", prompt)
    nombre = director.slug(res["titulo"])[:30] or "script"
    (carpeta / f"{nombre}.lua").write_text(res["codigo"], encoding="utf-8")
    m = _manifest(carpeta, "codigo", prompt, scripts=[f"{nombre}.lua"], fuente=res["fuente"],
                  relacionados=[scripts_lib.PLANTILLAS[r]["titulo"] for r in res.get("relacionados", [])],
                  destino=res.get("destino"), tipo_script=res.get("tipo"))
    log(f"Script: {res['titulo']} ({res['fuente']})")
    return _guardar(carpeta, m)


def modelo3d_tool(prompt: str, op: dict, log=print) -> Path:
    from PIL import Image
    from ..generators import mesh_pro
    pedidos = mesh_pro.interpretar(prompt)
    if any(w in prompt.lower() for w in ("bosque", "forest")) and not pedidos:
        pedidos = [("arbol", None, 2), ("pino", None, 1), ("arbusto", None, 1), ("roca", None, 1), ("hongo", None, 1)]
    if not pedidos:
        tema = presets.elegir(prompt)
        pedidos = [(n, None, 1) for n in presets.PRESETS[tema]["props"]]
        pedidos = [(("arbol_seco" if n == "arbol_seco" else n), c, k) for n, c, k in pedidos if n in mesh_pro.PROPS] or [("arbol", None, 1)]
    variaciones = int(op.get("variaciones") or 0)
    if not variaciones:
        variaciones = 3 if len(pedidos) == 1 and pedidos[0][2] == 1 else 1
    color_op = mesh_pro.rgb(op["color"]) if op.get("color") else None
    exportar_obj = str(op.get("obj", "")).lower() in ("1", "true", "si", "sí", "on")
    carpeta = _nueva_carpeta("modelo3d", prompt)
    rutas, previews = [], []
    for nombre, color, cant in pedidos[:10]:
        total = max(cant, variaciones)
        log(f"Modelo 3D: {nombre}" + (f" x{total}" if total > 1 else ""))
        for k in range(total):
            destino = carpeta / f"{nombre}{'_' + str(k + 1) if total > 1 else ''}.glb"

            def ia(nombre=nombre, destino=destino):
                if config.get()["malla3d"]["backend"] != "cloud":
                    raise RuntimeError("offline")
                from ..generators import cloud
                ref = destino.with_suffix(".ref.png")
                imagen_ia(f"low poly stylized {nombre}, {prompt}, game asset, white background", ref)
                return cloud.malla_desde_imagen(config.get()["malla3d"]["cloud_model"], ref, destino)

            def offline(nombre=nombre, destino=destino, k=k, color=color):
                m = mesh_pro.construir(nombre, int(op.get("semilla", 0)) * 50 + k + 1, color if color is not None else color_op,
                                       float(op.get("escala") or 1))
                mesh_pro.guardar_glb(m, destino, k)
                mesh_pro.render(m, destino.with_suffix(".png"), 384)
                mesh_pro.pulir(destino, nombre, log)
                if exportar_obj:
                    mesh_pro.guardar_obj(m, destino.with_suffix(".obj"))
                return destino
            ruta, _ = pipeline._con_respaldo("3D", config.get()["malla3d"]["backend"], ia, offline, log)
            rutas.append(ruta)
            if ruta.with_suffix(".png").exists():
                previews.append(ruta.with_suffix(".png"))
    if previews:
        cols = min(4, len(previews))
        hoja = Image.new("RGB", (384 * cols, 384 * ((len(previews) + cols - 1) // cols)), (18, 24, 38))
        for i, pth in enumerate(previews):
            hoja.paste(Image.open(pth), ((i % cols) * 384, (i // cols) * 384))
        hoja.save(carpeta / "hoja.png")
    m = _manifest(carpeta, "modelo3d", prompt, preview="hoja.png" if previews else None,
                  modelos=[_rel(carpeta, r) for r in rutas], imagenes=[_rel(carpeta, r) for r in previews])
    return _guardar(carpeta, m)


def mundo_tool(prompt: str, op: dict, log=print) -> Path:
    return pipeline.generar_pack(prompt, op.get("opciones"), log)


HERRAMIENTAS = {"iconos": iconos_tool, "gui": gui_tool, "miniatura": miniatura_tool, "sonido": sonido_tool,
                "codigo": codigo_tool, "modelo3d": modelo3d_tool, "mundo": mundo_tool}

INTENCIONES = [
    ("codigo", ["script", "codigo", "código", "luau", "sistema de", "programa", "datastore", "leaderstats", "remote"]),
    ("miniatura", ["miniatura", "thumbnail", "portada", "banner", "gfx"]),
    ("gui", ["gui", "interfaz", "hud", "menu", "menú", "ui ", "botones", "pantalla"]),
    ("iconos", ["icono", "ícono", "iconos", "íconos", "icon"]),
    ("sonido", ["sonido", "efecto de sonido", "sfx", "musica", "música", "audio", "cancion", "canción"]),
    ("modelo3d", ["modelo 3d", "3d", "prop", "malla", "mesh", "personaje", "npc", "avatar"]),
]


def detectar_intencion(prompt: str) -> str:
    t = prompt.lower() + " "
    for tipo, palabras in INTENCIONES:
        if any(p in t for p in palabras):
            return tipo
    return "juego"


def chat_tool(prompt: str, op: dict, log=print) -> Path:
    """Agente: entiende el pedido y usa una o varias herramientas.
    Si no pide algo concreto ("haz un tycoon de pizza"), arma el juego completo:
    mundo (luces, cielo, texturas, sonidos, musica, 3D) + GUI + miniatura."""
    intencion = detectar_intencion(prompt)
    if intencion != "juego":
        log(f"Agente: uso la herramienta '{intencion}'.")
        return HERRAMIENTAS[intencion](prompt, op, log)
    log("Agente: armo el juego completo (mundo + GUI + miniatura).")
    mundo = mundo_tool(prompt, op, log)
    gui = gui_tool(prompt, op, log)
    mini = miniatura_tool(prompt, op, log)
    carpeta = _nueva_carpeta("juego", prompt)
    m = _manifest(carpeta, "juego", prompt, preview=f"../{mini.name}/miniatura.png",
                  partes=[mundo.name, gui.name, mini.name])
    log("Listo: revisa las 3 tarjetas en la galeria.")
    return _guardar(carpeta, m)


# ------------------------------------------------------------- subir a Roblox
def subir(carpeta: Path, log=print) -> Path:
    m = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    if "tipo" not in m:  # pack de mundo (formato antiguo)
        pipeline.subir_pack(carpeta, log)
        return carpeta
    if m["tipo"] == "juego":
        for parte in m.get("partes", []):
            if (OUTPUT_DIR / parte).is_dir():
                subir(OUTPUT_DIR / parte, log)
        return carpeta
    archivos = m.get("iconos", []) + m.get("imagenes", []) + m.get("audios", []) + m.get("modelos", [])
    for rel in archivos:
        if rel in m["asset_ids"]:
            continue
        try:
            log(f"Subiendo {rel}...")
            m["asset_ids"][rel] = opencloud.subir(carpeta / rel, f"{director.slug(m['tema'])[:30]}_{Path(rel).stem}")
        except Exception as e:  # noqa: BLE001
            log(f"  Error con {rel}: {e}")
            if "ROBLOX_API_KEY" in str(e):
                break
    if m["tipo"] == "gui":
        spec = json.loads((carpeta / "gui.json").read_text(encoding="utf-8"))
        ids = {Path(k).stem: v for k, v in m["asset_ids"].items() if k.startswith("iconos/")}
        ids_arte = {Path(k).stem: v for k, v in m["asset_ids"].items() if k.startswith("arte/")}
        (carpeta / "CrearGUI.lua").write_text(gui_kit.script_luau(spec, ids, ids_arte), encoding="utf-8")
        log("CrearGUI.lua actualizado con los IDs de los iconos.")
    _guardar(carpeta, m)
    return carpeta
