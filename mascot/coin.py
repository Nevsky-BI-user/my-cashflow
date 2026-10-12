# -*- coding: utf-8 -*-
"""Процедурна монета ₴ для анімації «Розподіл зарплати».

Запуск лише без звуку і з чистими налаштуваннями:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -noaudio --factory-startup -P mascot\\coin.py -- [ключі]

Ключі після "--":
  --out DIR        тека для PNG-кадрів (типово %TEMP%\\coin-frames)
  --only LIST      still,spin,flip,burst (типово всі)
  --samples N      семпли Cycles (типово 256)
  --view NAME      перетворення кольору: AgX або Standard (типово AgX)

Скрипт нічого не завантажує: геометрія, матеріали й світло будуються кодом,
шрифт береться з системного C:\\Windows\\Fonts.
"""
import bpy
import bmesh
import math
import os
import random
import sys
import tempfile
import time
from mathutils import Vector, Matrix, Quaternion

# ---------------------------------------------------------------- аргументи
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


OUT = arg("--out", os.path.join(tempfile.gettempdir(), "coin-frames"))
ONLY = arg("--only", "still,spin,flip,burst").split(",")
SAMPLES = int(arg("--samples", "256"))
PREVIEW = float(arg("--res-scale", "1"))   # для швидких проб
LIGHT = float(arg("--light-scale", "0.6"))
VIEW = arg("--view", "AgX")

# Бренд-кольори (sRGB) -> лінійні
def srgb(hexstr):
    hexstr = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hexstr[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


TEAL = srgb("14b8a6")
INDIGO = srgb("4f46e5")
VIOLET = srgb("a21caf")
GOLD_LIGHT = srgb("fde68a")

# Розміри монети (радіус 1)
R = 1.0
FIELD_Z = 0.085      # рівень поля
RIM_Z = 0.122        # верх бортика
SIDE_Z = 0.088       # де гурт переходить у фаску
DOME = 0.016         # опуклість поля: відбиття тече градієнтом
REEDS = 120          # рифлі на гурті
STEPS = 480          # сегментів обертання профілю

# ---------------------------------------------------------------- сцена
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"

prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
try:
    prefs.refresh_devices()
except Exception:
    prefs.get_devices()
gpu = False
for d in prefs.devices:
    d.use = d.type == "OPTIX"
    gpu = gpu or d.use
scene.cycles.device = "GPU" if gpu else "CPU"
print("COIN device:", scene.cycles.device, [d.name for d in prefs.devices if d.use])

scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.seed = 7
scene.cycles.use_animated_seed = False
scene.cycles.use_denoising = True
for dn in ("OPTIX", "OPENIMAGEDENOISE"):
    try:
        scene.cycles.denoiser = dn
        break
    except Exception:
        pass
scene.cycles.max_bounces = 8
scene.cycles.glossy_bounces = 6
scene.cycles.transparent_max_bounces = 16
scene.render.film_transparent = True
scene.render.use_motion_blur = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.render.resolution_percentage = 100
try:
    scene.view_settings.view_transform = VIEW
except Exception:
    print("COIN view transform not set:", VIEW)
try:
    scene.view_settings.look = "AgX - Medium High Contrast" if VIEW == "AgX" else "None"
except Exception:
    pass


def link(obj, parent=None):
    scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def node(nt, kind, loc=(0, 0), **inputs):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


# ---------------------------------------------------------------- матеріали
def gold_material(name, rough_lo, rough_hi, frosted, base=(1.0, 0.71, 0.28)):
    """Золото: варіації шорсткості, мікроподряпини, патина в западинах.

    Emission і Alpha керуються з Python (для спалаху в burst).
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (900, 0))
    p = node(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    p.name = "BSDF"
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Base Color"].default_value = base + (1,)
    p.inputs["Specular Tint"].default_value = (1.0, 0.84, 0.52, 1)
    p.inputs["Emission Color"].default_value = (1.0, 0.72, 0.32, 1)
    p.inputs["Emission Strength"].default_value = 0.0
    nt.links.new(p.outputs[0], out.inputs[0])

    tc = node(nt, "ShaderNodeTexCoord", (-900, 0))
    # великі плями зношеності
    n1 = node(nt, "ShaderNodeTexNoise", (-650, 200))
    n1.inputs["Scale"].default_value = 48.0    # дрібна зношеність, не плями
    n1.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    # мікроподряпини: шум, розтягнутий в одному напрямку
    mp = node(nt, "ShaderNodeMapping", (-800, -200))
    mp.inputs["Scale"].default_value = (260.0, 6.0, 6.0)
    mp.inputs["Rotation"].default_value = (0, 0, 0.6)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    n2 = node(nt, "ShaderNodeTexNoise", (-650, -200))
    n2.inputs["Scale"].default_value = 1.0
    n2.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs[0], n2.inputs["Vector"])

    mix = node(nt, "ShaderNodeMix", (-420, 100))
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.15
    nt.links.new(n1.outputs["Fac"], mix.inputs["A"])
    nt.links.new(n2.outputs["Fac"], mix.inputs["B"])

    ramp = node(nt, "ShaderNodeValToRGB", (-220, 100))
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (rough_lo,) * 3 + (1,)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (rough_hi,) * 3 + (1,)
    nt.links.new(mix.outputs["Result"], ramp.inputs["Fac"])

    # патина в западинах: AO затемнює колір і додає шорсткості
    ao = node(nt, "ShaderNodeAmbientOcclusion", (-420, 420))
    ao.samples = 8
    ao.inputs["Distance"].default_value = 0.06
    dirt = node(nt, "ShaderNodeMix", (100, 380))
    dirt.data_type = "RGBA"
    dirt.inputs["A"].default_value = (0.42, 0.24, 0.07, 1)
    dirt.inputs["B"].default_value = base + (1,)
    aor = node(nt, "ShaderNodeMapRange", (-200, 420))
    aor.inputs["From Min"].default_value = 0.35
    aor.inputs["From Max"].default_value = 1.0
    nt.links.new(ao.outputs["AO"], aor.inputs["Value"])
    nt.links.new(aor.outputs["Result"], dirt.inputs["Factor"])
    nt.links.new(dirt.outputs["Result"], p.inputs["Base Color"])

    rmix = node(nt, "ShaderNodeMix", (300, 120))
    rmix.data_type = "FLOAT"
    rmix.inputs["B"].default_value = 0.55
    inv = node(nt, "ShaderNodeMath", (100, 200), )
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(aor.outputs["Result"], inv.inputs[1])
    nt.links.new(inv.outputs[0], rmix.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], rmix.inputs["A"])
    nt.links.new(rmix.outputs["Result"], p.inputs["Roughness"])

    # дрібний рельєф поверхні (матовий рельєф знаку має більший)
    n3 = node(nt, "ShaderNodeTexNoise", (-200, -300))
    n3.inputs["Scale"].default_value = 160.0 if frosted else 90.0
    n3.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], n3.inputs["Vector"])
    bump = node(nt, "ShaderNodeBump", (300, -250))
    bump.inputs["Strength"].default_value = 0.04 if frosted else 0.02
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(n3.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def emit_material(name, strength):
    """Іскра: колір і прозорість з Object Color (RGBA)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (600, 0))
    oi = node(nt, "ShaderNodeObjectInfo", (-400, 0))
    em = node(nt, "ShaderNodeEmission", (0, 60))
    em.inputs["Strength"].default_value = strength
    tr = node(nt, "ShaderNodeBsdfTransparent", (0, -100))
    mx = node(nt, "ShaderNodeMixShader", (300, 0))
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    nt.links.new(oi.outputs["Alpha"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    return m


def flash_material():
    """Кругле сяйво: сферичний градієнт, інтенсивність з Object Color alpha."""
    m = bpy.data.materials.new("flash")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (800, 0))
    tc = node(nt, "ShaderNodeTexCoord", (-600, 0))
    gr = node(nt, "ShaderNodeTexGradient", (-400, 0))
    gr.gradient_type = "SPHERICAL"
    nt.links.new(tc.outputs["Object"], gr.inputs["Vector"])
    pw = node(nt, "ShaderNodeMath", (-200, 0))
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.2
    nt.links.new(gr.outputs["Fac"], pw.inputs[0])
    oi = node(nt, "ShaderNodeObjectInfo", (-200, 200))
    mul = node(nt, "ShaderNodeMath", (0, 0))
    mul.operation = "MULTIPLY"
    nt.links.new(pw.outputs[0], mul.inputs[0])
    nt.links.new(oi.outputs["Alpha"], mul.inputs[1])
    em = node(nt, "ShaderNodeEmission", (200, 120))
    em.inputs["Strength"].default_value = 1.6
    nt.links.new(oi.outputs["Color"], em.inputs["Color"])
    tr = node(nt, "ShaderNodeBsdfTransparent", (200, -80))
    mx = node(nt, "ShaderNodeMixShader", (500, 0))
    nt.links.new(mul.outputs[0], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    return m


GOLD = gold_material("gold_polished", 0.075, 0.10, frosted=False)
# рельєф: насичене золото, сатинова поверхня; читається фаскою, а не матовістю
GOLD_RELIEF = gold_material("gold_frosted", 0.17, 0.22, frosted=True, base=(1.0, 0.60, 0.16))
GOLD_EDGE = gold_material("gold_edge", 0.16, 0.30, frosted=False)


# ---------------------------------------------------------------- геометрія монети
def coin_profile():
    """Профіль (r, z) верхньої половини від центру назовні."""
    pts = []
    # поле з ледь опуклим центром
    for i in range(13):
        r = 0.80 * i / 12
        pts.append((r, FIELD_Z + DOME * (1 - (r / 0.80) ** 2)))
    pts += [
        (0.812, FIELD_Z + 0.002),   # жолобок біля бортика
        (0.828, FIELD_Z + 0.020),
        (0.842, RIM_Z - 0.004),
        (0.852, RIM_Z),             # верх бортика
        (0.940, RIM_Z),
        (0.958, RIM_Z - 0.006),
        (0.980, RIM_Z - 0.020),     # фаска
        (0.995, SIDE_Z + 0.008),
        (R, SIDE_Z),
    ]
    return pts


def build_coin_body():
    top = coin_profile()
    side = [(R, SIDE_Z * f) for f in (0.5, 0.0, -0.5)]
    bottom = [(r, -z) for (r, z) in reversed(top)]
    prof = top + side + bottom
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for (r, z) in prof]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=2 * math.pi, steps=STEPS, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # гострі ребра за кутом профілю (до рифлення, щоб рифлі лишились гладкими)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(32):
            e.smooth = False
    # рифлений гурт: модулюємо радіус вершин на бічній стінці
    for v in bm.verts:
        r = math.hypot(v.co.x, v.co.y)
        if r > R - 1e-4 and abs(v.co.z) <= SIDE_Z + 1e-5:
            a = math.atan2(v.co.y, v.co.x)
            k = 1.0 - 0.011 * (0.5 - 0.5 * math.cos(a * REEDS))
            v.co.x *= k
            v.co.y *= k
    me = bpy.data.meshes.new("coin_body")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    # окремий матеріал гурту (трохи матовіший)
    me.materials.append(GOLD)
    me.materials.append(GOLD_EDGE)
    for poly in me.polygons:
        c = poly.center
        if math.hypot(c.x, c.y) > 0.99 and abs(c.z) < SIDE_Z:
            poly.material_index = 1
    return bpy.data.objects.new("coin_body", me)


def mesh_from_curve(obj, name):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    me.name = name
    bpy.data.objects.remove(obj)
    return me


def build_hryvnia(coin):
    font = None
    for f in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        p = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", f)
        if os.path.exists(p):
            font = bpy.data.fonts.load(p)
            break
    cu = bpy.data.curves.new("hryvnia", "FONT")
    cu.font = font
    cu.body = "\u20b4"
    cu.size = 1.62
    cu.extrude = 0.008
    cu.bevel_depth = 0.013
    cu.bevel_resolution = 0     # плоска фаска: чіткий блик по контуру
    cu.resolution_u = 24
    tmp = bpy.data.objects.new("hryvnia_tmp", cu)
    link(tmp)
    me = mesh_from_curve(tmp, "hryvnia")
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    assert me.vertices and max(xs) - min(xs) > 0.3, "гліф ₴ порожній"
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    me.transform(Matrix.Translation((-cx, -cy, 0)))
    print("COIN glyph size", round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3))
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(GOLD_RELIEF)
    o = link(bpy.data.objects.new("hryvnia", me), coin)
    o.location = (0, 0, FIELD_Z + DOME * 0.75 + 0.006)
    return o


def build_arrow(coin):
    """Стрілка росту з лого (лінія вгору-вправо з кутовим вістрям) на реверсі."""
    cu = bpy.data.curves.new("arrow", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.042
    cu.bevel_resolution = 4
    cu.use_fill_caps = True

    def poly(points):
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for i, (x, y) in enumerate(points):
            sp.points[i].co = (x, y, 0.0, 1.0)

    # тренд: злам униз, потім ріст під 45 градусів як у лого
    poly([(-0.56, -0.30), (-0.22, 0.04), (0.02, -0.18), (0.50, 0.30)])
    poly([(0.20, 0.30), (0.50, 0.30), (0.50, 0.00)])
    tmp = bpy.data.objects.new("arrow_tmp", cu)
    link(tmp)
    me = mesh_from_curve(tmp, "arrow")
    me.transform(Matrix.Scale(0.42, 4, (0, 0, 1)))   # сплющуємо трубку в рельєф
    for poly_ in me.polygons:
        poly_.use_smooth = True
    me.materials.append(GOLD_RELIEF)
    o = link(bpy.data.objects.new("arrow", me), coin)
    # реверс: поворот на 180 градусів навколо локальної Y, читається після оберту монети
    o.rotation_euler = (0, math.pi, 0)
    o.location = (0, 0, -(FIELD_Z + DOME * 0.75 + 0.004))
    return o


def build_bead_ring(coin, z_sign):
    """Тонкий намистовий обідок біля бортика."""
    me = bpy.data.meshes.new("beads")
    bm = bmesh.new()
    n = 72
    for i in range(n):
        a = 2 * math.pi * i / n
        m = Matrix.Translation((0.765 * math.cos(a), 0.765 * math.sin(a), 0))
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.014, matrix=m)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Scale(0.6, 4, (0, 0, 1)))
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(GOLD_RELIEF)
    o = link(bpy.data.objects.new("beads", me), coin)
    o.location = (0, 0, z_sign * (FIELD_Z + 0.002))
    return o


# Ієрархія: spin (оберт навколо світової Z) -> tilt -> coin (вісь монети до камери)
rig_spin = link(bpy.data.objects.new("rig_spin", None))
rig_tilt = link(bpy.data.objects.new("rig_tilt", None), rig_spin)
coin = link(build_coin_body(), rig_tilt)
coin.rotation_euler = (math.radians(90), 0, 0)   # аверс дивиться на камеру (-Y)
build_hryvnia(coin)
build_arrow(coin)
build_bead_ring(coin, 1)
build_bead_ring(coin, -1)
COIN_PARTS = [o for o in scene.objects if o.type == "MESH"]
COIN_MATS = [GOLD, GOLD_RELIEF, GOLD_EDGE]

# ---------------------------------------------------------------- світло
def area(name, loc, size, color, power, shape="RECTANGLE", roll=0.0):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = shape
    ld.size = size[0]
    ld.size_y = size[1]
    ld.color = color
    ld.energy = power * LIGHT
    o = link(bpy.data.objects.new(name, ld))
    o.location = loc
    d = Vector((0, 0, 0)) - Vector(loc)
    q = d.to_track_quat("-Z", "Y") @ Quaternion((0, 0, 1), math.radians(roll))
    o.rotation_euler = q.to_euler()
    o.visible_camera = False
    return o


# великий теплий софтбокс ліворуч-спереду: його бачить аверс у ракурсі 3/4
area("key", (-3.6, -2.4, 4.6), (3.0, 3.0), (1.0, 0.93, 0.84), 520)
# вузька діагональна смуга: чіткий блик, що тече по опуклому полю
area("strip", (-5.4, -2.6, 1.7), (0.35, 5.0), (1.0, 0.96, 0.9), 260, roll=35)
# софтбокс позаду камери згори: градієнт на аверсі анфас
area("front", (0.0, -7.0, 2.6), (7.0, 2.4), (1.0, 0.96, 0.9), 380)
# верхнє світло: бортик і верх гурту
area("top", (0.0, -0.5, 6.5), (6.0, 3.0), (1.0, 0.97, 0.92), 300)
# холодний заповнювач праворуч: блик на іншому боці під час оберту
area("fill", (5.0, -3.2, 1.0), (2.2, 3.5), (0.92, 0.95, 1.0), 220)
# бренд-смуги позаду: бірюзовий і індиго-фіолетовий відблиск лише на фасці й гурті
area("teal", (-3.6, 3.0, 3.2), (0.35, 4.0), TEAL, 70)
area("indigo", (4.0, 2.4, 1.6), (0.35, 4.0), INDIGO, 70)
area("violet", (2.6, 3.4, 3.6), (0.35, 3.0), VIOLET, 28)
# тепле відбите світло знизу: монета в перекиданні лишається золотою
area("bounce", (0.0, -3.2, -4.6), (6.5, 3.0), (1.0, 0.86, 0.66), 340)
area("bounce_back", (0.0, 3.0, -4.2), (5.0, 2.5), (1.0, 0.84, 0.62), 200)
# нижній правий: його відбиває реверс, коли монета в перекиданні дивиться вниз-уперед
area("bounce_r", (3.3, -1.2, -4.6), (3.5, 3.5), (1.0, 0.86, 0.64), 300)
# контровий теплий: світиться гурт на ребрі
area("rim", (0.0, 4.5, 3.0), (3.0, 1.0), (1.0, 0.9, 0.75), 120)

# світ: темний градієнт із світлішою верхньою півсферою (тільки для відбиттів)
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
wout = node(wnt, "ShaderNodeOutputWorld", (600, 0))
bg = node(wnt, "ShaderNodeBackground", (400, 0))
wtc = node(wnt, "ShaderNodeTexCoord", (-400, 0))
sep = node(wnt, "ShaderNodeSeparateXYZ", (-200, 0))
wnt.links.new(wtc.outputs["Generated"], sep.inputs[0])
wr = node(wnt, "ShaderNodeValToRGB", (0, 0))
els = wr.color_ramp.elements
els[0].position = 0.0
els[0].color = (0.07, 0.055, 0.035, 1)
els[1].position = 1.0
els[1].color = (0.60, 0.55, 0.48, 1)
e = els.new(0.52)
e.color = (0.11, 0.095, 0.08, 1)
mr = node(wnt, "ShaderNodeMapRange", (-100, -150))
mr.inputs["From Min"].default_value = -1.0
mr.inputs["From Max"].default_value = 1.0
wnt.links.new(sep.outputs["Z"], mr.inputs["Value"])
wnt.links.new(mr.outputs["Result"], wr.inputs["Fac"])
wnt.links.new(wr.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
wnt.links.new(bg.outputs[0], wout.inputs[0])

# ---------------------------------------------------------------- камера
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 60
cam_data.sensor_width = 36
cam = link(bpy.data.objects.new("cam", cam_data))
scene.camera = cam


def place_camera(frame_width):
    """Камера трохи згори; frame_width: ширина кадру в одиницях сцени біля монети."""
    dist = frame_width / (cam_data.sensor_width / cam_data.lens)
    el = math.radians(6)
    cam.location = (0, -dist * math.cos(el), dist * math.sin(el))
    d = Vector((0, 0, 0)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def clean(sub):
    """Прибирає старі кадри режиму, щоб пакувальник не взяв застарілі."""
    d = os.path.join(OUT, sub)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".png"):
            os.remove(os.path.join(d, f))


def render(path, res):
    res = int(res * PREVIEW)
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print("COIN frame", os.path.basename(path), round(time.time() - t, 2), "s")


def reset_pose():
    rig_spin.rotation_euler = (0, 0, 0)
    rig_tilt.rotation_euler = (0, 0, 0)
    rig_spin.scale = (1, 1, 1)
    for m in COIN_MATS:
        b = m.node_tree.nodes["BSDF"]
        b.inputs["Emission Strength"].default_value = 0.0
        b.inputs["Alpha"].default_value = 1.0
    for o in COIN_PARTS:
        o.hide_render = False


os.makedirs(OUT, exist_ok=True)
T0 = time.time()
timings = {}

# ---------------------------------------------------------------- still: аверс 3/4
if "still" in ONLY:
    t = time.time()
    clean("still")
    reset_pose()
    place_camera(2.34)
    rig_spin.rotation_euler = (0, 0, math.radians(-32))
    rig_tilt.rotation_euler = (math.radians(-12), 0, 0)
    render(os.path.join(OUT, "still", "still.png"), 768)
    timings["still"] = time.time() - t

# ---------------------------------------------------------------- spin: 24 кадри + контрольний 25-й
if "spin" in ONLY:
    t = time.time()
    clean("spin")
    reset_pose()
    place_camera(2.34)
    for i in range(25):   # кадр 24 (індекс) = 360 градусів, лише для перевірки шва
        rig_spin.rotation_euler = (0, 0, 2 * math.pi * i / 24)
        render(os.path.join(OUT, "spin", "f%02d.png" % i), 320)
    timings["spin"] = time.time() - t

# ---------------------------------------------------------------- flip: перекидання в польоті
if "flip" in ONLY:
    t = time.time()
    clean("flip")
    reset_pose()
    place_camera(2.34)
    rig_spin.rotation_euler = (0, 0, math.radians(28))   # постійний розворот
    for i in range(12):
        rig_tilt.rotation_euler = (-2 * math.pi * i / 12, 0, 0)
        render(os.path.join(OUT, "flip", "f%02d.png" % i), 320)
    timings["flip"] = time.time() - t

# ---------------------------------------------------------------- burst: монета розсипається іскрами
if "burst" in ONLY:
    t = time.time()
    clean("burst")
    reset_pose()
    place_camera(2.95)
    rng = random.Random(21)

    spark_mat = emit_material("spark", 1.8)
    ico = bpy.data.meshes.new("spark_mesh")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    bm.to_mesh(ico)
    bm.free()
    for poly in ico.polygons:
        poly.use_smooth = True
    ico.materials.append(spark_mat)

    chip = bpy.data.meshes.new("chip_mesh")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=5, radius1=1.0, radius2=0.8, depth=0.25)
    bm.to_mesh(chip)
    bm.free()
    chip.materials.append(GOLD)

    palette = [GOLD_LIGHT, (1.0, 0.72, 0.30), (1.0, 0.62, 0.20), (1.0, 0.90, 0.70)]
    parts = []
    for k in range(44):
        a = rng.uniform(0, 2 * math.pi)
        el = rng.uniform(-0.35, 0.35)
        d = Vector((math.cos(a) * math.cos(el), math.sin(el) * 0.6, math.sin(a) * math.cos(el))).normalized()
        start = Vector((math.cos(a), 0, math.sin(a))) * rng.uniform(0.1, 0.85)
        is_chip = k % 4 == 0
        o = link(bpy.data.objects.new("p%d" % k, chip if is_chip else ico))
        o.hide_render = True
        col = palette[rng.randrange(len(palette))]
        parts.append(dict(o=o, d=d, start=start, v=rng.uniform(0.45, 1.0),
                          size=rng.uniform(0.026, 0.05) if not is_chip else rng.uniform(0.045, 0.075),
                          life=rng.uniform(0.75, 1.15), col=col, chip=is_chip,
                          rot=Vector((rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-6, 6))),
                          delay=rng.uniform(0.0, 0.12), k=k))

    flash_me = bpy.data.meshes.new("flash_plane")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
    bm.to_mesh(flash_me)
    bm.free()
    flash_me.materials.append(flash_material())
    flash = link(bpy.data.objects.new("flash", flash_me))
    flash.rotation_euler = (math.radians(90), 0, 0)
    flash.location = (0, -0.4, 0)
    flash.visible_glossy = False
    flash.visible_diffuse = False

    # кільце світла: тонкий тор у площині кадру, розходиться і згасає
    ring_me = bpy.data.meshes.new("ring_mesh")
    bm = bmesh.new()
    prof = []
    for j in range(10):
        a = 2 * math.pi * j / 10
        prof.append(bm.verts.new((1.0 + 0.022 * math.cos(a), 0.0, 0.022 * math.sin(a))))
    pe = [bm.edges.new((prof[j], prof[(j + 1) % 10])) for j in range(10)]
    bmesh.ops.spin(bm, geom=prof + pe, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=96, use_merge=True)
    bm.to_mesh(ring_me)
    bm.free()
    for poly in ring_me.polygons:
        poly.use_smooth = True
    ring_me.materials.append(emit_material("ring", 1.5))
    ring = link(bpy.data.objects.new("ring", ring_me))
    ring.rotation_euler = (math.radians(90), 0, 0)
    ring.location = (0, -0.3, 0)
    ring_amp = [0, 0.45, 1.0, 0.8, 0.52, 0.3, 0.15, 0.06, 0.02, 0, 0, 0, 0, 0]
    ring_size = [0.9, 0.96, 1.02, 1.1, 1.17, 1.23, 1.28, 1.32, 1.35, 1.38, 1.4, 1.42, 1.43, 1.44]
    # монета: кадр 0 ціла, 1-2 розжарюється, 3-4 тане, далі лише іскри
    coin_emit = [0.0, 0.12, 0.3, 0.3, 0.22, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    coin_alpha = [1.0, 1.0, 0.92, 0.55, 0.18, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    coin_scale = [1.0, 1.04, 1.07, 0.95, 0.8, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    flash_amp = [0.0, 0.16, 0.30, 0.26, 0.18, 0.10, 0.05, 0.02, 0, 0, 0, 0, 0, 0]
    flash_size = [0.6, 0.95, 1.2, 1.35, 1.42, 1.46, 1.48, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5]
    for i in range(14):
        for m in COIN_MATS:
            b = m.node_tree.nodes["BSDF"]
            b.inputs["Emission Strength"].default_value = coin_emit[i]
            b.inputs["Alpha"].default_value = coin_alpha[i]
        rig_spin.scale = (coin_scale[i],) * 3
        for o in COIN_PARTS:
            o.hide_render = coin_alpha[i] <= 0.0
        flash.hide_render = flash_amp[i] <= 0.0
        flash.color = (1.0, 0.68, 0.28, flash_amp[i])
        flash.scale = (flash_size[i],) * 3
        ring.hide_render = ring_amp[i] <= 0.0
        ring.color = (1.0, 0.60, 0.16, ring_amp[i])
        ring.scale = (ring_size[i], ring_size[i], 1.0)

        for p in parts:
            o = p["o"]
            tt = (i - 1) / 12.0 - p["delay"]      # іскри стартують з кадру 1
            if tt <= 0:
                o.hide_render = True
                continue
            life = tt / p["life"]
            ease = 1 - (1 - min(life, 1.0)) ** 2.6     # сповільнення
            pos = p["start"] + p["d"] * p["v"] * ease * 0.62
            fade = max(0.0, 1.0 - life) ** 1.3
            # останні кадри: ледь помітний залишок, щоб кадр не був порожнім
            if i >= 12:
                fade = max(fade, 0.06 if p["k"] % 4 == 0 else 0.0)
            o.hide_render = fade <= 0.0
            o.location = pos
            speed = (1 - min(life, 1.0)) ** 1.6
            if p["chip"]:
                o.scale = (p["size"] * (0.35 + 0.65 * fade),) * 3
                o.rotation_euler = tuple(p["rot"] * tt)
            else:
                # витягуємо іскру вздовж руху (без motion blur)
                stretch = 1.0 + 5.0 * speed
                q = p["d"].to_track_quat("X", "Z")
                o.rotation_euler = q.to_euler()
                s = p["size"] * (0.4 + 0.6 * fade)
                o.scale = (s * stretch, s, s)
                o.color = (p["col"][0], p["col"][1], p["col"][2], min(1.0, 0.25 + fade))
        render(os.path.join(OUT, "burst", "f%02d.png" % i), 400)
    timings["burst"] = time.time() - t

print("COIN timings", {k: round(v, 1) for k, v in timings.items()}, "total", round(time.time() - T0, 1), "s")
print("COIN out", OUT)
