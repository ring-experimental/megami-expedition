"""Auto-rigging for the part-built models (Blender 5.x). See RIG_SPEC.md.

The model scripts keep building rigid Parts with pivots at the joints (common.Part / char_helpers).
`rig_from_parts(root)` then converts that object hierarchy into:

    root (ARMATURE object)            ← replaces the old 'root' empty
      bones = every MESH part, same name, head at the part's pivot, same parent chain
      <name>_skin (one joined MESH)   ← all bone parts merged, skinned with vertex groups
      rigid attachments (weapon, shield, key, steam_point, ...) bone-parented, NOT skinned

so the game keeps addressing joints by the same names ('arm_L', 'torso', ...), while gaining real
skinning (elbows, knees, cloth chains) and far fewer draw calls.

Typical use at the end of a model script, before export:

    arm = rig_from_parts(root, rigid={"weapon", "steam_point"},
                         smooth={"forearm_L": 0.06, "shin_L": 0.07, "coat_L_2": 0.08},
                         influence={"skirt_F_1": [("leg_L", 0.25), ("leg_R", 0.25)]},
                         skin_name="kai_skin")
    export_glb("kai")
    pose_preview(arm, "kai_pose", HUMANOID_TEST_POSE)   # check deformation, then pose is reset
"""
import math

import bpy
from mathutils import Matrix, Vector

from common import render_preview


def _walk(obj):
    for c in obj.children:
        yield c
        yield from _walk(c)


def _ss(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0))) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)


class _B:
    def __init__(self, obj, parent):
        self.obj = obj
        self.name = obj.name
        self.parent = parent      # _B or None
        self.children = []
        self.head = obj.matrix_world.translation.copy()
        self.tail = None
        vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
        self.centroid = sum(vs, Vector()) / len(vs) if vs else self.head.copy()

    @property
    def axis(self):
        d = self.tail - self.head
        return d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))


def rig_from_parts(root, rigid=(), smooth=None, influence=None, tails=None, skin_name=None, min_len=0.05):
    """Convert the Part hierarchy under `root` into an armature + one skinned mesh.

    root      : the top-level 'root' empty of the model.
    rigid     : names of objects that must stay separate rigid objects (weapon, shield, key, ...).
                EMPTY objects are always kept rigid (markers like steam_point / staff_tip).
                Everything below a rigid object stays attached to it.
    smooth    : {bone: radius_m} soft-blend this bone with its parent around the joint
                (vertices of both parts within `radius` of the joint). Use for elbows, knees, cloth.
    influence : {bone: [(other_bone, weight), ...]} extra constant weights for ALL vertices of that
                part (normalized afterwards), e.g. skirt panels partly following the thighs.
    tails     : {bone: (x, y, z)} explicit world-space tail positions (rarely needed).
    Returns the armature object (named 'root').
    """
    smooth = dict(smooth or {})
    influence = dict(influence or {})
    tails = dict(tails or {})
    rigid = set(rigid)
    vl = bpy.context.view_layer
    vl.update()

    # ---- classify -----------------------------------------------------------------
    bones, by_name, rigid_objs = [], {}, []

    def visit(obj, parent_bone):
        for c in obj.children:
            if c.type == "MESH" and c.name not in rigid:
                b = _B(c, parent_bone)
                if parent_bone:
                    parent_bone.children.append(b)
                bones.append(b)
                by_name[b.name] = b
                visit(c, b)
            else:
                rigid_objs.append((c, parent_bone))   # subtree stays attached to c
    visit(root, None)
    if not bones:
        raise RuntimeError("rig_from_parts: no mesh parts found under root")
    for n in list(smooth) + list(influence):
        if n not in by_name:
            raise RuntimeError(f"rig_from_parts: unknown bone '{n}' in smooth/influence")

    # ---- tails ------------------------------------------------------------------------
    for b in bones:
        if b.name in tails:
            b.tail = Vector(tails[b.name])
        elif len(b.children) == 1 and (b.children[0].head - b.head).length >= min_len:
            b.tail = b.children[0].head.copy()
        else:
            d = b.centroid - b.head
            if d.length < 1e-4:
                d = Vector((0, 0, 1))
            b.tail = b.head + d.normalized() * max(min_len, d.length * 1.6)
        if (b.tail - b.head).length < min_len:
            b.tail = b.head + b.axis * min_len

    # ---- armature ---------------------------------------------------------------------
    root.name = "__root_tmp"
    arm_data = bpy.data.armatures.new("root_armature")
    arm = bpy.data.objects.new("root", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    for b in bones:
        e = eb.new(b.name)
        e.head, e.tail = b.head, b.tail
        e.use_deform = True
    for b in bones:
        if b.parent:
            eb[b.name].parent = eb[b.parent.name]
            eb[b.name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    vl.update()

    # ---- rigid attachments → bone parented (keep world transform) ----------------------
    saved = [(o, o.matrix_world.copy(), pb) for (o, pb) in rigid_objs]
    for o, mw, pb in saved:
        o.parent = arm
        if pb:
            o.parent_type = "BONE"
            o.parent_bone = pb.name
        else:
            o.parent_type = "OBJECT"
        o.matrix_parent_inverse = Matrix.Identity(4)
    vl.update()
    for o, mw, pb in saved:
        o.matrix_world = mw
    vl.update()

    # ---- bake part transforms into vertices --------------------------------------------
    world = {b.name: b.obj.matrix_world.copy() for b in bones}
    for b in bones:
        b.obj.parent = None
    for b in bones:
        b.obj.matrix_world = Matrix.Identity(4)
        b.obj.data.transform(world[b.name])
    vl.update()

    # ---- weights --------------------------------------------------------------------------
    for b in bones:
        o = b.obj
        groups = {}

        def group(name):
            if name not in groups:
                groups[name] = o.vertex_groups.get(name) or o.vertex_groups.new(name=name)
            return groups[name]

        for v in o.data.vertices:
            p = v.co
            w = {b.name: 1.0}
            # child side of this bone's own joint
            if b.name in smooth and b.parent:
                r = smooth[b.name]
                t = (p - b.head).dot(b.axis)
                if t < r:
                    wc = 0.5 + 0.5 * max(-1.0, min(1.0, t / r))
                    w = {b.name: wc, b.parent.name: 1.0 - wc}
            # parent side: vertices of this part near a smoothed child joint
            for c in b.children:
                if c.name not in smooth:
                    continue
                r = smooth[c.name]
                d3 = (p - c.head).length
                if d3 > r * 1.6:
                    continue
                t = (p - c.head).dot(c.axis)
                if t <= -r:
                    continue
                wc = (0.5 + 0.5 * max(-1.0, min(1.0, t / r))) * (1.0 - _ss(r, r * 1.6, d3))
                own = w.get(b.name, 0.0)
                w[b.name] = own * (1.0 - wc)
                w[c.name] = w.get(c.name, 0.0) + own * wc
            # constant extra influences
            for other, k in influence.get(b.name, []):
                w[other] = w.get(other, 0.0) + k
            s = sum(w.values())
            for name, val in w.items():
                if val > 1e-4:
                    group(name).add([v.index], val / s, "REPLACE")

    # ---- join into one skinned mesh ----------------------------------------------------
    meshes = [b.obj for b in bones]
    for o in vl.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    active = meshes[0]
    vl.objects.active = active
    with bpy.context.temp_override(active_object=active, object=active,
                                   selected_objects=meshes, selected_editable_objects=meshes):
        bpy.ops.object.join()
    skin = active
    skin.name = skin_name or "skin"
    skin.data.name = skin.name
    skin.parent = arm
    skin.matrix_world = Matrix.Identity(4)
    mod = skin.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    # ---- cleanup old root ------------------------------------------------------------------
    tmp = bpy.data.objects.get("__root_tmp")
    if tmp:
        for c in list(tmp.children):
            mw = c.matrix_world.copy()
            c.parent = arm
            c.matrix_world = mw
        bpy.data.objects.remove(tmp)
    vl.update()
    print(f"[rig] {len(bones)} bones, {len(saved)} rigid attachments, skin '{skin.name}' "
          f"({len(skin.data.vertices)} verts, {len(skin.data.materials)} materials)")
    return arm


# ---------------------------------------------------------------------------------------
# Posing (for deformation previews only — always reset before export)
# ---------------------------------------------------------------------------------------
_AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def pose_world(arm, rotations):
    """rotations: {bone: [(axis 'X'|'Y'|'Z', degrees), ...]} rotations about WORLD axes through the
    bone's head, applied parents-first. Blender world: -Y is the model's front, +Z up, model's left +X.
    e.g. raise arm forward: {"arm_L": [("X", -80)]}; bend knee: {"shin_L": [("X", 60)]}."""
    reset_pose(arm)
    order = []

    def visit(bone):
        order.append(bone.name)
        for c in bone.children:
            visit(c)
    for b in arm.data.bones:
        if b.parent is None:
            visit(b)
    for name in order:
        if name not in rotations:
            continue
        pb = arm.pose.bones[name]
        m = pb.matrix.copy()
        head = m.translation.copy()
        R = Matrix.Identity(4)
        for axis, deg in rotations[name]:
            R = Matrix.Rotation(math.radians(deg), 4, _AXES[axis]) @ R
        pb.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ m
        bpy.context.view_layer.update()


def pose_preview(arm, filename, rotations, **kw):
    """Render a deformation test preview in the given pose, then reset to rest pose."""
    pose_world(arm, rotations)
    out = render_preview(filename, **kw)
    reset_pose(arm)
    return out


# A pose that exercises shoulders, elbows, hips, knees and cloth/chain bones of a humanoid.
HUMANOID_TEST_POSE = {
    "torso": [("Z", 15)],
    "head": [("Z", -20)],
    "arm_L": [("X", -70), ("Y", -25)],
    "forearm_L": [("X", -70)],
    "arm_R": [("X", 40)],
    "forearm_R": [("X", -60)],
    "leg_L": [("X", -45)],
    "shin_L": [("X", 70)],
    "leg_R": [("X", 20)],
    "shin_R": [("X", 25)],
}
