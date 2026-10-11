"""Extra rigging helpers for the armored humanoid enemies (knight, golem). See RIG_SPEC.md.

Builds on common.py / char_helpers.py / rig_helpers.py WITHOUT modifying them.

    build_at(p, parent, pivot, frame)      build a Part modelled in its parent's space with its origin
                                           (= future bone head) moved to a joint pivot
    tag_part(obj, tag)                     mark every vertex of a part (survives rig_from_parts' join)
    reweight_chain(arm, skin, tag, chain)  seam-continuous weights for a cloth panel split into a chain
    side_thigh_influence(...)              depth-graded, side-biased thigh influence for cloth panels
    pose_views(arm, rotations, views)      render several previews of one pose, then reset to rest
"""
import bmesh
import bpy
from mathutils import Vector

from common import render_preview
from rig_helpers import pose_world, reset_pose


def build_at(p, parent, pivot, frame=(0.0, 0.0, 0.0)):
    """Build Part `p` whose geometry was modelled in a frame located at `frame` (in the parent's local
    space; default: the parent's own origin), placing the object's origin at `pivot` (parent space).
    The geometry ends up exactly where it was modelled; only the pivot moves. All parts have identity
    rest rotation (ASSET_SPEC), so plain translations are enough."""
    off = Vector(frame) - Vector(pivot)
    if off.length > 0:
        bmesh.ops.translate(p.bm, vec=off, verts=p.bm.verts[:])
    return p.build(parent, loc=tuple(pivot))


def tag_part(obj, tag):
    """Put every vertex of `obj` into a helper vertex group `tag` (weight 1). The group survives the
    join in rig_from_parts, so reweight_chain can find the part's vertices in the skin afterwards."""
    g = obj.vertex_groups.new(name=tag)
    g.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    return g


def _ramp(t, r):
    """0 below -r, 1 above +r, smoothstep in between (r <= 0 -> hard step at 0)."""
    if r <= 0:
        return 1.0 if t >= 0 else 0.0
    x = max(0.0, min(1.0, (t + r) / (2.0 * r)))
    return x * x * (3.0 - 2.0 * x)


def reweight_chain(arm, skin, tag, chain, radius=0.08, anchor_radius=0.04, extra=None, remove_tag=True):
    """Recompute the skin weights of all vertices tagged `tag` — one cloth panel split into the
    consecutive bones `chain` (e.g. ["tabard_F_1", "tabard_F_2"], chain[0]'s parent is the anchor).

    Weights depend ONLY on each vertex's projection along the chain bones' axes, so vertices on both
    sides of a seam between two chain parts get identical weights and the seam never opens (the
    `smooth` falloff of rig_from_parts fades the parent side out by distance from the bone head, which
    tears wide panels at their outer corners).
      radius        : blend half-width around each joint inside the chain (m)
      anchor_radius : blend half-width around chain[0]'s head (panel <-> anchor bone)
      extra(p)      : optional callback -> {bone: weight} additional influences at world position p
                      (added on top of the chain weights, then everything is normalised)
    """
    bones = arm.data.bones
    anchor = bones[chain[0]].parent.name
    heads = [bones[n].head_local.copy() for n in chain]
    axes = [(bones[n].tail_local - bones[n].head_local).normalized() for n in chain]
    radii = [anchor_radius] + [radius] * (len(chain) - 1)
    g_tag = skin.vertex_groups[tag]
    gi = g_tag.index
    mw = skin.matrix_world
    groups = {g.name: g for g in skin.vertex_groups}

    def group(name):
        if name not in groups:
            groups[name] = skin.vertex_groups.new(name=name)
        return groups[name]

    count = 0
    for v in skin.data.vertices:
        if not any(e.group == gi and e.weight > 0.5 for e in v.groups):
            continue
        p = mw @ v.co
        f = [_ramp((p - h).dot(a), r) for h, a, r in zip(heads, axes, radii)] + [0.0]
        w = {anchor: 1.0 - f[0]}
        for i, n in enumerate(chain):
            w[n] = max(0.0, f[i] - f[i + 1])
        if extra:
            for n, k in extra(p).items():
                w[n] = w.get(n, 0.0) + k
        s = sum(w.values())
        old = [skin.vertex_groups[e.group] for e in v.groups if e.group != gi]
        for g in old:
            g.remove([v.index])
        for n, val in w.items():
            if val / s > 1e-4:
                group(n).add([v.index], val / s, "REPLACE")
        count += 1
    if remove_tag:
        skin.vertex_groups.remove(g_tag)
    print(f"[rig] reweighted {count} verts of '{tag}' along {chain}")
    return count


def side_thigh_influence(z_top, z_bot, k_top, k_bot, half_width, bias=0.6, legs=("leg_L", "leg_R")):
    """Factory for reweight_chain(extra=...): thigh influence for a cloth panel hanging over both legs.
    The total thigh influence grows linearly from k_top (at world z_top) to k_bot (at z_bot); it is
    split between the legs by the vertex's side: at x = +half_width (model's left) leg_L gets
    (0.5 + bias/2) of it, leg_R (0.5 - bias/2); mirrored on the right; 50/50 on the centre line."""
    lg_L, lg_R = legs

    def extra(p):
        t = max(0.0, min(1.0, (z_top - p.z) / (z_top - z_bot)))
        k = k_top + (k_bot - k_top) * t
        u = max(-1.0, min(1.0, p.x / half_width))
        return {lg_L: k * (0.5 + 0.5 * bias * u), lg_R: k * (0.5 - 0.5 * bias * u)}
    return extra


def pose_views(arm, rotations, views):
    """Pose `arm` (rig_helpers.pose_world rotations), render every (filename, azimuth, elevation) in
    `views` with common.render_preview, then reset to the rest pose."""
    pose_world(arm, rotations)
    out = [render_preview(fn, azimuth=az, elevation=el) for (fn, az, el) in views]
    reset_pose(arm)
    return out
