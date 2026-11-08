"""Limpia un modelo 3D generado por IA y lo deja listo para Roblox.

1. Importa (GLB/GLTF/FBX/OBJ/STL), aplica transformaciones y une todo en UNA malla.
2. Une vertices duplicados, borra geometria suelta/degenerada, recalcula normales.
3. Reduce triangulos con Decimate (collapse) conservando las UV -> la textura sigue sirviendo.
4. Triangula, suaviza por angulo, escala a studs, pivote abajo al centro.
5. Empaqueta texturas y exporta GLB (+ FBX con texturas embebidas) y vista previa.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def main(p):
    comun.escena_vacia()
    mallas = comun.importar(p["entrada"])
    obj = comun.unir(mallas)
    obj.name = os.path.splitext(os.path.basename(p["glb"]))[0]
    tris_ini = comun.triangulos(obj)
    comun.limpiar_geometria(obj, 1e-5)
    tris = comun.reducir(obj, int(p.get("max_tris", 18000)))
    comun.triangular(obj)
    comun.suavizar(obj, 60.0 if p.get("organico", True) else 35.0)
    medidas = comun.normalizar(obj, float(p.get("altura", 6.0)))
    comun.empaquetar_texturas()
    con_textura = any(img.size[0] > 0 for img in __import__("bpy").data.images)
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
    return {"triangulos_originales": tris_ini, "triangulos": comun.triangulos(obj), "mallas": 1, "textura": con_textura,
            "medidas_studs": [round(x, 2) for x in medidas], "fbx": p.get("fbx"), "preview": preview, "reducido_a": tris}


if __name__ == "__main__":
    comun.principal(main)
