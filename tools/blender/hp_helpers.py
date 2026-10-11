"""Hi-poly helpers (2026-10 quality pass) — smooth shading, bevel / subdivision, vertex-colour AO,
vertex-colour aware GLB export and EEVEE previews. Builds on common.py WITHOUT modifying it.

Shading convention for the hi-poly models (game side: core/assets.ts no longer forces flatShading,
it uses the normals stored in the GLB):
    * curved surfaces are smooth-shaded, hard metal edges stay crisp via sharp edges (smooth by angle)
    * silhouettes that would read as "boxy" get a real bevel (bevel_obj) before smoothing
    * a per-corner colour attribute "Col" (ambient occlusion x optional tint) is multiplied with the
      material base colour by three.js (GLTFLoader turns on vertexColors when COLOR_0 exists)

Typical flow inside a model script (Part objects are still built with common.Part / char_helpers):

    obj = p.build(parent, loc=pivot)
    hp.bevel_obj(obj, width=0.006, segments=2)        # optional, applied immediately
    hp.subdivide_obj(obj, levels=1)                   # optional, applied immediately (organic parts)
    hp.smooth_obj(obj, angle=35)                      # per object, or hp.smooth_all() at the end
    ...
    arm = rig_from_parts(root, ...)                   # rigged models only
    hp.bake_vertex_ao(ground=True)                    # AFTER rigging/joining, right before export
    hp.export_glb_hp("cograt")
    hp.render_hp("cograt")                            # EEVEE preview with AO + materials
    hp.render_hp("cograt_back", azimuth=200)

All functions are safe in background mode (no bpy.ops context needed except export / render).
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from common import OUT_DIR, PREVIEW_DIR, get_mat, _link  # noqa: F401

AO_ATTR = "Col"
NO_AO_PREFIXES = ("glow_", "jelly_", "glass")


# ---------------------------------------------------------------------------
# Modifier helpers (applied immediately through the evaluated depsgraph)
# ---------------------------------------------------------------------------

def apply_modifiers(obj):
    """Bake obj's modifier stack into its mesh data (works headless, keeps materials)."""
    if obj.type != "MESH" or not obj.modifiers:
        return obj
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = obj.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    name = old.name
    obj.modifiers.clear()
    obj.data = new
    if old.users == 0:
        bpy.data.meshes.remove(old)
    new.name = name
    return obj


def bevel_obj(obj, width=0.008, segments=2, angle=30.0, profile=0.5, harden=True, clamp=True, apply=True,
              limit="ANGLE"):
    """Bevel edges sharper than `angle` degrees (rounded corners catch highlights).
    width in metres. segments 1 = chamfer, 2-3 = rounded. harden=True keeps flat faces flat."""
    m = obj.modifiers.new("hp_bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = limit
    if limit == "ANGLE":
        m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = clamp
    m.harden_normals = harden
    m.miter_outer = "MITER_ARC"
    if apply:
        apply_modifiers(obj)
    return obj


def subdivide_obj(obj, levels=1, catmull=True, apply=True, keep_corners=False):
    """Subdivision surface (catmull=True) or simple subdivide (catmull=False, adds density only)."""
    m = obj.modifiers.new("hp_subsurf", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    m.subdivision_type = "CATMULL_CLARK" if catmull else "SIMPLE"
    m.boundary_smooth = "PRESERVE_CORNERS" if keep_corners else "ALL"
    if apply:
        apply_modifiers(obj)
    return obj


def weighted_normals(obj, weight=50, keep_sharp=True, apply=True):
    """Weighted-normal modifier: big flat faces dominate vertex normals (clean hard-surface shading)."""
    smooth_obj(obj)
    m = obj.modifiers.new("hp_wn", "WEIGHTED_NORMAL")
    m.weight = weight
    m.keep_sharp = keep_sharp
    m.mode = "FACE_AREA"
    if apply:
        apply_modifiers(obj)
    return obj


def displace_noise(obj, strength=0.05, scale=0.6, seed=0, apply=True):
    """Organic noise displacement along normals (rocks, bark, canopy clumps). Needs some density
    (subdivide first)."""
    tex = bpy.data.textures.new(f"hp_noise_{obj.name}", "CLOUDS")
    tex.noise_scale = scale
    tex.noise_depth = 2
    m = obj.modifiers.new("hp_disp", "DISPLACE")
    m.texture = tex
    m.strength = strength
    m.mid_level = 0.5
    m.texture_coords = "OBJECT" if False else "LOCAL"
    if seed:
        # offset the sampling position to vary the pattern
        e = bpy.data.objects.new(f"hp_noise_off_{obj.name}", None)
        _link(e)
        rnd = random.Random(seed)
        e.location = (rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50))
        m.texture_coords = "OBJECT"
        m.texture_coords_object = e
    if apply:
        apply_modifiers(obj)
        if seed:
            bpy.data.objects.remove(e)
        bpy.data.textures.remove(tex)
    return obj


# ---------------------------------------------------------------------------
# Shading
# ---------------------------------------------------------------------------

def smooth_obj(obj, angle=35.0, keep_existing_sharp=True):
    """Smooth-shade every face, then mark edges sharper than `angle` degrees as sharp.
    angle >= 180 -> fully smooth. Existing sharp edges (e.g. from bevel harden) are kept."""
    if obj.type != "MESH":
        return obj
    me = obj.data
    n = len(me.polygons)
    if n == 0:
        return obj
    prev = None
    if keep_existing_sharp and "sharp_edge" in me.attributes and len(me.edges):
        prev = np.zeros(len(me.edges), dtype=bool)
        me.attributes["sharp_edge"].data.foreach_get("value", prev)
    me.polygons.foreach_set("use_smooth", [True] * n)
    if angle < 180:
        me.set_sharp_from_angle(angle=math.radians(angle))
    if prev is not None and prev.any():
        if "sharp_edge" not in me.attributes:
            me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
        cur = np.zeros(len(me.edges), dtype=bool)
        me.attributes["sharp_edge"].data.foreach_get("value", cur)
        me.attributes["sharp_edge"].data.foreach_set("value", cur | prev)
    me.update()
    return obj


def flat_obj(obj):
    """Explicitly faceted object (crystals etc.)."""
    me = obj.data
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    me.update()
    return obj


def smooth_all(angle=35.0, skip=()):
    """smooth_obj on every mesh in the scene except names in `skip` (or whose name starts with an
    entry ending in '*')."""
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        if any(o.name == s or (s.endswith("*") and o.name.startswith(s[:-1])) for s in skip):
            continue
        smooth_obj(o, angle)


def smooth_faces_by_material(obj, mats_smooth=None, mats_flat=None, angle=35.0):
    """Mixed shading inside ONE mesh: faces whose material name is in mats_flat become flat."""
    smooth_obj(obj, angle)
    if mats_flat:
        names = [m.name if m else "" for m in obj.data.materials]
        flat_idx = {i for i, nm in enumerate(names) if any(nm == f or nm.startswith(f) for f in mats_flat)}
        for p in obj.data.polygons:
            if p.material_index in flat_idx:
                p.use_smooth = False
    return obj


# ---------------------------------------------------------------------------
# Vertex colours: ambient occlusion (+ optional tint)
# ---------------------------------------------------------------------------

def _mesh_objects(objs=None):
    if objs is None:
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.startswith("_preview")]
    return [o for o in objs if o.type == "MESH" and len(o.data.polygons)]


def _world_bvh(objs, ground):
    verts, polys = [], []
    for o in objs:
        mw = o.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in o.data.vertices)
        polys.extend(tuple(base + i for i in p.vertices) for p in o.data.polygons)
    if ground is not None:
        z = ground
        base = len(verts)
        S = 500.0
        verts.extend([Vector((-S, -S, z)), Vector((S, -S, z)), Vector((S, S, z)), Vector((-S, S, z))])
        polys.append((base, base + 1, base + 2, base + 3))
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def _hemisphere(n_samples, seed=7):
    """Cosine-weighted unit hemisphere directions around +Z (fixed pattern -> deterministic)."""
    rnd = random.Random(seed)
    out = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n_samples):
        u = (i + rnd.random()) / n_samples
        r = math.sqrt(u)
        a = i * golden + rnd.random() * 0.3
        out.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - u)))))
    return out


def bake_vertex_ao(objs=None, samples=40, distance=0.6, strength=0.9, floor=0.25, ground=0.0,
                   gamma=1.0, tint=None, skip_prefixes=NO_AO_PREFIXES, occluders=None):
    """Per-vertex ambient occlusion written to the corner colour attribute 'Col' of every mesh.

    objs      : meshes to colour (default: all meshes in the scene)
    occluders : meshes used for occlusion rays (default: same as objs -> parts shadow each other)
    distance  : ray length in metres (~ size of the creases you want darkened; 0.3 small props,
                1-2 m buildings / arena)
    strength  : 0 = no darkening, 1 = full AO.  floor: minimum brightness.
    ground    : z of an infinite occluding ground plane (None for flying models / airship)
    tint(p_world, n_world) -> (r, g, b) : optional extra multiplier per vertex (gradients, dirt,
                rust at the bottom, lighter tips on leaves ...). Values ~0.5-1.2.
    Faces whose material name starts with glow_/jelly_/glass get white (no AO).
    Run AFTER rig_from_parts (it joins meshes) and before export."""
    objs = _mesh_objects(objs)
    occ = _mesh_objects(occluders) if occluders is not None else objs
    bpy.context.view_layer.update()
    bvh = _world_bvh(occ, ground)
    dirs = _hemisphere(samples)
    for o in objs:
        me = o.data
        mw = o.matrix_world
        nm = mw.to_3x3().inverted_safe().transposed()
        nv = len(me.vertices)
        vals = np.ones((nv, 3), dtype=np.float32)
        for v in me.vertices:
            p = mw @ v.co
            n = (nm @ v.normal).normalized()
            # tangent frame
            t = n.orthogonal().normalized()
            b = n.cross(t)
            origin = p + n * 0.002
            hit = 0.0
            for d in dirs:
                w = t * d.x + b * d.y + n * d.z
                loc, _, _, dist = bvh.ray_cast(origin, w, distance)
                if loc is not None:
                    hit += 1.0 - (dist / distance) ** 2 * 0.5
            occl = hit / len(dirs)
            ao = max(floor, 1.0 - strength * occl)
            if gamma != 1.0:
                ao = ao ** gamma
            c = (ao, ao, ao)
            if tint is not None:
                tr = tint(p, n)
                c = (c[0] * tr[0], c[1] * tr[1], c[2] * tr[2])
            vals[v.index] = c
        # write per corner
        skip_idx = set()
        for i, m in enumerate(me.materials):
            if m and any(m.name.startswith(s) for s in skip_prefixes):
                skip_idx.add(i)
        if AO_ATTR in me.color_attributes:
            me.color_attributes.remove(me.color_attributes[AO_ATTR])
        attr = me.color_attributes.new(AO_ATTR, "BYTE_COLOR", "CORNER")
        nl = len(me.loops)
        loop_v = np.empty(nl, dtype=np.int64)
        me.loops.foreach_get("vertex_index", loop_v)
        cols = np.ones((nl, 4), dtype=np.float32)
        cols[:, :3] = np.clip(vals[loop_v], 0.0, 1.0)
        if skip_idx:
            for p in me.polygons:
                if p.material_index in skip_idx:
                    cols[p.loop_start:p.loop_start + p.loop_total, :3] = 1.0
        # BYTE_COLOR stores sRGB; color_srgb takes linear-ish display values -> use 'color' (linear)
        attr.data.foreach_set("color", cols.ravel())
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.find(AO_ATTR)
    print(f"[ao] baked vertex AO on {len(objs)} mesh(es), {samples} samples, dist {distance} m")


def fill_vertex_color(objs=None, color=(1, 1, 1)):
    """Give meshes a plain 'Col' attribute (use for meshes you deliberately skip in bake_vertex_ao so
    every primitive in the file has COLOR_0)."""
    for o in _mesh_objects(objs):
        me = o.data
        if AO_ATTR in me.color_attributes:
            continue
        attr = me.color_attributes.new(AO_ATTR, "BYTE_COLOR", "CORNER")
        cols = np.tile(np.array([*color, 1.0], dtype=np.float32), len(me.loops))
        attr.data.foreach_set("color", cols)
        me.color_attributes.active_color = attr


# ---------------------------------------------------------------------------
# Export / stats
# ---------------------------------------------------------------------------

def scene_tris(objs=None):
    objs = _mesh_objects(objs)
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)


def obj_tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons) if obj.type == "MESH" else 0


def tree_tris(obj):
    return obj_tris(obj) + sum(tree_tris(c) for c in obj.children)


def tree_meshes(root):
    """root + all descendant MESH objects."""
    out = [root] if root.type == "MESH" else []
    for c in root.children_recursive:
        if c.type == "MESH":
            out.append(c)
    return out


def bake_tree_ao(root, **kw):
    """bake_vertex_ao restricted to one object tree (a single prop): only its own meshes colour and
    occlude each other, so neighbouring props in props.glb don't shadow it."""
    ms = tree_meshes(root)
    bpy.context.view_layer.update()
    bake_vertex_ao(objs=ms, occluders=ms, **kw)


def export_glb_hp(filename, out_dir=None):
    """Like common.export_glb but keeps the 'Col' vertex colours (COLOR_0) and smooth normals.
    out_dir defaults to public/models (pass a scratch dir for test exports)."""
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    fill_vertex_color()          # every mesh needs COLOR_0, or three.js renders it black-free but inconsistent
    path = os.path.join(out_dir, filename if filename.endswith(".glb") else filename + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        use_selection=False,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_all_vertex_colors=False,
        export_active_vertex_color_when_no_material=True,
    )
    tris = scene_tris()
    print(f"[export] {path}  (~{tris} tris)")
    return path


# ---------------------------------------------------------------------------
# EEVEE preview (materials x vertex AO, sun + sky light) — closer to the in-game look
# ---------------------------------------------------------------------------

def _wire_vcol(on):
    """Temporarily multiply every material's base colour by the 'Col' attribute (preview only)."""
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if not bsdf:
            continue
        if on:
            if nt.nodes.get("hp_vcol"):
                continue
            base = tuple(bsdf.inputs["Base Color"].default_value)
            ca = nt.nodes.new("ShaderNodeVertexColor")
            ca.name = "hp_vcol"
            ca.layer_name = AO_ATTR
            mix = nt.nodes.new("ShaderNodeMix")
            mix.name = "hp_mix"
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            mix.inputs[6].default_value = base           # A (color)
            nt.links.new(ca.outputs["Color"], mix.inputs[7])  # B (color)
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        else:
            for nm in ("hp_vcol", "hp_mix"):
                n = nt.nodes.get(nm)
                if n:
                    nt.nodes.remove(n)


def _setup_world(bg_col, sky=(0.62, 0.70, 0.82), strength=1.0):
    """World: bright sky light for lighting/reflections, plain dark backdrop for camera rays."""
    scene = bpy.context.scene
    w = bpy.data.worlds.get("_hp_world") or bpy.data.worlds.new("_hp_world")
    prev = scene.world
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    light = nt.nodes.new("ShaderNodeBackground")
    light.inputs["Color"].default_value = (*sky, 1.0)
    light.inputs["Strength"].default_value = strength
    cam = nt.nodes.new("ShaderNodeBackground")
    cam.inputs["Color"].default_value = (*bg_col, 1.0)
    cam.inputs["Strength"].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(light.outputs[0], mix.inputs[1])
    nt.links.new(cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return prev


def render_hp(filename, size=720, azimuth=35.0, elevation=18.0, dist_k=2.6, target=None, objs=None,
              sun=(50.0, 35.0), sun_strength=3.2, ground=True, bg=(0.16, 0.17, 0.2), exposure=0.0,
              lens=50):
    """EEVEE render -> tools/blender/previews/<filename>.png. Shows vertex AO, metal reflections
    (sky light), soft sun shadows and a neutral ground disc. Does NOT alter what gets exported
    (temporary nodes/objects are removed). target: (center Vector, radius) to frame manually."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    objs = _mesh_objects(objs)
    if target is None:
        mins = Vector((1e9, 1e9, 1e9))
        maxs = Vector((-1e9, -1e9, -1e9))
        for o in objs:
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                mins = Vector(map(min, mins, w))
                maxs = Vector(map(max, maxs, w))
        center = (mins + maxs) / 2
        radius = max((maxs - mins).length / 2, 0.1)
    else:
        center, radius = Vector(target[0]), target[1]
    temp = []
    _wire_vcol(True)
    prev_world = _setup_world(bg)
    # ground disc
    if ground:
        gz = min((o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box)
        me = bpy.data.meshes.new("_preview_ground")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=radius * 3.5)
        bm.to_mesh(me)
        bm.free()
        gmat = bpy.data.materials.get("_preview_ground_mat") or bpy.data.materials.new("_preview_ground_mat")
        try:
            gmat.use_nodes = True
        except Exception:
            pass
        gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.34, 0.3, 1)
        gmat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
        me.materials.append(gmat)
        g = bpy.data.objects.new("_preview_ground", me)
        _link(g)
        g.location = (center.x, center.y, min(gz, 0.0) - 0.002)
        temp.append(g)
    # sun
    ld = bpy.data.lights.new("_preview_sun", "SUN")
    ld.energy = sun_strength
    ld.angle = math.radians(3.0)
    ls = bpy.data.objects.new("_preview_sun", ld)
    _link(ls)
    ls.rotation_euler = (math.radians(sun[0]), 0.0, math.radians(sun[1]))
    temp.append(ls)
    # camera
    az, el = math.radians(azimuth), math.radians(elevation)
    dist = radius * dist_k * (50.0 / lens)
    cam_pos = center + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    cd = bpy.data.cameras.new("_preview_cam")
    cd.lens = lens
    cd.clip_end = max(1000.0, dist * 4)
    cam = bpy.data.objects.new("_preview_cam", cd)
    _link(cam)
    cam.location = cam_pos
    cam.rotation_euler = (center - cam_pos).to_track_quat("-Z", "Y").to_euler()
    temp.append(cam)
    prev_cam = scene.camera
    scene.camera = cam
    scene.render.engine = "BLENDER_EEVEE"
    try:
        scene.eevee.taa_render_samples = 32
        scene.eevee.use_shadows = True
    except Exception:
        pass
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.exposure = exposure
    except Exception:
        pass
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.film_transparent = False
    out = os.path.join(PREVIEW_DIR, filename + ".png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    # cleanup
    scene.camera = prev_cam
    scene.world = prev_world
    for o in temp:
        data = o.data
        bpy.data.objects.remove(o)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
    _wire_vcol(False)
    print(f"[preview] {out}")
    return out


def render_views(name, views=(("", 35, 18), ("_front", 0, 8), ("_side", 90, 8), ("_back", 200, 20)), **kw):
    """Several render_hp angles: views = ((suffix, azimuth, elevation), ...)."""
    return [render_hp(name + s, azimuth=a, elevation=e, **kw) for (s, a, e) in views]
