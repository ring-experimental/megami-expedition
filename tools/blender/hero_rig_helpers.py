"""Extra helpers for rigging the hero characters (kai, lyra) — see RIG_SPEC.md.

common.py / char_helpers.py / rig_helpers.py are shared and must not be edited; this module adds:

geometry (while building Parts)
    resample(sections, zs)       re-sample a loft profile [(z, w, d[, cx, cy]), ...] at new heights:
                                 same silhouette, but extra edge loops where joints / chains bend
    loft_sector(p, mat, sections, n, k0, k1, loc)
                                 faces k0..k1 of an n-gon char_helpers.loft (same vertices, open
                                 surface) — cuts a flared skirt into panels that match at rest
    build_at(p, parent, pivot, parent_pivot)
                                 geometry authored in a shared frame -> part pivoted at `pivot`
    joint_cap(name, parent, mat, profile, z)
                                 round elbow/knee filler: a closed cylinder along the hinge axis,
                                 centred on the joint, rigid on its own bone (see the function)

weights (after rig_helpers.rig_from_parts, which bakes the skin in world space)
    read_weights / write_weights per-vertex {bone: w} access on the skinned mesh
    add_influence(skin, bones, other, k_fn)
                                 position-dependent extra influence (e.g. coat tails following the
                                 thighs more toward the hem). A pure function of the vertex position,
                                 so coincident seam vertices of split parts stay identical (no cracks).
    skirt_weights(skin, ...)     continuous skirt weighting: angular blend between the panel bones,
                                 vertical blend down each chain, side/height-dependent thigh influence
    limit_influences(skin, 4)    three.js skins use 4 joints per vertex: enforce it here so the
                                 Blender pose previews match the game
"""
import math

import bmesh
from mathutils import Vector

from common import Part


def ss(e0, e1, x):
    """smoothstep from e0 (0) to e1 (1); e1 < e0 allowed (descending)."""
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------

def _sec(s):
    z, w, d = s[0], s[1], s[2]
    cx, cy = (s[3], s[4]) if len(s) >= 5 else (0.0, 0.0)
    return (z, w, d, cx, cy)


def joint_cap(name, parent, mat, profile, z, seg=10, pad=0.002, inset=0.004):
    """Round filler for a hinge joint (elbow / knee).

    A closed cylinder along the hinge axis (local X) centred on the joint = `parent`'s pivot, sized
    from the limb's loft `profile` at height `z` (radius = half the limb depth + pad, length = limb
    width - 2*inset so it never pokes out of the sides). Bending rotates the cylinder about its own
    axis, so its silhouette never changes: the outer corner of a bent elbow/knee stays round instead
    of the flat bevel that linear-blend skinning produces.
    It becomes its own bone (child of `parent`) with RIGID weights — keep it out of `smooth`, or the
    blend would flatten it again.
    """
    _, w, d, cx, cy = resample(profile, [z])[0]
    p = Part(name)
    p.cyl(mat, r=d / 2 + pad, h=w - 2 * inset, seg=seg, loc=(cx, cy, 0), rot=(0, 90, 0))
    return p.build(parent, loc=(0, 0, 0))


def resample(sections, zs):
    """Piecewise-linear re-sampling of a loft profile at heights zs (in the given order)."""
    S = sorted((_sec(s) for s in sections), key=lambda s: s[0])
    out = []
    for z in zs:
        a, b = S[0], S[1]
        for i in range(len(S) - 1):
            if z >= S[i][0]:
                a, b = S[i], S[i + 1]
        f = (z - a[0]) / (b[0] - a[0])
        out.append(tuple([z] + [a[k] + (b[k] - a[k]) * f for k in range(1, 5)]))
    return out


def loft_sector(p, mat, sections, n, k0, k1, loc=(0, 0, 0), phase=None):
    """Open surface made of the faces between ring vertices k0..k1 (k1 > k0, wraps mod n) of an
    n-gon loft through `sections` (bottom -> top). Vertices are exactly those of
    char_helpers.loft(shape=n), so sectors built side by side reproduce the original surface."""
    phase = math.pi / n if phase is None else phase
    off = Vector(loc)
    bm = p.bm
    rows, allv = [], []
    for s in sections:
        z, w, d, cx, cy = _sec(s)
        row = []
        for k in range(k0, k1 + 1):
            a = 2 * math.pi * (k % n) / n + phase
            row.append(bm.verts.new(off + Vector((cx + w / 2 * math.cos(a), cy + d / 2 * math.sin(a), z))))
        rows.append(row)
        allv += row
    for i in range(len(rows) - 1):
        A, B = rows[i], rows[i + 1]
        for j in range(len(A) - 1):
            bm.faces.new((A[j], A[j + 1], B[j + 1], B[j]))
    return p._assign(allv, mat)


def strip(p, mat, left, right):
    """Quad strip between two polylines of equal length (lists of xyz points, top -> bottom)."""
    bm = p.bm
    L = [bm.verts.new(Vector(v)) for v in left]
    R = [bm.verts.new(Vector(v)) for v in right]
    for i in range(len(L) - 1):
        bm.faces.new((L[i], R[i], R[i + 1], L[i + 1]))
    return p._assign(L + R, mat)


def build_at(p, parent, pivot, parent_pivot=(0, 0, 0)):
    """The Part's geometry was authored in a shared frame F. Move it so `pivot` (in F) becomes the
    part's origin and build it under `parent`, whose origin sits at `parent_pivot` (in F)."""
    pv = Vector(pivot)
    bmesh.ops.translate(p.bm, vec=-pv, verts=p.bm.verts[:])
    return p.build(parent, loc=tuple(pv - Vector(parent_pivot)))


# ---------------------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------------------

def read_weights(skin):
    names = {g.index: g.name for g in skin.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 1e-6} for v in skin.data.vertices]


def _clean(w, max_inf):
    items = sorted(((k, v) for k, v in w.items() if v > 1e-4), key=lambda kv: -kv[1])[:max_inf]
    s = sum(v for _, v in items) or 1.0
    return {k: v / s for k, v in items}


def write_weights(skin, weights, indices=None, max_inf=4):
    vgs = {g.name: g for g in skin.vertex_groups}
    old = read_weights(skin)
    for i in (range(len(weights)) if indices is None else indices):
        w = _clean(weights[i], max_inf)
        for name in old[i]:
            if name not in w:
                vgs[name].remove([i])
        for name, val in w.items():
            if name not in vgs:
                vgs[name] = skin.vertex_groups.new(name=name)
            vgs[name].add([i], val, "REPLACE")


def limit_influences(skin, max_inf=4):
    W = read_weights(skin)
    idx = [i for i, w in enumerate(W) if len(w) > max_inf]
    if idx:
        write_weights(skin, W, idx, max_inf)
    return len(idx)


def add_influence(skin, bones, other, k_fn):
    """For every vertex weighted to any of `bones` add influence k_fn(world_co) * (its weight on
    `bones`) of bone `other` (others scaled down). Returns number of changed vertices."""
    bones = set(bones)
    W = read_weights(skin)
    changed = []
    for v in skin.data.vertices:
        w = W[v.index]
        s = sum(val for b, val in w.items() if b in bones)
        if s <= 0:
            continue
        k = max(0.0, min(0.95, k_fn(v.co) * s))
        if k <= 1e-4:
            continue
        nw = {b: val * (1 - k) for b, val in w.items()}
        nw[other] = nw.get(other, 0.0) + k
        W[v.index] = nw
        changed.append(v.index)
    write_weights(skin, W, changed)
    return len(changed)


SKIRT_DIRS = {  # direction (deg, atan2(y, x) around the hips; -Y = front) -> chain top -> bottom
    "F": (270.0, ["skirt_F_1", "skirt_F_2"]),
    "B": (90.0, ["skirt_B_1", "skirt_B_2"]),
    "L": (0.0, ["skirt_L_1"]),
    "R": (180.0, ["skirt_R_1"]),
}


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def skirt_weights(skin, center, parent="hips", dirs=None, prefix="skirt_",
                  z_attach=0.02, attach_fade=0.10, z_split=-0.20, split_r=0.08,
                  legs=(("leg_L", 1), ("leg_R", -1)), side_x=(-0.06, 0.12),
                  k_front=0.5, k_back=0.3, leg_z=(-0.02, -0.38), sharp=2.0,
                  surface=None, n=10):
    """Rewrite the weights of every vertex whose strongest bone starts with `prefix`, as a smooth
    function of its position q = co - center (hips pivot, world):
      * angular blend between the panel chains (cos^sharp partition around the hips),
      * vertical: parent (belt) above z_attach, then chain bone _1, blending into _2 around z_split,
      * thigh influence growing toward the hem (leg_z), on the leg's side (side_x on s*x),
        stronger in front (k_front) than behind (k_back).
    Every split part shares the same weight field, so the panels deform as one continuous skirt.

    surface: optional loft profile [(z, w, d[, cx, cy])] (hips frame) of the main skirt n-gon. Each
    vertex is then projected radially onto that surface and gets the weights of the surface point,
    linearly interpolated between the two ring vertices of the face it lands on — exactly how the
    main surface itself deforms. Overlays (front panel, edging, underskirt, hem trim) thus move
    with the skirt behind them instead of cutting through it."""
    dirs = dirs or SKIRT_DIRS

    def field(x, y, z):
        th = math.atan2(y, x)
        a = {d: max(0.0, math.cos(th - math.radians(ang))) ** sharp for d, (ang, _) in dirs.items()}
        sa = sum(a.values()) or 1.0
        c1 = ss(z_attach, z_attach - attach_fade, z)
        c2 = ss(z_split + split_r, z_split - split_r, z)
        w = {parent: 1.0 - c1}
        for d, (_, bones) in dirs.items():
            if a[d] <= 0:
                continue
            levels = [1.0] if len(bones) == 1 else [1.0 - c2, c2]
            for b, f in zip(bones, levels):
                w[b] = w.get(b, 0.0) + a[d] / sa * c1 * f
        h = ss(leg_z[0], leg_z[1], z)
        K = k_back + (k_front - k_back) * ss(0.12, -0.12, y)
        ks = {leg: K * h * ss(side_x[0], side_x[1], s * x) for leg, s in legs}
        tot = sum(ks.values())
        w = {b: val * (1.0 - tot) for b, val in w.items()}
        for leg, k in ks.items():
            w[leg] = w.get(leg, 0.0) + k
        return w

    def on_surface(q):
        z, w_, d_, cx, cy = resample(surface, [q.z])[0]
        ring = [(cx + w_ / 2 * math.cos(2 * math.pi * k / n + math.pi / n),
                 cy + d_ / 2 * math.sin(2 * math.pi * k / n + math.pi / n)) for k in range(n)]
        dvec = (q.x - cx, q.y - cy)
        for k in range(n):
            p0, p1 = ring[k], ring[(k + 1) % n]
            e = (p1[0] - p0[0], p1[1] - p0[1])
            r = (p0[0] - cx, p0[1] - cy)
            den = _cross(dvec, e)
            if abs(den) < 1e-12:
                continue
            u = _cross(r, dvec) / den
            t = _cross(r, e) / den
            if -1e-6 <= u <= 1 + 1e-6 and t > 0:
                u = max(0.0, min(1.0, u))
                wa, wb = field(p0[0], p0[1], z), field(p1[0], p1[1], z)
                return {b: wa.get(b, 0.0) * (1 - u) + wb.get(b, 0.0) * u for b in set(wa) | set(wb)}
        return field(q.x, q.y, q.z)

    W = read_weights(skin)
    changed = []
    for v in skin.data.vertices:
        w0 = W[v.index]
        if not w0 or not max(w0.items(), key=lambda kv: kv[1])[0].startswith(prefix):
            continue
        q = v.co - Vector(center)
        W[v.index] = on_surface(q) if surface else field(q.x, q.y, q.z)
        changed.append(v.index)
    write_weights(skin, W, changed)
    return len(changed)
