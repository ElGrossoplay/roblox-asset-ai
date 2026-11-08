"""Orquestador: tema -> style pack -> assets -> carpeta lista para Roblox."""
import json
import shutil
import time
import traceback
from pathlib import Path

from . import config, director
from .paths import OUTPUT_DIR
from .generators import audio_offline, image_offline, mesh_offline
from .roblox import luau, opencloud
from .ia import creador, motor as motor_ia


def _con_respaldo(nombre_modulo, backend, intento_ia, respaldo, log):
    if backend in ("cloud", "local", "pollinations"):
        try:
            return intento_ia(), backend
        except Exception as e:  # noqa: BLE001
            log(f"  {nombre_modulo}: {backend} fallo ({e}); uso offline.")
    return respaldo(), "offline"


def generar_pack(tema: str, opciones: dict | None = None, log=print) -> Path:
    opciones = {"texturas": True, "skybox": True, "sfx": True, "musica": True, "modelos": True, **(opciones or {})}
    cfg = config.get()
    estilo = director.crear_style_pack(tema, log)
    carpeta = OUTPUT_DIR / f"{estilo['nombre']}_{time.strftime('%Y%m%d_%H%M%S')}"
    carpeta.mkdir(parents=True)
    manifest = {"tema": tema, "nombre": estilo["nombre"], "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
                "texturas": [], "sfx": [], "musica": None, "modelos": [], "skybox": [], "backends": {}, "asset_ids": {}}
    (carpeta / "estilo.json").write_text(json.dumps(estilo, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Estilo: preset base '{estilo['preset_base']}', mood '{estilo['mood']}'")

    if opciones["texturas"]:
        c = cfg["imagen"]
        for t in estilo["texturas"]:
            destino = carpeta / "texturas" / f"{t['nombre']}.png"
            log(f"Textura: {t['nombre']}")

            def ia(t=t, destino=destino):
                if c["backend"] == "pollinations":
                    from .generators import cloud
                    return cloud.imagen_pollinations(t["prompt"], destino, 1024, 1024)
                if c["backend"] == "cloud":
                    from .generators import cloud
                    return cloud.imagen(c["cloud_model"], t["prompt"], destino)
                from .generators import local
                return local.imagen(c["local_model"], t["prompt"], destino, c.get("tamano", 1024))
            ruta, usado = None, None
            if motor_ia.disponible():
                try:
                    ruta, usado = creador.textura(t["nombre"], tema, destino, 1024, log), "ia"
                except motor_ia.SinIA as e:
                    log(f"  textura IA no disponible ({str(e)[:80]})")
            if ruta is None:
                ruta, usado = _con_respaldo("Imagen", c["backend"], ia,
                                            lambda t=t, destino=destino: image_offline.textura(t["nombre"], estilo["paleta"], destino), log)
            manifest["texturas"].append(str(ruta.relative_to(carpeta)).replace("\\", "/"))
            try:  # mapas PBR para MaterialVariant (normal + rugosidad)
                pbr = image_offline.mapas_pbr(ruta, t["nombre"])
                manifest.setdefault("pbr", {})[t["nombre"]] = {
                    "color": manifest["texturas"][-1], "material": image_offline.material_roblox(t["nombre"]),
                    **{k: str(v.relative_to(carpeta)).replace("\\", "/") for k, v in pbr.items()}}
            except Exception as e:  # noqa: BLE001
                log(f"  PBR no disponible para {t['nombre']}: {e}")
            manifest["backends"]["imagen"] = usado

    if opciones["skybox"]:
        log("Skybox: 6 caras")
        rutas = None
        if motor_ia.disponible():
            try:
                rutas = creador.skybox(tema, estilo["mood"], carpeta / "skybox", log)
                (carpeta / "skybox" / "panorama_ia.png").unlink(missing_ok=True)
                manifest["backends"]["skybox"] = "ia"
            except motor_ia.SinIA as e:
                log(f"  cielo IA no disponible ({str(e)[:80]})")
        if rutas is None:
            rutas = image_offline.skybox(estilo["cielo"], carpeta / "skybox")
        manifest["skybox"] = [str(r.relative_to(carpeta)).replace("\\", "/") for r in rutas.values()]

    if opciones["sfx"]:
        c = cfg["sfx"]
        for s in estilo["sfx"]:
            destino = carpeta / "sfx" / f"{s['nombre']}.wav"
            log(f"Efecto: {s['nombre']}")

            def ia(s=s, destino=destino):
                if c["backend"] == "cloud":
                    from .generators import cloud
                    return cloud.audio(c["cloud_model"], s["prompt"], destino, c.get("duracion_seg", 2))
                from .generators import local
                return local.sfx(c["local_model"], s["prompt"], destino, c.get("duracion_seg", 2))
            ruta, usado = None, None
            if motor_ia.disponible():
                try:
                    amb = s["nombre"] in ("olas", "viento", "lluvia", "fuego", "pajaros", "susurro_viento", "noche", "cueva", "rio")
                    ruta, usado = creador.sfx(s["prompt"], destino, 9.0 if amb else 2.5, log), "ia"
                except motor_ia.SinIA as e:
                    log(f"  sonido IA no disponible ({str(e)[:80]})")
            if ruta is None:
                ruta, usado = _con_respaldo("SFX", c["backend"], ia,
                                            lambda s=s, destino=destino: audio_offline.generar_sfx(s["nombre"], destino), log)
            manifest["sfx"].append({"nombre": s["nombre"], "archivo": str(ruta.relative_to(carpeta)).replace("\\", "/")})
            manifest["backends"]["sfx"] = usado

    if opciones["musica"]:
        c = cfg["musica"]
        destino = carpeta / "musica" / "loop_principal.wav"
        log("Musica: loop principal")
        dur = c.get("duracion_seg", 30)

        def ia():
            if c["backend"] == "cloud":
                from .generators import cloud
                return cloud.audio(c["cloud_model"], estilo["musica"]["prompt"], destino, dur)
            from .generators import local
            return local.musica(c["local_model"], estilo["musica"]["prompt"], destino, dur)
        ruta, usado = None, None
        if motor_ia.disponible():
            try:
                from .generators import musica_pro
                genero = musica_pro.detectar_genero(estilo["musica"]["prompt"])
                ruta, usado = creador.musica(f"{tema}, {estilo['mood']}", genero, destino, max(dur, 30), log=log), "ia"
            except motor_ia.SinIA as e:
                log(f"  musica IA no disponible ({str(e)[:80]})")
        if ruta is None:
            ruta, usado = _con_respaldo("Musica", c["backend"], ia,
                                        lambda: audio_offline.generar_musica(estilo["musica"], destino, dur), log)
        manifest["musica"] = str(ruta.relative_to(carpeta)).replace("\\", "/")
        manifest["backends"]["musica"] = usado
        if estilo["musica"].get("_info"):
            manifest["musica_info"] = estilo["musica"].pop("_info")
            log("  {genero} · {bpm} BPM · {segundos}s en loop".format(**manifest["musica_info"]))

    if opciones["modelos"]:
        c = cfg["malla3d"]
        for p in estilo["props"]:
            destino = carpeta / "modelos" / f"{p['nombre']}.glb"
            log(f"Modelo 3D: {p['nombre']}")

            def ia(p=p, destino=destino):
                from .generators import cloud
                ref = destino.with_suffix(".ref.png")
                cloud.imagen(cfg["imagen"]["cloud_model"], p["prompt"], ref)
                return cloud.malla_desde_imagen(c["cloud_model"], ref, destino)
            ruta, usado = None, None
            if motor_ia.disponible():
                try:
                    creador.modelo(p["nombre"].replace("_", " "), tema, "low_poly", destino, log=log)
                    ruta, usado = destino, "ia"
                except motor_ia.SinIA as e:
                    log(f"  3D IA no disponible ({str(e)[:80]})")
            if ruta is None:
                ruta, usado = _con_respaldo("3D", c["backend"], ia,
                                            lambda p=p, destino=destino: mesh_offline.generar_prop(p["nombre"], estilo["paleta"], destino), log)
            manifest["modelos"].append(str(ruta.relative_to(carpeta)).replace("\\", "/"))
            if ruta.with_suffix(".png").exists():
                manifest.setdefault("modelos_preview", []).append(str(ruta.with_suffix(".png").relative_to(carpeta)).replace("\\", "/"))
            manifest["backends"]["malla3d"] = usado

    escribir_salidas(carpeta, estilo, manifest)
    log(f"Listo: {carpeta.name}")
    return carpeta


def escribir_salidas(carpeta: Path, estilo: dict, manifest: dict) -> None:
    (carpeta / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (carpeta / "AplicarEstetica.lua").write_text(luau.script_estetica(estilo, manifest), encoding="utf-8")
    (carpeta / "LEEME.txt").write_text(
        f"Pack: {estilo['tema']}\n\n"
        "1. AplicarEstetica.lua -> pegalo en ServerScriptService (o en la Command Bar de Studio).\n"
        "2. texturas/ y skybox/ -> importalos con el Asset Manager o subelos desde la app.\n"
        "3. modelos/*.glb -> File > Import 3D en Roblox Studio.\n"
        "4. sfx/ y musica/ -> sube los audios (Asset Manager) o usa 'Subir a Roblox' en la app;\n"
        "   al subir desde la app, el script se regenera con los IDs.\n", encoding="utf-8")


def subir_pack(carpeta: Path, log=print) -> dict:
    manifest = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    estilo = json.loads((carpeta / "estilo.json").read_text(encoding="utf-8"))
    archivos = manifest["texturas"] + manifest["skybox"] + [s["archivo"] for s in manifest["sfx"]]
    for mapas in manifest.get("pbr", {}).values():
        archivos += [mapas["normal"], mapas["rugosidad"]]
    if manifest.get("musica"):
        archivos.append(manifest["musica"])
    archivos += manifest["modelos"]
    for rel in archivos:
        if rel in manifest["asset_ids"]:
            continue
        try:
            log(f"Subiendo {rel}...")
            manifest["asset_ids"][rel] = opencloud.subir(carpeta / rel, f"{manifest['nombre']}_{Path(rel).stem}")
        except Exception as e:  # noqa: BLE001
            log(f"  Error con {rel}: {e}")
            if "ROBLOX_API_KEY" in str(e):
                break
    escribir_salidas(carpeta, estilo, manifest)
    return manifest


def borrar_pack(carpeta: Path) -> None:
    if carpeta.resolve().parent == OUTPUT_DIR.resolve():
        shutil.rmtree(carpeta)


def error_texto(e: Exception) -> str:
    return "".join(traceback.format_exception_only(type(e), e)).strip()
