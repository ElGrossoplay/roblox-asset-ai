"""Vista previa de estudio con Cycles en CPU (funciona en cualquier PC, con o sin GPU)."""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comun  # noqa: E402


def _mat_suelo():
    m = bpy.data.materials.new("Suelo")
    m.use_nodes = True
    n = comun.bsdf(m)
    if n:
        n.inputs["Base Color"].default_value = (0.08, 0.1, 0.15, 1)
        e = comun.entrada_bsdf(n, "Roughness")
        if e:
            e.default_value = 0.9
    return m


def preparar_y_renderizar(objs, ruta, tam=512, muestras=24):
    escena = bpy.context.scene
    puntos = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector((min(p.x for p in puntos), min(p.y for p in puntos), min(p.z for p in puntos)))
    mx = Vector((max(p.x for p in puntos), max(p.y for p in puntos), max(p.z for p in puntos)))
    centro = (mn + mx) / 2
    radio = max((mx - mn).length / 2, 1e-3)

    # suelo
    bpy.ops.mesh.primitive_plane_add(size=radio * 12, location=(centro.x, centro.y, mn.z))
    suelo = bpy.context.active_object
    suelo.data.materials.append(_mat_suelo())

    # luces: sol + relleno
    sol = bpy.data.lights.new("Sol", "SUN")
    sol.energy = 3.0
    if hasattr(sol, "angle"):
        sol.angle = math.radians(8)
    o_sol = bpy.data.objects.new("Sol", sol)
    o_sol.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    escena.collection.objects.link(o_sol)
    relleno = bpy.data.lights.new("Relleno", "AREA")
    relleno.energy = 400 * radio ** 2
    relleno.size = radio * 3
    o_rel = bpy.data.objects.new("Relleno", relleno)
    o_rel.location = centro + Vector((-radio * 3, -radio * 2.5, radio * 2))
    o_rel.rotation_euler = (math.radians(60), 0, math.radians(-50))
    escena.collection.objects.link(o_rel)

    # mundo
    mundo = bpy.data.worlds.new("Mundo")
    mundo.use_nodes = True
    fondo = mundo.node_tree.nodes.get("Background")
    if fondo:
        fondo.inputs[0].default_value = (0.16, 0.2, 0.3, 1)
        fondo.inputs[1].default_value = 0.7
    escena.world = mundo

    # camara 3/4 que encuadra el objeto
    cam = bpy.data.cameras.new("Camara")
    cam.lens = 50
    o_cam = bpy.data.objects.new("Camara", cam)
    escena.collection.objects.link(o_cam)
    direccion = Vector((1.0, -1.25, 0.75)).normalized()
    fov = 2 * math.atan(cam.sensor_width / (2 * cam.lens))
    dist = radio / math.sin(fov / 2) * 1.08
    o_cam.location = centro + direccion * dist
    o_cam.rotation_euler = (centro - o_cam.location).to_track_quat("-Z", "Y").to_euler()
    escena.camera = o_cam

    # Cycles en CPU: lo mas compatible (Eevee cambia de nombre entre versiones y necesita GPU/OpenGL)
    escena.render.engine = "CYCLES"
    escena.cycles.device = "CPU"
    escena.cycles.samples = int(muestras)
    if hasattr(escena.cycles, "use_adaptive_sampling"):
        escena.cycles.use_adaptive_sampling = True
    try:
        escena.cycles.use_denoising = True
    except AttributeError:
        pass
    escena.render.resolution_x = escena.render.resolution_y = int(tam)
    escena.render.resolution_percentage = 100
    escena.render.image_settings.file_format = "PNG"
    escena.view_settings.view_transform = "Filmic" if bpy.app.version < (4, 0, 0) else "AgX"
    escena.render.filepath = ruta
    bpy.ops.render.render(write_still=True)
    return ruta


def main(p):
    comun.escena_vacia()
    objs = comun.importar(p["entrada"])
    preparar_y_renderizar(objs, p["preview"], p.get("tam_preview", 512), p.get("muestras", 24))
    return {"preview": p["preview"]}


if __name__ == "__main__":
    comun.principal(main)
