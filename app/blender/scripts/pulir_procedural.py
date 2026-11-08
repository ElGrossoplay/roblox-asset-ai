"""Pule un modelo procedural low-poly para un acabado profesional.

- Biseles pequenos en aristas vivas (limitados por angulo) -> la luz "atrapa" los bordes.
- Normales ponderadas (Weighted Normal) -> caras planas limpias sin sombreado raro.
- Organicos (arboles, rocas, hongos...): una subdivision suave + ruido leve para que no se vean geometricos.
- Material: rugosidad realista y conserva colores por vertice si el modelo los trae.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def _ajustar_materiales(obj):
    for slot in obj.material_slots:
        m = slot.material
        n = comun.bsdf(m)
        if not n:
            continue
        r = comun.entrada_bsdf(n, "Roughness")
        if r and not r.is_linked:
            r.default_value = 0.65
        spec = comun.entrada_bsdf(n, "Specular IOR Level", "Specular")
        if spec and not spec.is_linked:
            spec.default_value = 0.35


def main(p):
    comun.escena_vacia()
    mallas = comun.importar(p["entrada"])
    obj = comun.unir(mallas)
    obj.name = os.path.splitext(os.path.basename(p["glb"]))[0]
    comun.limpiar_geometria(obj, 1e-4)
    dims = obj.dimensions
    tam = max(dims.x, dims.y, dims.z, 1e-3)

    if p.get("organico"):
        sub = obj.modifiers.new("Suave", "SUBSURF")
        sub.levels = 1
        sub.render_levels = 1
        if hasattr(sub, "subdivision_type"):
            sub.subdivision_type = "SIMPLE"
        comun.aplicar_modificador(obj, sub)
        tex = bpy.data.textures.new("Ruido", "CLOUDS")
        tex.noise_scale = tam * 0.35
        disp = obj.modifiers.new("Ruido", "DISPLACE")
        disp.texture = tex
        disp.strength = tam * 0.025
        disp.mid_level = 0.5
        comun.aplicar_modificador(obj, disp)
        comun.suavizar(obj, 50.0)
    else:
        bev = obj.modifiers.new("Bisel", "BEVEL")
        bev.width = tam * 0.012
        bev.segments = 2
        bev.limit_method = "ANGLE"
        bev.angle_limit = 0.5236  # 30 grados
        if hasattr(bev, "harden_normals"):
            bev.harden_normals = True
        if hasattr(bev, "use_clamp_overlap"):
            bev.use_clamp_overlap = True
        comun.aplicar_modificador(obj, bev)
        comun.suavizar(obj, 30.0)
        wn = obj.modifiers.new("Normales", "WEIGHTED_NORMAL")
        if hasattr(wn, "keep_sharp"):
            wn.keep_sharp = True
        comun.aplicar_modificador(obj, wn)

    comun.reducir(obj, int(p.get("max_tris", 18000)))
    comun.triangular(obj)
    _ajustar_materiales(obj)
    comun.exportar_glb(obj, p["glb"])
    if p.get("fbx"):
        try:
            comun.exportar_fbx(obj, p["fbx"])
        except Exception as e:  # noqa: BLE001
            print("FBX no exportado:", e)
            p["fbx"] = None
    preview = None
    if p.get("preview"):
        try:
            import render
            render.preparar_y_renderizar([obj], p["preview"], p.get("tam_preview", 512), p.get("muestras", 24))
            preview = p["preview"]
        except Exception as e:  # noqa: BLE001
            print("Vista previa no generada:", e)
    return {"triangulos": comun.triangulos(obj), "fbx": p.get("fbx"), "preview": preview}


if __name__ == "__main__":
    comun.principal(main)
