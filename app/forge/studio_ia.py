"""Herramientas con IA generativa REAL (primero IA; si no hay, el generador procedural).

Se registran encima de las herramientas de studio.py (mismos nombres), asi la interfaz,
el plugin y el MCP usan automaticamente la version con IA.
"""
import base64
import json
import re
from pathlib import Path

from PIL import Image

from .. import config, director, presets
from ..generators import audio_offline, mesh_pro
from ..ia import creador, motor, prompts
from ..ia.agente import planificar
from ..ia.motor import SinIA
from . import gui_kit, iconos, miniaturas, scripts_lib, studio
from .studio import _guardar, _manifest, _nueva_carpeta, _paleta, _rel

ESTILO_ARTE_GUI = {"cartoon": "cartoon", "scifi": "neon", "fantasia": "fantasia", "minimal": "plano", "terror": "terror", "pixel": "pixel"}


def _slug(t):
    return director.slug(t)[:28] or "asset"


def _hoja(rutas, destino, celda=256, fondo=(0, 0, 0, 0)):
    if not rutas:
        return None
    cols = min(4, len(rutas))
    hoja = Image.new("RGBA", (celda * cols, celda * ((len(rutas) + cols - 1) // cols)), fondo)
    for i, r in enumerate(rutas):
        hoja.alpha_composite(Image.open(r).convert("RGBA").resize((celda, celda)), ((i % cols) * celda, (i // cols) * celda))
    hoja.save(destino)
    return destino


def _imagen_usuario(op, carpeta):
    datos = op.get("imagen_ref") or op.get("referencia_3d")
    if not datos:
        return None
    if "," in datos:
        datos = datos.split(",", 1)[1]
    ruta = carpeta / "imagen_usuario.png"
    ruta.write_bytes(base64.b64decode(datos))
    return ruta


# ============================================================= ICONOS
def iconos_ia(prompt, op, log=print):
    if not motor.disponible():
        return studio.iconos_tool(prompt, op, log)
    items = op.get("iconos") or prompts.elementos(prompt)
    estilo = op.get("estilo_icono") or prompts.estilo_de(prompt)
    tam = int(op.get("tam") or 512)
    color = op.get("color")
    extra = f"main color {color}," if color else ""
    carpeta = _nueva_carpeta("iconos", prompt)
    log(f"Iconos IA ({estilo}), set consistente: {', '.join(items)}")
    rutas, fuente = [], "ia"
    for i, item in enumerate(items):
        destino = carpeta / "iconos" / f"{_slug(item)}.png"
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            creador.icono(item, destino, estilo, semilla=int(op.get("semilla") or 7), tam=tam, extra=extra, log=log)
            rutas.append(destino)
        except SinIA as e:
            if i == 0 and not rutas:
                log(f"IA no disponible ({str(e)[:100]}). Uso iconos procedurales.")
                return studio.iconos_tool(prompt, op, log)
            proc = studio._detectar(item, studio.SINONIMOS_ICONOS)
            if proc:
                iconos.dibujar(proc[0], estilo={"realista": "cartoon", "anime": "cartoon", "fantasia": "cartoon", "terror": "plano",
                                                "low_poly": "plano"}.get(estilo, estilo), tam=tam).save(destino)
                rutas.append(destino)
                fuente = "mixto"
    _hoja(rutas, carpeta / "hoja.png")
    m = _manifest(carpeta, "iconos", prompt, preview="hoja.png", imagenes=[_rel(carpeta, r) for r in rutas], estilo=estilo, fuente=fuente)
    return _guardar(carpeta, m)


# ============================================================= GUI
def gui_ia(prompt, op, log=print):
    carpeta_proc = studio.gui_tool(prompt, op, log)  # estructura real (ScreenGui) + respaldo vectorial
    if not motor.disponible():
        return carpeta_proc
    m = json.loads((carpeta_proc / "manifest.json").read_text(encoding="utf-8"))
    spec = json.loads((carpeta_proc / "gui.json").read_text(encoding="utf-8"))
    estilo_arte = ESTILO_ARTE_GUI.get(spec["estilo"], "cartoon")
    try:
        log(f"Arte IA para la GUI (estilo {estilo_arte})...")
        arte = creador.arte_gui(prompt, estilo_arte, carpeta_proc / "arte", m.get("paleta"), log)
    except SinIA as e:
        log(f"IA no disponible para el arte ({str(e)[:100]}); queda la GUI vectorial.")
        return carpeta_proc
    iconos_png = {}
    for nombre in gui_kit.iconos_usados(spec):
        destino = carpeta_proc / "iconos" / f"{nombre}.png"
        try:
            creador.icono(nombre, destino, estilo_arte, semilla=7, tam=512, log=log)
            iconos_png[nombre] = destino
        except SinIA:
            pass
    gui_kit.asignar_arte(spec, arte)
    (carpeta_proc / "gui.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    log("Renderizando la GUI con el arte IA...")
    gui_kit.renderizar(spec, carpeta_proc / "vista_previa.png", arte=arte, iconos_png=iconos_png)
    elementos = gui_kit.exportar_elementos(spec, carpeta_proc / "elementos", arte=arte, iconos_png=iconos_png)
    (carpeta_proc / "CrearGUI.lua").write_text(gui_kit.script_luau(spec), encoding="utf-8")
    m["imagenes"] = [_rel(carpeta_proc, r) for r in list(arte.values()) + elementos]
    m["fuente"] = "ia"
    return _guardar(carpeta_proc, m)


# ============================================================= MINIATURA / GFX
def miniatura_ia(prompt, op, log=print):
    if not motor.disponible() or op.get("fondo_ia") is False:
        return studio.miniatura_tool(prompt, op, log)
    titulo = op.get("titulo") or prompt
    for _ in range(5):
        titulo = re.sub(r"^(haz|crea|genera|hazme|una?|miniatura|thumbnail|portada|gfx|de|para|mi|juego|el|la)\s+", "", titulo.strip(), flags=re.I)
    titulo = titulo[:40] or "Mi Juego"
    estilo = op.get("estilo_icono") or prompts.estilo_de(prompt)
    carpeta = _nueva_carpeta("miniatura", titulo)
    try:
        log("Arte IA de la miniatura (escena con personajes)...")
        fondo = creador.fondo_miniatura(prompt, titulo, estilo, carpeta / "gfx.png", log)
    except SinIA as e:
        log(f"IA no disponible ({str(e)[:100]}); miniatura procedural.")
        carpeta.rmdir() if not any(carpeta.iterdir()) else None
        return studio.miniatura_tool(prompt, op, log)
    icono_png = None
    try:
        objeto = prompts.elementos(prompt)[0]
        icono_png = creador.icono(f"main object of a game about {objeto}", carpeta / "icono_objeto.png", estilo, 11, 512, log=log)
    except SinIA:
        pass
    sal = miniaturas.generar(titulo.replace("\\n", "\n"), carpeta, _paleta(prompt, op), op.get("subtitulo", ""), ["estrella"],
                             "rayos", fondo, "cartoon", op.get("fuente"), icono_png=icono_png)
    imgs = [_rel(carpeta, r) for r in sal.values()] + ["gfx.png"]
    m = _manifest(carpeta, "miniatura", prompt, preview="miniatura.png", imagenes=imgs, fuente="ia")
    return _guardar(carpeta, m)


# ============================================================= 3D
PERSONAJE = ("personaje", "character", "npc", "avatar", "guerrero", "mago", "caballero", "ninja", "robot", "zombie", "pirata",
             "princesa", "heroe", "héroe", "villano", "jefe", "boss", "chico", "chica", "humano")


def modelo3d_ia(prompt, op, log=print):
    if not motor.disponible():
        return studio.modelo3d_tool(prompt, op, log)
    carpeta = _nueva_carpeta("modelo3d", prompt)
    imagen_usr = _imagen_usuario(op, carpeta)
    items = [prompt] if imagen_usr else prompts.elementos(prompt, 6)
    estilo = op.get("estilo_icono") or prompts.estilo_de(prompt, "low_poly")
    variaciones = int(op.get("variaciones") or 1)
    modo = motor.cfg().get("modelo3d", {}).get("modo", "imagen")
    max_tris = int(motor.cfg().get("modelo3d", {}).get("max_triangulos", 18000))
    rutas, previews, infos = [], [], {}
    for item in items:
        cantidad = re.match(r"^(\d+)\s+", item)
        n = max(variaciones, int(cantidad.group(1)) if cantidad else 1)
        item_limpio = re.sub(r"^\d+\s+", "", item)
        es_personaje = any(w in item_limpio.lower() for w in PERSONAJE)
        for k in range(min(n, 4)):
            destino = carpeta / f"{_slug(item_limpio)}{'_' + str(k + 1) if n > 1 else ''}.glb"
            log(f"Modelo 3D IA: {item_limpio}" + (" (personaje)" if es_personaje else "") + (f" {k + 1}/{n}" if n > 1 else ""))
            try:
                info = creador.modelo(item_limpio, prompt, estilo, destino, es_personaje,
                                      float(op["escala"]) * 6 if op.get("escala") else None, semilla=3 + k * 17,
                                      modo=modo, max_tris=max_tris, imagen_usuario=imagen_usr, log=log)
                infos[destino.name] = info
            except SinIA as e:
                proc = mesh_pro.interpretar(item_limpio)
                nombre = proc[0][0] if proc else ("personaje" if es_personaje else None)
                if not nombre:
                    log(f"  No se pudo crear '{item_limpio}' con IA ({str(e)[:90]}) y no hay modelo procedural parecido.")
                    continue
                log(f"  IA no disponible; uso el modelo procedural '{nombre}'.")
                mm = mesh_pro.construir(nombre, k + 1, proc[0][1] if proc else None)
                mesh_pro.guardar_glb(mm, destino, k)
                mesh_pro.render(mm, destino.with_suffix(".png"), 384)
                mesh_pro.pulir(destino, nombre, log)
            rutas.append(destino)
            if destino.with_suffix(".png").exists():
                previews.append(destino.with_suffix(".png"))
    if previews:
        hoja = Image.new("RGB", (384 * min(4, len(previews)), 384 * ((len(previews) + 3) // 4)), (18, 24, 38))
        for i, pth in enumerate(previews):
            hoja.paste(Image.open(pth).convert("RGB"), ((i % 4) * 384, (i // 4) * 384))
        hoja.save(carpeta / "hoja.png")
    refs = sorted(carpeta.glob("*_referencia.png"))
    m = _manifest(carpeta, "modelo3d", prompt, preview="hoja.png" if previews else None, modelos=[_rel(carpeta, r) for r in rutas],
                  imagenes=[_rel(carpeta, r) for r in previews + refs], info3d=infos, fuente="ia" if infos else "procedural")
    return _guardar(carpeta, m)


# ============================================================= SONIDO / MUSICA
AMBIENTE = ("lluvia", "viento", "fuego", "olas", "mar", "rio", "río", "bosque", "noche", "cueva", "ambiente", "ambient", "loop", "tormenta")


def sonido_ia(prompt, op, log=print):
    t = prompt.lower()
    es_musica = op.get("tipo") == "musica" or (op.get("tipo") != "sfx" and any(
        w in t for w in ("musica", "música", "cancion", "canción", "soundtrack", "melodia", "melodía", "beat", "ost", "tema musical")))
    if not motor.disponible():
        return studio.sonido_tool(prompt, op, log)
    if es_musica:
        from ..generators import musica_pro
        genero = op.get("genero") or musica_pro.detectar_genero(prompt, "") or musica_pro.detectar_genero(
            presets.PRESETS[presets.elegir(prompt)]["musica"]["prompt"])
        dur = float(op.get("duracion") or 45)
        carpeta = _nueva_carpeta("sonido", prompt)
        try:
            log(f"Musica IA ({genero}, {dur:.0f}s)...")
            ruta = creador.musica(prompt, genero, carpeta / "musica.wav", dur, op.get("bpm"), op.get("letra"), log)
            m = _manifest(carpeta, "sonido", prompt, audios=[_rel(carpeta, ruta)], fuente="ia",
                          musica_info={"genero": genero, "bpm": op.get("bpm") or "auto", "escala": "IA", "compases": "-", "segundos": dur})
            return _guardar(carpeta, m)
        except SinIA as e:
            log(f"IA de musica no disponible ({str(e)[:100]}); uso el compositor procedural.")
            carpeta.rmdir() if not any(carpeta.iterdir()) else None
            return studio.sonido_tool(prompt, {**op, "tipo": "musica", "genero": genero}, log)
    items = op.get("sfx_texto") or prompts.elementos(prompt)
    variaciones = int(op.get("variaciones") or (2 if len(items) <= 3 else 1))
    carpeta = _nueva_carpeta("sonido", prompt)
    audios, fuente = [], "ia"
    from ..generators import sfx_pro
    mods = sfx_pro.modificadores(prompt)
    for i, item in enumerate(items[:10]):
        dur = 9.0 if any(w in item.lower() for w in AMBIENTE) else float(op.get("duracion_sfx") or 2.5)
        for v in range(variaciones):
            destino = carpeta / f"{_slug(item)}{'_' + str(v + 1) if variaciones > 1 else ''}.wav"
            try:
                if v == 0:
                    log(f"Efecto IA: {item}")
                audios.append(creador.sfx(item, destino, dur, log))
            except SinIA as e:
                if i == 0 and not audios:
                    log(f"IA de sonido no disponible ({str(e)[:100]}); uso efectos procedurales.")
                    carpeta.rmdir() if not any(carpeta.iterdir()) else None
                    return studio.sonido_tool(prompt, op, log)
                proc = studio._detectar(item, studio.SINONIMOS_SFX)
                if proc:
                    audios.append(audio_offline.generar_sfx(proc[0], destino.with_suffix(".wav"), v + 1, mods))
                    fuente = "mixto"
    m = _manifest(carpeta, "sonido", prompt, audios=[_rel(carpeta, r) for r in audios], fuente=fuente)
    return _guardar(carpeta, m)


def musica_ia(prompt, op, log=print):
    return sonido_ia(prompt, {**op, "tipo": "musica"}, log)


# ============================================================= CODIGO
def codigo_ia(prompt, op, log=print):
    if not motor.disponible():
        return studio.codigo_tool(prompt, op, log)
    coincidencias = scripts_lib.buscar(prompt)
    base = scripts_lib.PLANTILLAS[coincidencias[0]]["codigo"] if coincidencias else None
    usuario = prompt if not base else f"{prompt}\n\nPuedes partir de esta plantilla y mejorarla:\n```lua\n{base}\n```"
    try:
        log("Escribiendo el script con IA...")
        texto = motor.texto(scripts_lib.SYSTEM, usuario, log)
        bloques = re.findall(r"```(?:lua|luau)?\s*\n(.*?)```", texto, re.S)
        codigo = ("\n\n".join(bloques) if bloques else texto).strip() + "\n"
        if len(codigo) < 40:
            raise SinIA("respuesta vacia")
    except SinIA as e:
        log(f"LLM no disponible ({str(e)[:100]}); uso la biblioteca de plantillas.")
        return studio.codigo_tool(prompt, op, log)
    carpeta = _nueva_carpeta("codigo", prompt)
    nombre = _slug(prompt)
    (carpeta / f"{nombre}.lua").write_text(codigo, encoding="utf-8")
    tipo = "LocalScript" if re.search(r"LocalScript|LocalPlayer|UserInputService", codigo) else "Script"
    m = _manifest(carpeta, "codigo", prompt, scripts=[f"{nombre}.lua"], fuente="ia", tipo_script=tipo,
                  destino="StarterPlayer > StarterPlayerScripts" if tipo == "LocalScript" else "ServerScriptService",
                  relacionados=[scripts_lib.PLANTILLAS[r]["titulo"] for r in coincidencias[:3]])
    return _guardar(carpeta, m)


# ============================================================= AGENTE
def chat_ia(prompt, op, log=print):
    plan = planificar(prompt, log)
    if not plan:
        return studio.chat_tool(prompt, op, log)
    if plan.get("respuesta"):
        log(f"Agente: {plan['respuesta']}")
    if len(plan["pasos"]) == 1:
        p = plan["pasos"][0]
        log(f"Agente -> {p['herramienta']}: {p['prompt']}")
        return HERRAMIENTAS[p["herramienta"]](p["prompt"], {**op, **(p.get("opciones") or {})}, log)
    partes = []
    for i, p in enumerate(plan["pasos"], 1):
        log(f"[{i}/{len(plan['pasos'])}] {p['herramienta']}: {p['prompt']}")
        try:
            partes.append(HERRAMIENTAS[p["herramienta"]](p["prompt"], {**(p.get("opciones") or {})}, log).name)
        except Exception as e:  # noqa: BLE001
            log(f"  fallo el paso ({str(e)[:120]})")
    carpeta = _nueva_carpeta("juego", prompt)
    mini = next((pt for pt in partes if pt.startswith("miniatura_")), None)
    m = _manifest(carpeta, "juego", prompt, preview=f"../{mini}/miniatura.png" if mini else None, partes=partes,
                  plan=plan, fuente="ia")
    log("Listo. Todo quedo agrupado en 'Juego completo'.")
    return _guardar(carpeta, m)


HERRAMIENTAS = {**studio.HERRAMIENTAS, "iconos": iconos_ia, "gui": gui_ia, "miniatura": miniatura_ia, "modelo3d": modelo3d_ia,
                "sonido": sonido_ia, "musica": musica_ia, "codigo": codigo_ia}
