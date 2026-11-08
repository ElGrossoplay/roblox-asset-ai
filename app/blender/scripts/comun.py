"""Funciones compartidas para los scripts de Blender (compatibles con Blender 3.6 a 5.x).
Se ejecutan DENTRO de Blender:  blender -b --python <script> -- entrada.json
"""
import json
import math
import os
import sys
import traceback

import bmesh
import bpy
from mathutils import Vector

VERSION = bpy.app.version


def parametros() -> dict:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with open(argv[0], encoding="utf-8") as f:
        return json.load(f)


def terminar(params: dict, ok=True, **datos):
    datos["ok"] = ok
    datos["blender"] = bpy.app.version_string
    with open(params["salida_json"], "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)


def principal(fn):
    """Envuelve el script: cualquier excepcion se reporta en el JSON de salida."""
    params = parametros()
    try:
        datos = fn(params) or {}
        terminar(params, True, **datos)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        terminar(params, False, error=f"{type(e).__name__}: {e}")


def escena_vacia():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    escena = bpy.context.scene
    escena.unit_settings.system = "METRIC"
    escena.unit_settings.scale_length = 1.0
    return escena


def importar(ruta: str):
    ext = os.path.splitext(ruta)[1].lower()
    antes = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=ruta)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=ruta)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=ruta)
        else:
            bpy.ops.import_scene.obj(filepath=ruta)
    elif ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=ruta)
        else:
            bpy.ops.import_mesh.stl(filepath=ruta)
    else:
        raise ValueError(f"Formato no soportado: {ext}")
    nuevos = [o for o in bpy.data.objects if o not in antes]
    mallas = [o for o in nuevos if o.type == "MESH"]
    if not mallas:
        raise ValueError("El archivo no contiene mallas")
    return mallas


def seleccionar(objs, activo=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = activo or objs[0]


def unir(mallas):
    """Aplica transformaciones (incluidas las de padres/vacios) y une todo en un objeto."""
    for o in mallas:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    seleccionar(mallas)
    try:  # mallas compartidas (instancias) no se pueden transformar: se independizan primero
        bpy.ops.object.make_single_user(object=True, obdata=True)
    except (RuntimeError, TypeError):
        pass
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(mallas) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    # borra vacios/armaduras importados que ya no sirven
    for o in list(bpy.data.objects):
        if o.type in ("EMPTY",) and not o.children:
            bpy.data.objects.remove(o, do_unlink=True)
    return obj


def limpiar_geometria(obj, distancia=1e-5):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distancia)
    sueltos = [v for v in bm.verts if not v.link_faces]
    if sueltos:
        bmesh.ops.delete(bm, geom=sueltos, context="VERTS")
    degeneradas = [f for f in bm.faces if f.calc_area() < 1e-12]
    if degeneradas:
        bmesh.ops.delete(bm, geom=degeneradas, context="FACES")
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def triangulos(obj) -> int:
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def aplicar_modificador(obj, mod):
    seleccionar([obj])
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError:
        # algunos modificadores no se pueden aplicar en ciertas versiones: se descarta
        obj.modifiers.remove(mod)


def reducir(obj, max_tris: int) -> int:
    """Decimate 'collapse': reduce triangulos CONSERVANDO las UV (la textura sigue sirviendo)."""
    tris = triangulos(obj)
    if tris <= max_tris:
        return tris
    for _ in range(3):  # el collapse no siempre llega exacto: se repite
        ratio = max(0.01, min(1.0, max_tris / max(triangulos(obj), 1) * 0.98))
        mod = obj.modifiers.new("Reducir", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        if hasattr(mod, "use_collapse_triangulate"):
            mod.use_collapse_triangulate = True
        aplicar_modificador(obj, mod)
        if triangulos(obj) <= max_tris:
            break
    return triangulos(obj)


def triangular(obj):
    mod = obj.modifiers.new("Triangular", "TRIANGULATE")
    aplicar_modificador(obj, mod)


def suavizar(obj, angulo_grados=40.0):
    """Suavizado por angulo: la API cambio en Blender 4.1 (auto smooth paso a ser modificador)."""
    seleccionar([obj])
    ang = math.radians(angulo_grados)
    if VERSION >= (4, 1, 0):
        for op in ("shade_smooth_by_angle", "shade_auto_smooth"):
            fn = getattr(bpy.ops.object, op, None)
            if fn is None:
                continue
            try:
                fn(angle=ang)
                return
            except (RuntimeError, TypeError):
                continue
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_smooth()
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
            obj.data.auto_smooth_angle = ang


def normalizar(obj, altura: float):
    """Escala a la altura pedida (studs), centra en X/Y y apoya en el suelo (Z=0); pivote abajo al centro."""
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    alto = max(mx.z - mn.z, 1e-6)
    s = altura / alto
    centro = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    for v in obj.data.vertices:
        v.co = (obj.matrix_world @ v.co - centro) * s
    obj.matrix_world.identity()
    obj.location = (0, 0, 0)
    obj.data.update()
    return [(mx.x - mn.x) * s, (mx.y - mn.y) * s, altura]


def empaquetar_texturas():
    for img in bpy.data.images:
        try:
            if img.source == "FILE" and not img.packed_file:
                img.pack()
        except RuntimeError:
            pass


def exportar_glb(obj, ruta):
    seleccionar([obj])
    kw = dict(filepath=ruta, export_format="GLB", use_selection=True, export_apply=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        kw.pop("export_apply", None)
        bpy.ops.export_scene.gltf(**kw)


def exportar_fbx(obj, ruta):
    """FBX con texturas embebidas, eje Y arriba (Roblox)."""
    seleccionar([obj])
    kw = dict(filepath=ruta, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
              apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
              path_mode="COPY", embed_textures=True, bake_space_transform=True, add_leaf_bones=False)
    try:
        bpy.ops.export_scene.fbx(**kw)
    except TypeError:
        for k in ("bake_space_transform", "add_leaf_bones", "mesh_smooth_type"):
            kw.pop(k, None)
        bpy.ops.export_scene.fbx(**kw)


def bsdf(material):
    if not material or not material.use_nodes:
        return None
    return next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def entrada_bsdf(nodo, *nombres):
    for n in nombres:
        if n in nodo.inputs:
            return nodo.inputs[n]
    return None
