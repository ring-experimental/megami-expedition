"""Shared helpers for building stylized models in Blender (5.x) and exporting GLB.

Usage (headless):
    blender -b --factory-startup -P tools/blender/<model>.py

Conventions (see ASSET_SPEC.md):
    * 1 unit = 1 m, Z up in Blender (exported as Y up).
    * Models FACE -Y in Blender (=> +Z in three.js). Character's right side is -X.
    * Animated parts are separate objects whose origin sits on the joint/pivot.
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Matrix, Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(PROJECT_ROOT, "public", "models")
PREVIEW_DIR = os.path.join(HERE, "previews")

# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
# Colors are sRGB hex; converted to linear for Blender/glTF.
# Material name prefixes are meaningful to the game code:
#   glow_*   -> emissive, gets bloom
#   jelly_*  -> translucent
PALETTE = {
    "brass":        dict(hex="#c9a14a", metallic=0.9, roughness=0.35),
    "brass_dark":   dict(hex="#8a6a2c", metallic=0.9, roughness=0.45),
    "copper":       dict(hex="#b8673a", metallic=0.9, roughness=0.4),
    "iron":         dict(hex="#3a3c42", metallic=0.8, roughness=0.55),
    "steel":        dict(hex="#9aa2ad", metallic=0.85, roughness=0.3),
    "gunmetal":     dict(hex="#2a2d33", metallic=0.7, roughness=0.5),
    "leather":      dict(hex="#6b3f22", metallic=0.0, roughness=0.75),
    "leather_dark": dict(hex="#3b2416", metallic=0.0, roughness=0.75),
    "wood":         dict(hex="#7a5230", metallic=0.0, roughness=0.85),
    "wood_dark":    dict(hex="#4a3020", metallic=0.0, roughness=0.85),
    "stone":        dict(hex="#8d877c", metallic=0.0, roughness=0.95),
    "stone_dark":   dict(hex="#5d5850", metallic=0.0, roughness=0.95),
    "cloth_red":    dict(hex="#a8302a", metallic=0.0, roughness=0.85),
    "cloth_navy":   dict(hex="#26324f", metallic=0.0, roughness=0.85),
    "cloth_cream":  dict(hex="#e3d6b4", metallic=0.0, roughness=0.85),
    "cloth_purple": dict(hex="#5b3a7a", metallic=0.0, roughness=0.85),
    "cloth_green":  dict(hex="#3f5a3a", metallic=0.0, roughness=0.85),
    "skin":         dict(hex="#f1c9a5", metallic=0.0, roughness=0.6),
    "hair_brown":   dict(hex="#5a3418", metallic=0.0, roughness=0.7),
    "hair_silver":  dict(hex="#dfe3ee", metallic=0.0, roughness=0.6),
    "leaf":         dict(hex="#4f7a3a", metallic=0.0, roughness=0.9),
    "leaf_teal":    dict(hex="#3f8a7e", metallic=0.0, roughness=0.9),
    "leaf_autumn":  dict(hex="#c4702a", metallic=0.0, roughness=0.9),
    "grass":        dict(hex="#5e8a3e", metallic=0.0, roughness=0.95),
    "black":        dict(hex="#111111", metallic=0.0, roughness=0.5),
    "white":        dict(hex="#f4f1ea", metallic=0.0, roughness=0.5),
    "glass":        dict(hex="#bfe6f0", metallic=0.1, roughness=0.05),
    "glow_cyan":    dict(hex="#5ff3ff", emission="#5ff3ff", strength=6.0),
    "glow_violet":  dict(hex="#b77bff", emission="#b77bff", strength=6.0),
    "glow_amber":   dict(hex="#ffb347", emission="#ffb347", strength=6.0),
    "glow_red":     dict(hex="#ff4a3a", emission="#ff4a3a", strength=6.0),
    "glow_green":   dict(hex="#7dff9a", emission="#7dff9a", strength=6.0),
    "glow_white":   dict(hex="#fff4dc", emission="#fff4dc", strength=5.0),
    "jelly_teal":   dict(hex="#3fd1b8", metallic=0.0, roughness=0.15, alpha=0.7),
    "jelly_pink":   dict(hex="#ff7fb8", metallic=0.0, roughness=0.15, alpha=0.7),
}

_MATS = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def get_mat(name, **override):
    """Get (or create) a material by palette name. Unknown names need hex=... override."""
    if name in _MATS:
        return _MATS[name]
    spec = dict(PALETTE.get(name, {}))
    spec.update(override)
    if "hex" not in spec:
        raise ValueError(f"Unknown material '{name}' (add it to PALETTE or pass hex=)")
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True  # deprecated in 5.x but harmless
    except Exception:
        pass
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    col = hex_to_linear(spec["hex"])
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    bsdf.inputs["Roughness"].default_value = spec.get("roughness", 0.6)
    if "emission" in spec:
        bsdf.inputs["Emission Color"].default_value = (*hex_to_linear(spec["emission"]), 1.0)
        bsdf.inputs["Emission Strength"].default_value = spec.get("strength", 4.0)
    if "alpha" in spec:
        bsdf.inputs["Alpha"].default_value = spec["alpha"]
    m.diffuse_color = (*col, spec.get("alpha", 1.0))  # viewport / workbench color
    _MATS[name] = m
    return m


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def empty(name, parent=None, loc=(0, 0, 0), size=0.1):
    """Pivot / marker node (exported as a plain glTF node)."""
    o = bpy.data.objects.new(name, None)
    o.empty_display_size = size
    _link(o)
    o.parent = parent
    o.location = loc
    return o


def _rad(rot):
    return Euler(tuple(math.radians(a) for a in rot), "XYZ")


def _mtx(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    return Matrix.LocRotScale(Vector(loc), _rad(rot), Vector(scale))


# ---------------------------------------------------------------------------
# Part builder: accumulate primitives into one flat-shaded mesh object
# ---------------------------------------------------------------------------

class Part:
    """Accumulates primitives (in the part's LOCAL space, i.e. relative to its pivot)
    into a single mesh. Call .build(parent, loc) to create the object.

    rot is in degrees (XYZ euler). scale may be a number or 3-tuple.
    """

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mat_names = []

    # -- internals --------------------------------------------------------
    def _mi(self, mat):
        if mat not in self.mat_names:
            self.mat_names.append(mat)
        return self.mat_names.index(mat)

    def _assign(self, verts, mat):
        mi = self._mi(mat)
        for f in {f for v in verts for f in v.link_faces}:
            f.material_index = mi
            f.smooth = False
        return self

    # -- primitives -------------------------------------------------------
    def box(self, mat, size=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0)):
        if isinstance(size, (int, float)):
            size = (size, size, size)
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=_mtx(loc, rot, size))
        return self._assign(r["verts"], mat)

    def cyl(self, mat, r=0.5, h=1.0, r2=None, seg=8, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        """Cylinder / truncated cone along local Z, centered on loc."""
        r2 = r if r2 is None else r2
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                    radius1=r, radius2=r2, depth=h,
                                    matrix=_mtx(loc, rot, scale))
        return self._assign(res["verts"], mat)

    def cone(self, mat, r=0.5, h=1.0, seg=8, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        return self.cyl(mat, r=r, h=h, r2=0.0, seg=seg, loc=loc, rot=rot, scale=scale)

    def sphere(self, mat, r=0.5, seg=8, rings=6, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=rings, radius=r,
                                        matrix=_mtx(loc, rot, scale))
        return self._assign(res["verts"], mat)

    def ico(self, mat, r=0.5, subdiv=1, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=r,
                                         matrix=_mtx(loc, rot, scale))
        return self._assign(res["verts"], mat)

    def torus(self, mat, R=0.5, r=0.08, seg=16, seg2=6, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1),
              phase=0.0):
        """Torus lying in local XY plane (axis = local Z). phase rotates the cross-section (radians)."""
        M = _mtx(loc, rot, scale)
        rings = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ring = []
            for j in range(seg2):
                b = 2 * math.pi * j / seg2 + phase
                d = R + r * math.cos(b)
                p = Vector((d * math.cos(a), d * math.sin(a), r * math.sin(b)))
                ring.append(self.bm.verts.new(M @ p))
            rings.append(ring)
        verts = [v for ring in rings for v in ring]
        for i in range(seg):
            a, b = rings[i], rings[(i + 1) % seg]
            for j in range(seg2):
                k = (j + 1) % seg2
                self.bm.faces.new((a[j], b[j], b[k], a[k]))
        return self._assign(verts, mat)

    def gear(self, mat, r=0.5, thickness=0.1, teeth=10, tooth=0.12, hole=0.0,
             loc=(0, 0, 0), rot=(0, 0, 0), seg=None):
        """Gear disc in local XY plane (axis = local Z). hole>0 adds a hub ring instead of a solid disc."""
        seg = seg or max(teeth * 2, 12)
        M = _mtx(loc, rot)
        if hole > 0:
            half = (r - hole) / 2
            self.torus(mat, R=(r + hole) / 2, r=half / math.cos(math.pi / 4), seg=seg, seg2=4,
                       loc=loc, rot=rot, scale=(1, 1, thickness / (2 * half)), phase=math.pi / 4)
        else:
            res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                        radius1=r, radius2=r, depth=thickness, matrix=M)
            self._assign(res["verts"], mat)
        for i in range(teeth):
            a = 2 * math.pi * i / teeth
            tl = _mtx((math.cos(a) * (r + tooth * 0.45), math.sin(a) * (r + tooth * 0.45), 0),
                      (0, 0, math.degrees(a)), (tooth, 2 * math.pi * r / teeth * 0.5, thickness))
            res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M @ tl)
            self._assign(res["verts"], mat)
        return self

    def poly(self, mat, verts, faces):
        """Raw geometry: verts = [(x,y,z)...], faces = [(i,j,k,...)...]."""
        vs = [self.bm.verts.new(v) for v in verts]
        for f in faces:
            self.bm.faces.new([vs[i] for i in f])
        return self._assign(vs, mat)

    # -- output -----------------------------------------------------------
    def build(self, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
        mesh = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mn in self.mat_names:
            mesh.materials.append(get_mat(mn))
        obj = bpy.data.objects.new(self.name, mesh)
        _link(obj)
        obj.parent = parent
        obj.location = loc
        obj.rotation_euler = _rad(rot)
        return obj


# ---------------------------------------------------------------------------
# Export / preview
# ---------------------------------------------------------------------------

def export_glb(filename):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename if filename.endswith(".glb") else filename + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        use_selection=False,
    )
    tris = 0
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    print(f"[export] {path}  (~{tris} tris)")
    return path


def render_preview(filename, size=640, azimuth=35.0, elevation=18.0):
    """Workbench render of the whole scene from a 3/4 front view -> tools/blender/previews/<filename>.png"""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for o in scene.objects:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mins = Vector(map(min, mins, w))
            maxs = Vector(map(max, maxs, w))
    center = (mins + maxs) / 2
    radius = max((maxs - mins).length / 2, 0.1)
    az, el = math.radians(azimuth), math.radians(elevation)
    dist = radius * 2.8
    # Camera in front (-Y side), rotated by azimuth toward +X
    cam_pos = center + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    cam_data = bpy.data.cameras.new("preview_cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("preview_cam", cam_data)
    _link(cam)
    cam.location = cam_pos
    direction = center - cam_pos
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = True
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.film_transparent = False
    out = os.path.join(PREVIEW_DIR, filename + ".png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    print(f"[preview] {out}")
    return out
