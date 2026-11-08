"""Creacion de assets con IA generativa (cada funcion lanza SinIA si no hay IA disponible,
para que la herramienta use su respaldo procedural)."""
import shutil
from pathlib import Path

from PIL import Image

from . import fondo, imagenes, malla3d, motor, prompts
from .motor import SinIA

ALTURAS = {"personaje": 5.5, "casa": 14, "castillo": 22, "torre": 16, "arbol": 12, "pino": 13, "palmera": 14, "roca": 3,
           "espada": 4, "escudo": 3, "cofre": 3, "moneda": 1.5, "gema": 2, "mascota": 3, "auto": 5, "coche": 5, "nave": 8,
           "dragon": 10, "dragón": 10, "barril": 3, "mesa": 3, "silla": 3.5, "lampara": 7, "farol": 7}


def _activo():
    if not motor.disponible():
        raise SinIA("IA desactivada (modo offline)")


def icono(objeto: str, destino: Path, estilo="cartoon", semilla=7, tam=512, extra="", log=print) -> Path:
    _activo()
    en = prompts.traducir(objeto, log)
    crudo = destino.with_name(destino.stem + "_ia.png")
    motor.imagen(prompts.p_icono(en, estilo, extra), crudo, 1024, 1024, semilla, log=log)
    img = fondo.recortar(fondo.quitar_fondo(Image.open(crudo)))
    img.resize((tam, tam), Image.LANCZOS).save(destino)
    crudo.unlink(missing_ok=True)
    return destino


ELEMENTOS_GUI = {
    "panel": "large empty rectangular window panel frame with decorative border and rounded corners",
    "boton": "wide empty rounded rectangular button, glossy",
    "boton2": "wide empty rounded rectangular secondary button, glossy, different color",
    "slot": "empty square inventory slot frame",
    "barra": "empty horizontal health bar frame",
    "titulo": "empty horizontal title banner ribbon",
}


def arte_gui(tema: str, estilo: str, carpeta: Path, paleta=None, log=print) -> dict:
    _activo()
    tema_en = prompts.traducir(tema, log)
    colores = f", main colors {', '.join(paleta[:3])}" if paleta else ""
    carpeta.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, desc in ELEMENTOS_GUI.items():
        destino = carpeta / f"{k}.png"
        crudo = carpeta / f"{k}_ia.png"
        ancho, alto = (1024, 768) if k == "panel" else ((1024, 512) if k in ("boton", "boton2", "barra", "titulo") else (768, 768))
        try:
            motor.imagen(prompts.p_gui(desc + colores, tema_en, estilo), crudo, ancho, alto, 21, log=log)
            fondo.recortar(fondo.quitar_fondo(Image.open(crudo)), 0.0, cuadrado=False).save(destino)
            crudo.unlink(missing_ok=True)
            out[k] = destino
        except SinIA:
            if not out:
                raise
    return out


def fondo_miniatura(tema: str, titulo: str, estilo: str, destino: Path, log=print) -> Path:
    _activo()
    return motor.imagen(prompts.p_miniatura(prompts.traducir(titulo, log), prompts.traducir(tema, log), estilo),
                        destino, 1344, 768, 5, log=log)


def textura(material: str, tema: str, destino: Path, tam=1024, log=print) -> Path:
    _activo()
    crudo = destino.with_name(destino.stem + "_ia.png")
    motor.imagen(prompts.p_textura(prompts.traducir(material.replace("_", " "), log), prompts.traducir(tema, log)), crudo, 1024, 1024, 3, log=log)
    imagenes.hacer_tileable(Image.open(crudo)).resize((tam, tam), Image.LANCZOS).save(destino)
    crudo.unlink(missing_ok=True)
    return destino


def skybox(tema: str, mood: str, carpeta: Path, log=print) -> dict:
    _activo()
    pano = carpeta / "panorama_ia.png"
    motor.imagen(prompts.p_skybox(prompts.traducir(tema, log), prompts.traducir(mood, log)), pano, 2048, 1024, 9, log=log)
    return imagenes.equirect_a_cubo(Image.open(pano), carpeta, 1024)


def modelo(objeto: str, tema: str, estilo: str, destino: Path, personaje=False, altura=None, semilla=3,
           modo="imagen", max_tris=18000, imagen_usuario: Path | None = None, log=print) -> dict:
    """Texto (o imagen) -> imagen de referencia IA -> malla 3D texturizada IA -> lista para Roblox."""
    _activo()
    obj_en = prompts.traducir(objeto, log)
    ref = None
    if imagen_usuario:
        ref = Path(imagen_usuario)
    elif modo == "imagen":
        ref = destino.with_name(destino.stem + "_referencia.png")
        p = prompts.p_personaje(obj_en, estilo) if personaje else prompts.p_objeto3d(obj_en, prompts.traducir(tema, log), estilo)
        motor.imagen(p, ref, 1024, 1024, semilla, log=log)
        con_alfa = fondo.recortar(fondo.quitar_fondo(Image.open(ref)), 0.08)
        fondo_blanco = Image.new("RGBA", con_alfa.size, (255, 255, 255, 255))
        fondo_blanco.alpha_composite(con_alfa)
        fondo_blanco.convert("RGB").save(ref)
    bruto = destino.with_name(destino.stem + "_ia_bruto.glb")
    archivo = motor.modelo3d(None if ref else f"{obj_en}, {prompts.ESTILOS_ARTE.get(estilo, '')}", bruto, ref, semilla, log)
    if altura is None:
        altura = 5.5 if personaje else next((v for k, v in ALTURAS.items() if k in objeto.lower()), 6.0)
    info = None
    from .. import blender, config as _cfg
    bcfg = _cfg.get().get("blender", {})
    if blender.disponible():
        try:
            log("    Blender: limpiando, reduciendo (conserva textura) y exportando GLB/FBX...")
            r = blender.limpiar_modelo(archivo, destino, altura, max_tris, bcfg.get("exportar_fbx", True),
                                       destino.with_suffix(".png") if bcfg.get("render_preview", True) else None, True, log)
            info = {"triangulos_originales": r.get("triangulos_originales"), "triangulos": r.get("triangulos"), "mallas": 1,
                    "textura": r.get("textura"), "fbx": bool(r.get("fbx")), "medidas_studs": r.get("medidas_studs"), "blender": r.get("blender")}
        except blender.BlenderError as e:
            log(f"    Blender fallo ({str(e)[:120]}); uso el procesado interno.")
    if info is None:
        info = malla3d.preparar_para_roblox(archivo, destino, altura, max_tris)
    if not destino.with_suffix(".png").exists():
        malla3d.render(malla3d.leer_glb(destino), destino.with_suffix(".png"), 384)
    if Path(archivo) != destino:
        Path(archivo).unlink(missing_ok=True)
    info.update({"referencia": ref.name if ref and ref.exists() else None, "altura_studs": altura})
    log(f"    3D listo: {info['triangulos_originales']} triangulos -> {info['mallas']} malla(s)"
        + (" con textura" if info["textura"] else ""))
    return info


def sfx(descripcion: str, destino: Path, duracion=2.5, log=print) -> Path:
    _activo()
    return motor.sfx(prompts.p_sfx(prompts.traducir(descripcion, log)), destino, duracion, log)


def musica(descripcion: str, genero: str, destino: Path, duracion=45, bpm=None, letra=None, log=print) -> Path:
    _activo()
    return motor.musica(prompts.p_musica(prompts.traducir(descripcion, log), genero, bpm), destino, duracion, letra, log)


def copiar(origen: Path, destino: Path) -> Path:
    shutil.copy(origen, destino)
    return destino
