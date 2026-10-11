"""Small interactables: rest-point beacon, treasure chest, crate, barrel, signpost (hi-poly).

Builders for props.glb (assembled by model_props.py). Each builder returns the prop's top-level
object named exactly as in ASSET_SPEC.md, origin at its base centre on the ground (z = 0).
Geometry helpers live in hp_small_helpers.py (Kit = Parts grouped by finish class, joined into one
mesh per prop node; plate / ring_plate / sweep_profile round only the visible edges, cheaply).

Test this group alone (no props.glb export):
    blender -b --factory-startup -P tools/blender/model_props.py -- --group=small --previews [--back] [--only=prop_x]
Test export to a scratch dir:  ... -- --group=small --out=<dir>
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import *  # noqa: E402,F401,F403
from env_helpers import Xform, mtx, box_m, set_mat  # noqa: E402,F401
from mathutils import Matrix, Vector  # noqa: E402,F401
import numpy as np  # noqa: E402
import hp_helpers as hp  # noqa: E402,F401
import hp_small_helpers as sh  # noqa: E402
from hp_small_helpers import I4, T, R, S, Kit, box, grid_box, param_box, revolve, sweep_profile, prism, \
    ring_prism, plate, ring_plate, slab, round_rect, rivet, tube, circle2d, frame  # noqa: E402


def setup_mats():
    """Group-specific materials (prefix sml_ / glow_sml_)."""
    get_mat("sml_velvet", hex="#7c1d33", roughness=0.92)                  # chest lining
    get_mat("sml_gold", hex="#ffc94a", metallic=1.0, roughness=0.22)      # coins / treasure
    get_mat("sml_paint", hex="#e6dbbf", roughness=0.8)                    # crate stencil paint
    get_mat("sml_paper", hex="#efe4c6", roughness=0.9)                    # signpost notice
    get_mat("jelly_sml_aether", hex="#62e8f0", roughness=0.08, alpha=0.55)  # rest-point pool surface
    # extra facet tones for the rest-point crystals (glow_cyan is the mid tone)
    get_mat("glow_sml_ice", hex="#d8fdff", emission="#d8fdff", strength=6.0)
    get_mat("glow_sml_deep", hex="#1479c9", emission="#1479c9", strength=2.4)


# ---------------------------------------------------------------------------
# shared bits
# ---------------------------------------------------------------------------

def _rect(w, d, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]


def _lin(a, b, n):
    return [a + (b - a) * i / n for i in range(n + 1)]


def _about(pivot, axis, deg):
    """Rotation by deg around `axis` through `pivot`."""
    return T(*pivot) @ R(axis, deg) @ T(*(-Vector(pivot)))


# local plate frame on a face: plate x -> world x, plate y -> world z, plate z -> outward (-Y = front)
def _front(x=0.0, y=0.0, z=0.0):
    return T(x, y, z) @ R("X", 90)


def _back(x=0.0, y=0.0, z=0.0):
    return T(x, y, z) @ R("Z", 180) @ R("X", 90)


# local (a, b, c) -> world (c, a, b): 2D outline in the YZ plane, extruded along X
_YZX = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def _plank(part, mat, p0, p1, up, width, thick, r=0.007, segs=3, M=I4, steps=2, grooves=()):
    """Straight plank: base face on the wall (inner side), outward = up; outer long edges rounded,
    optional V grain grooves [(s, width, depth)] along it."""
    p0, p1 = Vector(p0), Vector(p1)
    pts = [p0.lerp(p1, i / segs) for i in range(segs + 1)]
    return sweep_profile(part, mat, pts, [up] * len(pts), sh.plank_prof(width, thick, r, grooves, steps), M=M)


def _grain(rng, width, k=1):
    """k random grain grooves across a plank of `width`."""
    return [(rng.uniform(-0.28, 0.28) * width, rng.uniform(0.004, 0.006), rng.uniform(0.0012, 0.002))
            for _ in range(k)]


# minimal stroke 'font' for the painted Hangul place names (em box [0, 1]^2, y up):
# syllable -> (strokes [((x0, y0), (x1, y1)), ...], rings [(cx, cy, r), ...])
_HANGUL = {
    "si": ([((0.06, 0.06), (0.33, 0.9)), ((0.24, 0.58), (0.54, 0.06)), ((0.82, 0.02), (0.82, 0.98))], []),
    "gye": ([((0.04, 0.84), (0.42, 0.84)), ((0.42, 0.84), (0.35, 0.06)), ((0.66, 0.02), (0.66, 0.98)),
             ((0.88, 0.02), (0.88, 0.98)), ((0.52, 0.64), (0.66, 0.64)), ((0.52, 0.38), (0.66, 0.38))], []),
    "tap": ([((0.08, 0.95), (0.52, 0.95)), ((0.08, 0.76), (0.48, 0.76)), ((0.08, 0.57), (0.54, 0.57)),
             ((0.08, 0.95), (0.08, 0.57)), ((0.74, 0.98), (0.74, 0.5)), ((0.74, 0.74), (0.92, 0.74)),
             ((0.22, 0.4), (0.22, 0.02)), ((0.78, 0.4), (0.78, 0.02)), ((0.22, 0.21), (0.78, 0.21)),
             ((0.22, 0.02), (0.78, 0.02))], []),
    "ma": ([((0.06, 0.84), (0.5, 0.84)), ((0.06, 0.16), (0.5, 0.16)), ((0.06, 0.84), (0.06, 0.16)),
            ((0.5, 0.84), (0.5, 0.16)), ((0.76, 0.02), (0.76, 0.98)), ((0.76, 0.5), (0.94, 0.5))], []),
    "seok": ([((0.06, 0.5), (0.27, 0.96)), ((0.19, 0.74), (0.42, 0.5)), ((0.5, 0.74), (0.7, 0.74)),
              ((0.7, 0.98), (0.7, 0.46)), ((0.16, 0.34), (0.8, 0.34)), ((0.8, 0.34), (0.77, 0.0))], []),
    "jeung": ([((0.18, 0.95), (0.82, 0.95)), ((0.5, 0.95), (0.18, 0.64)), ((0.44, 0.84), (0.82, 0.64)),
               ((0.04, 0.47), (0.96, 0.47))], [(0.5, 0.17, 0.15)]),
    "gi": ([((0.06, 0.84), (0.5, 0.84)), ((0.5, 0.84), (0.4, 0.06)), ((0.82, 0.02), (0.82, 0.98))], []),
    "bu": ([((0.2, 0.98), (0.2, 0.5)), ((0.8, 0.98), (0.8, 0.5)), ((0.2, 0.74), (0.8, 0.74)), ((0.2, 0.5), (0.8, 0.5)),
            ((0.04, 0.32), (0.96, 0.32)), ((0.5, 0.32), (0.5, 0.0))], []),
    "pum": ([((0.12, 0.98), (0.88, 0.98)), ((0.08, 0.75), (0.92, 0.75)), ((0.35, 0.98), (0.35, 0.75)),
             ((0.65, 0.98), (0.65, 0.75)), ((0.04, 0.6), (0.96, 0.6)), ((0.5, 0.6), (0.5, 0.46)),
             ((0.2, 0.35), (0.8, 0.35)), ((0.2, 0.02), (0.8, 0.02)), ((0.2, 0.35), (0.2, 0.02)), ((0.8, 0.35), (0.8, 0.02))],
            []),
    "up": ([((0.5, 0.0), (0.5, 0.92)), ((0.5, 1.0), (0.18, 0.66)), ((0.5, 1.0), (0.82, 0.66))], []),
    "reum": ([((0.15, 0.98), (0.83, 0.98)), ((0.83, 0.98), (0.83, 0.76)), ((0.83, 0.76), (0.15, 0.76)),
              ((0.15, 0.76), (0.15, 0.54)), ((0.15, 0.54), (0.86, 0.54)), ((0.04, 0.42), (0.96, 0.42)),
              ((0.2, 0.3), (0.8, 0.3)), ((0.2, 0.0), (0.8, 0.0)), ((0.2, 0.3), (0.2, 0.0)), ((0.8, 0.3), (0.8, 0.0))], []),
}


def _paint_word(part, mat, M, syllables, x0, y0, em, gap, sw=0.11):
    """Paint Hangul syllables (keys of _HANGUL) as flat strokes in frame M starting at (x0, y0)."""
    for i, syl in enumerate(syllables):
        strokes, rings = _HANGUL[syl]
        ox = x0 + i * (em + gap)
        st = [((ox + ax * em, y0 + ay * em), (ox + bx * em, y0 + by * em)) for ((ax, ay), (bx, by)) in strokes]
        rg = [(ox + cx * em, y0 + cy * em, r * em) for (cx, cy, r) in rings]
        sh.stroke_quads(part, mat, M, st, rg, sw=sw * em, lift=0.0009, ring_seg=12)


def _ao_merge_open(objs, occluders, mats, bake_kw, set_open):
    """Bake AO closed, then open (set_open(True)); faces with materials in `mats` (interior lining,
    treasure) take the OPEN result so the inside is not pitch black once the lid is up."""
    hp.bake_vertex_ao(objs=objs, occluders=occluders, **bake_kw)
    closed = {}
    for o in objs:
        a = o.data.color_attributes[hp.AO_ATTR]
        c = np.empty(len(o.data.loops) * 4, dtype=np.float32)
        a.data.foreach_get("color", c)
        closed[o.name] = c.reshape(-1, 4)
    set_open(True)
    bpy.context.view_layer.update()
    hp.bake_vertex_ao(objs=objs, occluders=occluders, **bake_kw)
    set_open(False)
    bpy.context.view_layer.update()
    for o in objs:
        me = o.data
        a = me.color_attributes[hp.AO_ATTR]
        op = np.empty(len(me.loops) * 4, dtype=np.float32)
        a.data.foreach_get("color", op)
        op = op.reshape(-1, 4)
        out = closed[o.name].copy()
        names = [m.name if m else "" for m in me.materials]
        inner = {i for i, n in enumerate(names) if n in mats}
        for p in me.polygons:
            if p.material_index in inner:
                out[p.loop_start:p.loop_start + p.loop_total] = op[p.loop_start:p.loop_start + p.loop_total]
        a.data.foreach_set("color", out.ravel())


# ---------------------------------------------------------------------------
# prop_rest
# ---------------------------------------------------------------------------
RS_CRYSTAL_Z = 2.04          # crystal rest height (game bobs it +-0.08 and spins it around Z)
GEM3 = ("glow_sml_ice", "glow_cyan", "glow_sml_deep")

# rune glyphs for the plinth risers (unit box, y up)
_RUNES = [
    [((0.5, 0.0), (0.5, 1.0)), ((0.5, 0.78), (0.86, 1.0)), ((0.5, 0.46), (0.86, 0.7))],
    [((0.25, 0.0), (0.25, 1.0)), ((0.25, 0.92), (0.78, 0.5)), ((0.78, 0.5), (0.25, 0.08))],
    [((0.5, 0.0), (0.5, 1.0)), ((0.14, 0.78), (0.5, 0.42)), ((0.86, 0.78), (0.5, 0.42))],
    [((0.18, 1.0), (0.82, 0.0)), ((0.82, 1.0), (0.18, 0.0)), ((0.18, 1.0), (0.18, 0.0)), ((0.82, 1.0), (0.82, 0.0))],
    [((0.5, 1.0), (0.14, 0.5)), ((0.14, 0.5), (0.5, 0.0)), ((0.5, 0.0), (0.86, 0.5)), ((0.86, 0.5), (0.5, 1.0))],
    [((0.3, 0.0), (0.3, 1.0)), ((0.7, 0.0), (0.7, 1.0)), ((0.3, 0.72), (0.7, 0.42))],
]


def _ring_blocks(part, mat, rng, n, r0, r1, z0, z1, phase, gap=0.008, jz=0.006, jr=0.004, divs=(1, 1, 1)):
    """Ring of n wedge-shaped stone blocks with flat outer faces and parallel joints."""
    out = []
    for k in range(n):
        a0 = 2 * math.pi * k / n + phase
        a1 = 2 * math.pi * (k + 1) / n + phase
        dz = rng.uniform(-jz, jz * 0.4)
        dr = rng.uniform(-jr, jr)

        def fn(u, v, w, a0=a0, a1=a1, dz=dz, dr=dr):
            r = r0 + (r1 + dr - r0) * v
            pa = Vector((math.cos(a0), math.sin(a0), 0)) * r
            pb = Vector((math.cos(a1), math.sin(a1), 0)) * r
            t = (pb - pa).normalized()
            pa = pa + t * gap / 2
            pb = pb - t * gap / 2
            p = pa.lerp(pb, u)
            p.z = z0 + (z1 + dz - z0) * w
            return p
        param_box(part, mat, fn, divs=divs)
        out.append((a0, a1, z1 + dz, r1 + dr))
    return out


def build_rest():
    """Aether rest fountain: 3-step stone plinth (bevelled blocks, glowing runes + rune ring), brass
    collar and fluted stem, gadrooned brass basin with jewelled band and glowing aether pool, gear
    column, petal cup and four arching brass ribs (halo ring, glowing finials) around the floating
    crystal; four small crystal lamps on the lower step. Child `crystal` (spins / bobs in game)."""
    root = empty("prop_rest", size=0.5)
    rng = random.Random(53)
    kit = Kit("prop_rest_fountain")
    stone = kit.part("stone", bevel=(0.016, 2, 30), smooth=40)
    brass = kit.part("brass", smooth=45)
    small = kit.part("small", smooth=60, occluder=False)
    glow = kit.part("glow", smooth=None, recalc=False, occluder=False)
    gems = kit.part("gems", flat=True, occluder=False)
    pool = kit.part("pool", smooth=60, recalc=False, occluder=False)

    # ---- plinth: two block rings + round drum ----
    t1 = _ring_blocks(stone, "stone_dark", rng, 12, 0.78, 1.15, 0.0, 0.16, 0.0)
    t2 = _ring_blocks(stone, "stone", rng, 12, 0.44, 0.92, 0.0, 0.32, math.pi / 12)
    revolve(stone, "stone", [(0.0, 0.0), (0.52, 0.0), (0.52, 0.43), (0.0, 0.43)], seg=32)
    # runes on the riser of the 2nd step (flat outer faces)
    for k, (a0, a1, ztop, r1) in enumerate(t2):
        ac = (a0 + a1) / 2
        rr = r1 * math.cos((a1 - a0) / 2)
        n = Vector((math.cos(ac), math.sin(ac), 0))
        Mr = frame((rr * n.x, rr * n.y, 0.235), n, up=(0, 0, 1)) @ T(-0.04, -0.05, 0.0) @ S(0.08, 0.1, 1)
        rune = _RUNES[k % len(_RUNES)]
        sh.stroke_quads(glow, "glow_cyan", Mr, rune, sw=0.16, lift=0.0015)
    # glowing rune ring inlaid on the first step
    revolve(glow, "glow_cyan", [(1.035, 0.1615), (1.0, 0.1615)], seg=48)

    # ---- brass collar, fluted stem ----
    revolve(brass, "brass_dark", [(0.2, 0.425), (0.37, 0.425), (0.37, 0.455), (0.345, 0.485), (0.25, 0.51),
                                  (0.2, 0.515)], seg=32, closed=True)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        rivet(small, "brass", (0.33 * math.cos(a), 0.33 * math.sin(a), 0.489), (math.cos(a) * 0.25, math.sin(a) * 0.25, 0.97),
              r=0.015, h=0.009)

    def flutes(a, r, z):
        f = max(0.0, min(1.0, (z - 0.53) / 0.05, (0.84 - z) / 0.05))
        return r * (1 - 0.09 * f * (0.5 + 0.5 * math.cos(12 * a)) ** 3)
    stem = [(0.21, 0.5), (0.17, 0.54), (0.156, 0.6), (0.15, 0.7), (0.154, 0.8), (0.17, 0.85), (0.21, 0.88)]
    revolve(brass, "brass", stem, seg=48, rfn=flutes)
    # glowing aether conduits in every other flute groove

    def groove_r(z):
        for (r0, z0), (r1, z1) in zip(stem, stem[1:]):
            if z0 <= z <= z1:
                g0 = flutes(0.0, r0, z0)
                g1 = flutes(0.0, r1, z1)
                return g0 + (g1 - g0) * (z - z0) / (z1 - z0)
        return stem[-1][0]
    for m in range(0, 12, 2):
        a = 2 * math.pi * m / 12
        n = (math.cos(a), math.sin(a), 0.0)
        zz = [0.6, 0.65, 0.7, 0.75, 0.79]
        sh.ribbon(glow, "glow_cyan", [((groove_r(z) + 0.0015) * n[0], (groove_r(z) + 0.0015) * n[1], z) for z in zz],
                  [n] * len(zz), 0.011)

    # ---- four curved struts from the collar to the basin underside (aligned with ribs and lamps) ----
    sctrl = [(0.31, 0.47), (0.35, 0.56), (0.39, 0.68), (0.45, 0.82), (0.53, 0.9), (0.62, 0.955)]
    spath = sh.catmull([(rho, 0.0, z) for (rho, z) in sctrl], sub=2)
    for k in range(4):
        phi = math.pi / 4 + k * math.pi / 2
        c, s_ = math.cos(phi), math.sin(phi)
        pts = [(p.x * c, p.x * s_, p.z) for p in spath]
        tube(brass, "brass_dark", pts, 0.02, seg=8, radii=[0.024 - 0.008 * i / (len(pts) - 1) for i in range(len(pts))])
        for (rho, z, rr) in ((0.36, 0.585, 0.03), (0.6, 0.947, 0.025)):
            revolve(brass, "brass", [(0.0, -0.012), (rr, -0.01), (rr, 0.01), (0.0, 0.012)], seg=8,
                    M=frame((rho * c, rho * s_, z), (Vector(pts[min(len(pts) - 1, 3 if rho < 0.5 else len(pts) - 2)])
                                                       - Vector(pts[2 if rho < 0.5 else len(pts) - 3]))))

    # ---- basin (capital + gadrooned bowl + rolled lip) ----
    def gadroon(a, r, z):
        f = max(0.0, math.sin(math.pi * (z - 0.885) / 0.13)) if 0.885 < z < 1.015 else 0.0
        return r * (1 + 0.035 * f * math.cos(16 * a))
    bowl = [(0.2, 0.86), (0.27, 0.9), (0.4, 0.935), (0.55, 0.965), (0.68, 1.005), (0.79, 1.07), (0.87, 1.14),
            (0.92, 1.19), (0.932, 1.216), (0.917, 1.232), (0.89, 1.232), (0.87, 1.215), (0.845, 1.18), (0.72, 1.07),
            (0.45, 1.03), (0.2, 1.02)]
    revolve(brass, "brass", bowl, seg=48, closed=True, rfn=gadroon)
    # jewelled band around the belly
    revolve(brass, "brass_dark", [(0.775, 1.04), (0.803, 1.047), (0.814, 1.069), (0.803, 1.091), (0.79, 1.094)],
            seg=48, closed=True)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        n = Vector((math.cos(a), math.sin(a), 0))
        p = n * 0.81 + Vector((0, 0, 1.069))
        revolve(gems, "glow_cyan", [(0.0, -0.004), (0.018, 0.0), (0.012, 0.012), (0.0, 0.017)], seg=6,
                M=frame(p, n))
    # aether pool: deep-glowing floor with a bright magic sigil, under a translucent rippled surface
    revolve(pool, "glow_sml_deep", [(0.87, 1.1), (0.0, 1.1)], seg=32)      # outer -> centre = faces up
    Ms = T(0, 0, 1.1)
    sh.stroke_quads(pool, "glow_sml_ice", Ms, [], [(0.0, 0.0, 0.745), (0.0, 0.0, 0.615)], sw=0.014, lift=0.002,
                    ring_seg=40)
    star = [(0.55 * math.cos(2 * math.pi * i / 8 + math.pi / 8), 0.55 * math.sin(2 * math.pi * i / 8 + math.pi / 8))
            for i in range(8)]
    sh.stroke_quads(pool, "glow_sml_ice", Ms, [(star[i], star[(i + 3) % 8]) for i in range(8)], sw=0.012, lift=0.0025)
    for k in range(8):
        a = 2 * math.pi * k / 8
        Mrn = Ms @ R("Z", math.degrees(a) - 90) @ T(-0.03, 0.68 - 0.035, 0.0) @ S(0.06, 0.07, 1)
        sh.stroke_quads(pool, "glow_sml_ice", Mrn, _RUNES[k % len(_RUNES)], sw=0.16, lift=0.003)
    revolve(pool, "jelly_sml_aether", [(0.875, 1.143), (0.6, 1.147), (0.3, 1.142), (0.0, 1.146)], seg=32)

    # ---- central column, gear, petal cup ----
    revolve(brass, "brass_dark", [(0.0, 1.09), (0.085, 1.09), (0.085, 1.17), (0.1, 1.19), (0.1, 1.23), (0.07, 1.25),
                                  (0.06, 1.5), (0.0, 1.5)], seg=16)
    sh.gear(brass, "brass", 0.21, 14, 0.032, hole=0.065, spokes=5, hub=0.075, M=T(0, 0, 1.34))
    revolve(brass, "brass_dark", [(0.0, 1.29), (0.09, 1.29), (0.09, 1.39), (0.0, 1.39)], seg=12)

    def petals(a, r, z):
        f = max(0.0, (z - 1.5) / 0.1)
        return r * (1 + 0.12 * f * math.cos(8 * a))
    revolve(brass, "brass", [(0.0, 1.46), (0.075, 1.46), (0.1, 1.5), (0.15, 1.55), (0.175, 1.585), (0.165, 1.6),
                             (0.13, 1.59), (0.0, 1.57)], seg=24, rfn=petals)

    # ---- four arching ribs around the crystal (between the view axes), halo ring, finials ----
    ctrl = [(0.1, 1.55), (0.2, 1.6), (0.33, 1.7), (0.43, 1.86), (0.465, 2.04), (0.44, 2.22), (0.36, 2.36),
            (0.26, 2.44), (0.2, 2.46)]
    path2 = sh.catmull([(rho, 0.0, z) for (rho, z) in ctrl], sub=2)
    nP = len(path2)
    ell = [(0.024 * math.cos(2 * math.pi * i / 8), 0.017 * math.sin(2 * math.pi * i / 8)) for i in range(8)]
    for k in range(4):
        phi = math.pi / 4 + k * math.pi / 2
        c, s_ = math.cos(phi), math.sin(phi)
        pts = [(p.x * c, p.x * s_, p.z) for p in path2]
        scale = [1.25 - 0.6 * i / (nP - 1) for i in range(nP)]
        sweep_profile(brass, "brass", pts, [(c, s_, 0)] * nP, ell, scale=scale)
        # collar where the halo ring joins, finial with a glowing bead at the tip
        revolve(brass, "brass_dark", [(0.0, -0.022), (0.028, -0.02), (0.032, 0.0), (0.028, 0.02), (0.0, 0.022)],
                seg=8, M=frame((0.465 * c, 0.465 * s_, 2.04), (0, 0, 1)))
        tipv = Vector(pts[-1]) - Vector(pts[-2])
        revolve(brass, "brass_dark", [(0.0, -0.01), (0.017, 0.0), (0.02, 0.018), (0.0, 0.03)], seg=8,
                M=frame(pts[-1], tipv))
        tp = Vector(pts[-1]) + tipv.normalized() * 0.03
        revolve(gems, "glow_cyan", [(0.0, -0.005), (0.016, 0.012), (0.0, 0.05)], seg=5, M=frame(tp, tipv))
    sh.revolve(brass, "brass", [(0.452, 2.04 - 0.012), (0.478, 2.04 - 0.012), (0.478, 2.04 + 0.012),
                                (0.452, 2.04 + 0.012)], seg=48, closed=True)

    # ---- four crystal lamps on the lower step (aligned with the ribs) ----
    for k in range(4):
        phi = math.pi / 4 + k * math.pi / 2
        c, s_ = math.cos(phi), math.sin(phi)
        Ml = T(0.99 * c, 0.99 * s_, 0.155)
        revolve(brass, "brass_dark", [(0.0, 0.0), (0.075, 0.0), (0.075, 0.025), (0.05, 0.045), (0.032, 0.07),
                                      (0.0, 0.07)], seg=12, M=Ml)
        revolve(brass, "brass", [(0.0, 0.06), (0.022, 0.06), (0.018, 0.4), (0.03, 0.42), (0.03, 0.44), (0.0, 0.44)],
                seg=8, M=Ml)
        revolve(brass, "brass", [(0.0, 0.43), (0.03, 0.43), (0.05, 0.47), (0.045, 0.48), (0.0, 0.47)], seg=10,
                M=Ml, rfn=lambda a, r, z: r * (1 + 0.15 * math.cos(5 * a) * (z > 0.46)))
        sh.facet_gem(gems, [(0.0, 0.47, 0), (0.03, 0.51, 0), (0.028, 0.555, 30), (0.0, 0.625, 0)], M=Ml @ R("Z", 45 * k),
                     mats=GEM3, nseg=6)

    body_parts = kit.build_parts(root)

    # ---- floating crystal (child 'crystal', pivot = its centre) ----
    ck = Kit("crystal")
    cg = ck.part("gem", flat=True, occluder=False)
    sh.facet_gem(cg, [(0.0, -0.34, 0), (0.075, -0.25, 22.5), (0.14, -0.14, 0), (0.17, -0.03, 22.5),
                      (0.17, 0.1, 22.5), (0.14, 0.2, 0), (0.085, 0.31, 22.5), (0.0, 0.42, 0)], mats=GEM3)
    for i, (rr, zz, a, sz) in enumerate(((0.3, -0.06, 20, 1.0), (0.31, 0.12, 150, 0.8), (0.29, -0.16, 265, 0.7))):
        ar = math.radians(a)
        sh.facet_gem(cg, [(0.0, -0.07 * sz, 0), (0.032 * sz, 0.0, 0), (0.022 * sz, 0.035 * sz, 36), (0.0, 0.09 * sz, 0)],
                     M=T(rr * math.cos(ar), rr * math.sin(ar), zz) @ R("Z", a) @ R("X", 18 - i * 12), mats=GEM3,
                     nseg=5)
    crystal_parts = ck.build_parts(root, loc=(0, 0, RS_CRYSTAL_Z))

    sh.bake_parts(body_parts, crystal_parts, distance=0.45, samples=48, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.3, dark=0.8))
    body = kit.join_parts(body_parts)
    ck.join_parts(crystal_parts)
    sh.tint_islands(body, {"stone", "stone_dark"}, lo=0.8, hi=1.0, seed=7, hue=(0.97, 1.0, 1.05))
    return root


# ---------------------------------------------------------------------------
# prop_chest
# ---------------------------------------------------------------------------
CH_W, CH_D, CH_H = 0.84, 0.54, 0.40     # body (planks) width X, depth Y, height (top of the rail)
CH_E = 0.012                            # hinge axis sits this far behind the back face
LID_RIM, LID_RZ, LID_T = 0.035, 0.17, 0.028
CH_OPEN = -1.9                          # game: lid.rotation.x = -open * 1.9


def _lid_arch(th, d=0.0):
    """Point (y, z) on the lid arch in LID space (pivot = hinge axis). th: 0 = front .. pi = back;
    d = depth below the outer surface."""
    ay, bz = CH_D / 2 - d, LID_RZ - d
    yc = -CH_D / 2 - CH_E
    return yc - ay * math.cos(th), LID_RIM + bz * math.sin(th)


def _lid_normal(th):
    ny, nz = -math.cos(th) / (CH_D / 2), math.sin(th) / LID_RZ
    L = math.hypot(ny, nz)
    return ny / L, nz / L


def build_chest():
    root = empty("prop_chest", size=0.5)
    W, D, H = CH_W, CH_D, CH_H
    t = 0.035
    rng = random.Random(11)

    # ================= body =================
    kit = Kit("prop_chest_body")
    wood = kit.part("wood", smooth=50)
    soft = kit.part("soft", smooth=35)
    trim = kit.part("trim", smooth=50)
    small = kit.part("small", smooth=60, occluder=False)
    gem = kit.part("gem", flat=True, occluder=False)

    # plinth / base skirt
    plate(wood, "wood_dark", sh.fillet_poly(_rect(W + 0.03, D + 0.03), 0.012, 2), 0.06, bev=0.008)
    # wall planks (3 per side, slightly irregular)
    z0, z1, n = 0.06, 0.355, 3
    ph = (z1 - z0) / n
    for i in range(n):
        zc = z0 + ph * (i + 0.5)
        for sy in (-1, 1):
            M = T(0, rng.uniform(-0.0015, 0.0015), 0) @ _about((0, sy * D / 2, zc), "X", rng.uniform(-0.8, 0.8))
            L = W / 2 - 0.006
            _plank(wood, "wood", (-L, sy * (D / 2 - t), zc), (L, sy * (D / 2 - t), zc), (0, sy, 0), ph, t, M=M,
                   grooves=_grain(rng, ph))
        for sx in (-1, 1):
            M = T(rng.uniform(-0.0015, 0.0015), 0, 0) @ _about((sx * W / 2, 0, zc), "Y", rng.uniform(-0.8, 0.8))
            L = D / 2 - t
            _plank(wood, "wood", (sx * (W / 2 - t), -L, zc), (sx * (W / 2 - t), L, zc), (sx, 0, 0), ph, t, segs=2,
                   M=M, grooves=_grain(rng, ph))
    # top rail (dark wood frame, rounded inner edge) + brass band around it
    ring_plate(wood, "wood_dark", _rect(W, D), _rect(W - 0.09, D - 0.09), z1, H, bev=0.0, bev_inner=0.006)
    band_o = sh.fillet_poly(_rect(W + 0.014, D + 0.014), 0.007, 2)
    band_i = sh.fillet_poly(_rect(W - 0.004, D - 0.004), 0.002, 2)
    ring_plate(trim, "brass", band_o, band_i, z1 - 0.004, H - 0.008, bev=0.003, bev_inner=0.0, steps=1)
    # interior lining
    box(soft, "sml_velvet", (W - 2 * t, D - 2 * t, 0.014), loc=(0, 0, z0 + 0.007))
    for sy in (-1, 1):
        box(soft, "sml_velvet", (W - 2 * t, 0.012, z1 - z0 - 0.01), loc=(0, sy * (D / 2 - t - 0.006), (z0 + z1) / 2 + 0.005))
    for sx in (-1, 1):
        box(soft, "sml_velvet", (0.012, D - 2 * t - 0.024, z1 - z0 - 0.01),
            loc=(sx * (W / 2 - t - 0.006), 0, (z0 + z1) / 2 + 0.005))

    # brass corner guards (L section) + cast feet
    zc0, zc1 = 0.05, z1 - 0.004
    g, Lg = 0.008, 0.075
    for sx in (-1, 1):
        for sy in (-1, 1):
            Lo = [(W / 2, D / 2 - Lg), (W / 2 + g, D / 2 - Lg), (W / 2 + g, D / 2 + g), (W / 2 - Lg, D / 2 + g),
                  (W / 2 - Lg, D / 2), (W / 2, D / 2)]
            Lo = sh.fillet_poly(Lo, [0.0025, 0.0025, 0.007, 0.0025, 0.0025, 0.0], 1)
            Lo = [(sx * x, sy * y) for x, y in Lo]
            prism(trim, "brass", sh.polygon_ccw(Lo), zc0, zc1)
            foot = sh.fillet_poly(_rect(0.088, 0.088, sx * (W / 2 + 0.021 - 0.044), sy * (D / 2 + 0.021 - 0.044)),
                                  0.012, 1)
            plate(trim, "brass", foot, 0.074, bev=0.008, steps=2, bottom=False)
            rivet(small, "iron", (sx * (W / 2 - 0.03), sy * (D / 2 + g), 0.2), (0, sy, 0), r=0.009)
            rivet(small, "iron", (sx * (W / 2 + g), sy * (D / 2 - 0.03), 0.2), (sx, 0, 0), r=0.009)

    # iron straps front / back (continue the lid straps), rivets per plank
    SX = 0.24
    strap = round_rect(0.055, 0.007, 0.003, steps=1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            sweep_profile(trim, "iron", [(sx * SX, sy * D / 2, 0.062), (sx * SX, sy * D / 2, zc1)],
                          [(0, sy, 0)] * 2, strap)
            for i in range(n):
                rivet(small, "brass", (sx * SX, sy * (D / 2 + 0.007), z0 + ph * (i + 0.5)), (0, sy, 0), r=0.011,
                      h=0.007)
        # hinge knuckles on the hinge axis (static; the lid straps wrap around them)
        revolve(trim, "iron", [(0.0, -0.042), (0.013, -0.042), (0.017, -0.038), (0.017, 0.038), (0.013, 0.042),
                               (0.0, 0.042)], seg=8, M=T(sx * SX, D / 2 + CH_E, H) @ R("Y", 90))

    # lock plate (shield) with glowing magic keyhole
    shield = [(-0.08, 0.0), (-0.08, -0.07), (-0.066, -0.106), (-0.036, -0.132), (0.0, -0.145),
              (0.036, -0.132), (0.066, -0.106), (0.08, -0.07), (0.08, 0.0)]
    shield = sh.fillet_poly(shield, [0.01, 0.006, 0, 0, 0.004, 0, 0, 0.006, 0.01], 1)
    Mp = _front(0, -D / 2, z1 - 0.004)
    plate(trim, "brass", shield, 0.013, bev=0.004, steps=1, M=Mp, z0=-0.002)
    ring_plate(trim, "iron", circle2d(0.03, 12, cy=-0.074), circle2d(0.021, 12, cy=-0.074), 0.009, 0.0145,
               bev=0.002, bev_inner=0.0, steps=1, M=Mp)
    kh = [(0.0125 * math.cos(math.radians(a)), -0.067 + 0.0125 * math.sin(math.radians(a)))
          for a in range(-60, 241, 30)]
    kh += [(-0.0085, -0.093), (0.0085, -0.093)]
    prism(gem, "glow_cyan", kh, 0.006, 0.0125, M=Mp, fan=True, center=(0.0, -0.075))
    for (px, py) in ((-0.062, -0.018), (0.062, -0.018), (-0.045, -0.112), (0.045, -0.112)):
        rivet(small, "iron", (px, -D / 2 - 0.0105, z1 - 0.004 + py), (0, -1, 0), r=0.009, h=0.006)

    # side handles: mount plate, two eyes, hanging iron bail
    for sx in (-1, 1):
        Mh = T(sx * W / 2, 0, 0.3) @ R("Z", 90 * sx) @ R("X", 90)   # plate z -> outward (+-X)
        plate(trim, "brass", sh.fillet_poly(_rect(0.17, 0.06), 0.012, 2), 0.008, bev=0.003, steps=1, M=Mh)
        for sy in (-1, 1):
            rivet(small, "iron", (sx * (W / 2 + 0.008), sy * 0.068, 0.3), (sx, 0, 0), r=0.009)
            tube(small, "iron", [(sx * (W / 2 + 0.006), sy * 0.042, 0.3), (sx * (W / 2 + 0.034), sy * 0.042, 0.3)],
                 r=0.009, seg=6, caps=False)
        xb = sx * (W / 2 + 0.032)
        bail = [(-0.042, 0.3), (-0.06, 0.268), (-0.058, 0.232), (-0.034, 0.207), (0.0, 0.199),
                (0.034, 0.207), (0.058, 0.232), (0.06, 0.268), (0.042, 0.3)]
        tube(small, "iron", [(xb, y, z) for (y, z) in bail], r=0.009, seg=6)

    # ---- treasure (visible when open) ----
    zf = z0 + 0.014
    heap_c = Vector((0.0, 0.01, zf))
    heap_s = Vector((0.31, 0.175, 0.17))
    revolve(small, "sml_gold", [(1.0, 0.0), (0.95, 0.22), (0.8, 0.5), (0.5, 0.8), (0.0, 1.0)], seg=16,
            M=T(*heap_c) @ S(*heap_s),
            rfn=lambda a, r, z: r * (1 + 0.09 * math.sin(3 * a + 5 * z) + 0.06 * math.sin(5 * a + 1.3)))
    crng = random.Random(3)
    for i in range(15):
        phi = crng.uniform(0, 2 * math.pi)
        al = math.radians(crng.uniform(5, 80))
        d = Vector((math.cos(phi) * math.sin(al), math.sin(phi) * math.sin(al), math.cos(al)))
        pos = heap_c + Vector((d.x * heap_s.x, d.y * heap_s.y, d.z * heap_s.z)) * 0.98
        nrm = Vector((d.x / heap_s.x, d.y / heap_s.y, d.z / heap_s.z)).normalized()
        nrm = (nrm + Vector((crng.uniform(-0.5, 0.5), crng.uniform(-0.5, 0.5), 0))).normalized()
        prism(small, "sml_gold", circle2d(0.027, 8), -0.001, 0.0055, M=frame(pos, nrm, spin=crng.uniform(0, 360)))
    for (x, y) in ((-0.33, -0.15), (0.34, -0.12), (0.02, -0.19)):
        prism(small, "sml_gold", circle2d(0.027, 8), 0.0, 0.0055, M=T(x, y, zf))
    # goblet leaning on the heap
    gob = [(0.0, 0.0), (0.034, 0.0), (0.03, 0.007), (0.009, 0.016), (0.008, 0.05), (0.015, 0.057),
           (0.026, 0.08), (0.036, 0.115), (0.031, 0.117), (0.0, 0.088)]
    revolve(small, "sml_gold", gob, seg=10, M=T(0.21, 0.05, zf + 0.05) @ R("Y", 30) @ R("X", -12))
    # gems
    for (pos, r, rot) in (((-0.07, -0.02, zf + 0.165), 0.036, (14, 8)), ((0.1, 0.04, zf + 0.13), 0.025, (-30, 20)),
                          ((-0.2, 0.05, zf + 0.08), 0.023, (35, -10))):
        revolve(gem, "glow_cyan", [(0.0, -r * 1.1), (r, 0.0), (r * 0.66, r * 0.42), (0.0, r * 0.55)], seg=6,
                M=T(*pos) @ R("X", rot[0]) @ R("Y", rot[1]))

    body_parts = kit.build_parts(root)

    # ================= lid (pivot on the hinge axis) =================
    lk = Kit("lid")
    lwood = lk.part("wood", smooth=50)
    lsoft = lk.part("soft", smooth=50)
    ltrim = lk.part("trim", smooth=50)
    lsmall = lk.part("small", smooth=60, occluder=False)
    yc = -D / 2 - CH_E
    # brass rim band (bottom of the lid)
    ring_plate(ltrim, "brass", sh.fillet_poly(_rect(W + 0.014, D + 0.014, cy=yc), 0.007, 2),
               sh.fillet_poly(_rect(W - 0.07, D - 0.07, cy=yc), 0.002, 2), 0.0, LID_RIM, bev=0.003, bev_inner=0.0,
               steps=1)
    # arch planks (5 staves across the arch), cross-section swept along X
    xs = W / 2 - 0.03
    edges = [0, 36, 72, 108, 144, 180]
    for i in range(5):
        th0, th1 = math.radians(edges[i]), math.radians(edges[i + 1])
        lift = rng.uniform(-0.0015, 0.002)
        thg = th0 + (th1 - th0) * rng.uniform(0.3, 0.7)
        dg = math.radians(0.9)
        ths = sorted(_lin(th0, th1, 3) + [thg - dg, thg + dg])
        outer = [_lid_arch(th, -lift) for th in ths]
        gi = ths.index(thg - dg) + 1
        outer.insert(gi, _lid_arch(thg, -lift + rng.uniform(0.0013, 0.002)))
        inner = [_lid_arch(th, LID_T) for th in _lin(th1, th0, 2)]
        prof = [(-y, z) for (y, z) in outer + inner]
        no = len(outer)
        prof = sh.fillet_poly(prof, 0.0065, 2, mask=[k in (0, no - 1) for k in range(len(prof))])
        sweep_profile(lwood, "wood", [(x, 0, 0) for x in _lin(-xs, xs, 3)], [(0, 0, 1)] * 4, prof)
    # end caps (half-ellipse boards) + their brass arch trims
    cap = [_lid_arch(math.pi * k / 16) for k in range(17)]
    trim_prof = round_rect(0.052, 0.0065, 0.003, steps=1, u0=-0.001)
    strap_prof = round_rect(0.055, 0.0075, 0.003, steps=1, u0=-0.001)
    for sx in (-1, 1):
        prism(lwood, "wood", cap, sx * xs, sx * (W / 2), M=_YZX)
        pts, ups = [], []
        for th in _lin(0, math.pi, 12):
            y, z = _lid_arch(th)
            ny, nz = _lid_normal(th)
            pts.append((sx * (W / 2 - 0.02), y, z))
            ups.append((0, ny, nz))
        sweep_profile(ltrim, "brass", pts, ups, trim_prof)
        for k in (3, 13):
            th = math.pi * k / 16
            y, z = _lid_arch(th)
            ny, nz = _lid_normal(th)
            rivet(lsmall, "iron", (sx * (W / 2 - 0.02), y + ny * 0.0055, z + nz * 0.0055), (0, ny, nz), r=0.009)
    # iron straps over the arch, wrapping down to the hinge knuckles at the back
    for sx in (-1, 1):
        pts, ups = [], []
        for th in _lin(0, math.pi, 14):
            y, z = _lid_arch(th)
            ny, nz = _lid_normal(th)
            pts.append((sx * SX, y, z))
            ups.append((0, ny, nz))
        pts += [(sx * SX, -CH_E, LID_RIM * 0.4), (sx * SX, -CH_E, -0.006)]
        ups += [(0, 1, 0), (0, 1, 0)]
        sweep_profile(ltrim, "iron", pts, ups, strap_prof)
        for k in range(5):
            th = math.radians(18 + 36 * k)
            y, z = _lid_arch(th)
            ny, nz = _lid_normal(th)
            rivet(lsmall, "brass", (sx * SX, y + ny * 0.0065, z + nz * 0.0065), (0, ny, nz), r=0.011, h=0.007)
    # hasp hanging over the lock plate
    yf = -D - CH_E - 0.007
    hasp = [(-0.03, 0.03), (-0.03, -0.055), (-0.021, -0.074), (0.0, -0.082), (0.021, -0.074), (0.03, -0.055),
            (0.03, 0.03)]
    hasp = sh.fillet_poly(hasp, [0.006, 0, 0, 0, 0, 0, 0.006], 1)
    plate(ltrim, "brass", hasp, 0.0075, bev=0.0025, steps=1, M=_front(0, yf - 0.004, 0.0))
    revolve(ltrim, "iron", [(0.0, -0.034), (0.007, -0.034), (0.0095, -0.031), (0.0095, 0.031), (0.007, 0.034),
                                  (0.0, 0.034)], seg=8, M=T(0, yf - 0.007, 0.027) @ R("Y", 90))
    rivet(lsmall, "iron", (0, yf - 0.0115, -0.03), (0, -1, 0), r=0.016, h=0.011, seg=8)
    # lining inside the lid + quilting buttons
    dl = LID_T + 0.001

    def lfn(u, v, w):
        y, z = _lid_arch(math.pi * v, dl + 0.009 * w)
        return Vector((-xs + 2 * xs * u, y, z))
    param_box(lsoft, "sml_velvet", lfn, divs=(2, 8, 1))
    for sx in (-1, 1):
        inner = [_lid_arch(math.pi * k / 10, dl) for k in range(11)]
        prism(lsoft, "sml_velvet", inner, sx * (xs - 0.009), sx * xs, M=_YZX)
    for x in (-0.24, 0.0, 0.24):
        for thd in (50, 90, 130):
            th = math.radians(thd)
            y, z = _lid_arch(th, dl + 0.009)
            ny, nz = _lid_normal(th)
            rivet(lsmall, "brass", (x, y, z), (0, -ny, -nz), r=0.009, h=0.005, seg=5)
    lid_parts = lk.build_parts(root, loc=(0, D / 2 + CH_E, H))

    # ================= finishing =================
    allp = body_parts + lid_parts

    def set_open(on):
        for o, _ in lid_parts:
            o.rotation_euler = (CH_OPEN if on else 0.0, 0.0, 0.0)
    _ao_merge_open([o for o, _ in allp], [o for o, c in allp if c], {"sml_velvet", "sml_gold"},
                   dict(distance=0.22, samples=48, strength=0.85, floor=0.3,
                        tint=sh.ground_grime(0.0, 0.12, dark=0.85)), set_open)
    objs = [kit.join_parts(body_parts), lk.join_parts(lid_parts)]
    for o in objs:
        sh.tint_islands(o, {"wood", "wood_dark"}, lo=0.8, hi=1.0, seed=len(o.name) * 7, streak=0.12,
                        streak_freq=14)
    return root


# ---------------------------------------------------------------------------
# prop_crate
# ---------------------------------------------------------------------------

def _side_frame(k):
    """Face-local frame of side face k (0 front -Y, 1 right +X, 2 back +Y, 3 left -X):
    local (a, b, c) = (horizontal along the face, height z, outward distance from the centre)."""
    return R("Z", 90 * k) @ R("X", 90)


def build_crate():
    """1 m shipping crate: rounded dark frame beams, grooved board panels, diagonal braces, cast brass
    corner caps, nails, brass stencil plate, lifting cleats. Top stays flat at z = 1.0 (crates stack)."""
    root = empty("prop_crate", size=0.5)
    rng = random.Random(23)
    kit = Kit("prop_crate_mesh")
    wood = kit.part("wood", smooth=50)
    trim = kit.part("trim", smooth=50)
    small = kit.part("small", smooth=60, occluder=False)
    paint = kit.part("paint", smooth=None, recalc=False, occluder=False)

    o = 0.495           # beam outer face (caps reach 0.5)
    b = 0.09            # beam section
    i0 = o - b          # inner square half size
    zb0, zb1 = 0.005, 0.995
    beam = round_rect(b, b, 0.01, steps=2, corners=(1, 1, 1, 1), u0=-b / 2)
    # corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (o - b / 2), sy * (o - b / 2)
            sweep_profile(wood, "wood_dark", [(x, y, zb0), (x, y, 0.5), (x, y, zb1)], [(sx, 0, 0)] * 3, beam)
    # horizontal beams (butt between the posts)
    for z in (zb0 + b / 2, zb1 - b / 2):
        for s in (-1, 1):
            y = s * (o - b / 2)
            sweep_profile(wood, "wood_dark", [(-i0, y, z), (i0, y, z)], [(0, s, 0)] * 2, beam)
            x = s * (o - b / 2)
            sweep_profile(wood, "wood_dark", [(x, -i0, z), (x, i0, z)], [(s, 0, 0)] * 2, beam)

    # board panels: 3 boards per face, recessed 22 mm behind the beams
    bt = 0.022          # board thickness
    rec = 0.022         # boards sit this far behind the beam faces
    nb = 3
    bh = (zb1 - zb0 - 2 * b) / nb
    for k in range(4):
        Mf = _side_frame(k)
        for j in range(nb):
            zc = zb0 + b + bh * (j + 0.5)
            off = rng.uniform(-0.0015, 0.001)
            gr = _grain(rng, bh, 1 if rng.random() < 0.7 else 2)
            _plank(wood, "wood", (-i0 - 0.01, zc, o - rec - bt + off), (i0 + 0.01, zc, o - rec - bt + off),
                   (0, 0, 1), bh, bt, r=0.006, segs=2, steps=1, grooves=gr, M=Mf)
    for j in range(nb):     # top
        yc = -i0 + (2 * i0) / nb * (j + 0.5)
        off = rng.uniform(-0.0015, 0.001)
        _plank(wood, "wood", (-i0 - 0.01, yc, zb1 - rec - bt + off), (i0 + 0.01, yc, zb1 - rec - bt + off),
               (0, 0, 1), (2 * i0) / nb, bt, r=0.006, segs=2, steps=1, grooves=_grain(rng, bh))
    box(wood, "wood_dark", (2 * i0 + 0.02, 2 * i0 + 0.02, 0.02), loc=(0, 0, zb0 + 0.03))   # closed bottom

    # diagonal braces on the four sides (alternating)
    bw, btk = 0.1, 0.02
    L = math.hypot(2 * i0, zb1 - zb0 - 2 * b)
    for k in range(4):
        Mf = _side_frame(k)
        d = 1 if k % 2 == 0 else -1
        p0 = Vector((-d * i0, zb0 + b, 0.0))
        p1 = Vector((d * i0, zb1 - b, 0.0))
        dirv = (p1 - p0).normalized()
        e = bw * 0.55
        a0, a1 = p0 - dirv * e, p1 + dirv * e
        c0 = o - rec
        pts = [Vector((a0.x, a0.y, c0)).lerp(Vector((a1.x, a1.y, c0)), q / 2) for q in range(3)]
        sweep_profile(wood, "wood_dark", pts, [(0, 0, 1)] * 3, round_rect(bw, btk + 0.001, 0.005, steps=1), M=Mf)

    # cast brass corner caps (flush with the 1 m bounds) + rivets
    cs = 0.125
    for sx in (-1, 1):
        for sy in (-1, 1):
            out = sh.fillet_poly(_rect(cs, cs, sx * (0.5 - cs / 2), sy * (0.5 - cs / 2)), 0.016, 1)
            for top in (0, 1):
                Mz = T(0, 0, 1.0 - cs) if top else T(0, 0, cs) @ S(1, 1, -1)
                plate(trim, "brass", out, cs, bev=0.009, steps=2, M=Mz, bottom=True)
                zr = 1.0 - cs * 0.45 if top else cs * 0.45
                rivet(small, "brass_dark", (sx * 0.5, sy * (0.5 - cs * 0.45), zr), (sx, 0, 0), r=0.012, h=0.007)
                rivet(small, "brass_dark", (sx * (0.5 - cs * 0.45), sy * 0.5, zr), (0, sy, 0), r=0.012, h=0.007)

    # brass stencil plate on the front (upper-left triangle, clear of the brace): gear emblem + 'lettering'
    Mpl = _side_frame(0) @ T(-0.165, 0.765, o - rec)
    nrm = _side_frame(0).to_3x3() @ Vector((0, 0, 1))
    pw, phh = 0.3, 0.12
    plate(trim, "brass", sh.fillet_poly(_rect(pw, phh), 0.018, 2), 0.006, bev=0.0025, steps=1, M=Mpl)
    for (px, py) in ((-pw / 2 + 0.017, phh / 2 - 0.017), (pw / 2 - 0.017, phh / 2 - 0.017),
                     (-pw / 2 + 0.017, -phh / 2 + 0.017), (pw / 2 - 0.017, -phh / 2 + 0.017)):
        rivet(small, "brass_dark", Mpl @ Vector((px, py, 0.006)), nrm, r=0.008, h=0.005, seg=5)
    sh.gear(trim, "brass_dark", 0.036, 8, 0.006, hole=0.012, M=Mpl @ T(-0.1, 0, 0.007))
    for (lx, ly, lw) in ((0.04, 0.022, 0.15), (0.015, -0.006, 0.1), (0.035, -0.032, 0.14)):
        box(trim, "brass_dark", (lw, 0.012, 0.004), M=Mpl @ T(lx, ly, 0.007))

    # stencil paint: '부품' (parts) on the back, 'this side up' arrows on the sides (free brace triangles)
    _paint_word(paint, "sml_paint", _side_frame(2) @ T(0, 0, o - rec + 0.0025), ("bu", "pum"), -0.37, 0.7, 0.13, 0.025,
                sw=0.12)
    for k in (1, 3):
        _paint_word(paint, "sml_paint", _side_frame(k) @ T(0, 0, o - rec + 0.0025), ("up", "up"), -0.36, 0.15, 0.15,
                    0.02, sw=0.14)

    # lifting cleats on the left / right sides
    for k in (1, 3):
        Mf = _side_frame(k)
        _plank(wood, "wood_dark", (-0.17, 0.8, o - rec), (0.17, 0.8, o - rec), (0, 0, 1), 0.055, 0.035, r=0.01,
               segs=1, steps=2, M=Mf)

    built = kit.build_parts(root)
    sh.bake_parts(built, distance=0.25, samples=48, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.25, dark=0.8))
    obj = kit.join_parts(built)
    sh.tint_islands(obj, {"wood", "wood_dark"}, lo=0.78, hi=1.0, seed=5, streak=0.12, streak_freq=12)
    return root


# ---------------------------------------------------------------------------
# prop_barrel
# ---------------------------------------------------------------------------
BR_H, BR_END, BR_MID = 1.1, 0.37, 0.465
BR_N = 14               # staves


def _br_r(z):
    """Outer radius of the barrel belly at height z."""
    q = (z - BR_H / 2) / (BR_H / 2)
    return BR_END + (BR_MID - BR_END) * (1 - q * q)


def build_barrel():
    """Bulging barrel: 14 individual staves (curved faces, V grooves), 4 iron hoops with rivets, recessed
    plank head with a bung, brass spigot with T-handle, small brass maker's plate."""
    root = empty("prop_barrel", size=0.5)
    rng = random.Random(31)
    kit = Kit("prop_barrel_mesh")
    wood = kit.part("wood", smooth=50)
    trim = kit.part("trim", smooth=50)
    deco = kit.part("deco", smooth=50, occluder=False)
    small = kit.part("small", smooth=60, occluder=False)

    N, H = BR_N, BR_H
    st = 0.03                                   # stave thickness
    zs = _lin(0.0, H, 8)
    for k in range(N):
        phi = 2 * math.pi * (k + 0.5) / N + rng.uniform(-0.01, 0.01)
        c, s_ = math.cos(phi), math.sin(phi)
        dr = rng.uniform(-0.0015, 0.0015)
        top = H + rng.uniform(-0.006, 0.002)
        zz = zs[:-1] + [top]
        pts = [((_br_r(z) + dr) * c, (_br_r(z) + dr) * s_, z) for z in zz]
        w = 2 * BR_MID * math.sin(math.pi / N) - 0.004
        sag = BR_MID - math.sqrt(BR_MID ** 2 - (w / 2) ** 2)
        prof = [(-w / 2, -sag - st), (w / 2, -sag - st), (w / 2, -sag), (0.0, 0.0), (-w / 2, -sag)]
        prof = sh.fillet_poly(prof, 0.006, 1, mask=[False, False, True, False, True])
        sweep_profile(wood, "wood", pts, [(c, s_, 0)] * len(pts), prof, scale=[_br_r(z) / BR_MID for z in zz])

    # iron hoops (follow the belly), rivets
    hoops = [(0.075, 0.06), (0.31, 0.05), (0.79, 0.05), (1.025, 0.06)]
    for hi, (zc, hh) in enumerate(hoops):
        z0, z1 = zc - hh / 2, zc + hh / 2
        r0, r1 = _br_r(z0) + 0.001, _br_r(z1) + 0.001
        t = 0.009
        prof = [(r0, z0), (r0 + t, z0), ((r0 + r1) / 2 + t + 0.003, zc), (r1 + t, z1), (r1, z1)]
        revolve(trim, "iron", prof, seg=24, closed=True, phase=math.pi / 24)
        for j in range(4):
            a = 2 * math.pi * (j + 0.5) / 4 + hi * 0.3
            rr = _br_r(zc) + 0.001 + t + 0.0025
            rivet(small, "brass_dark", (rr * math.cos(a), rr * math.sin(a), zc), (math.cos(a), math.sin(a), 0),
                  r=0.011, h=0.006)

    # recessed head: 5 boards (circle-clipped), bung with brass ring
    zh = H - 0.035
    rh = _br_r(zh) - st - 0.006
    nbd = 5
    for j in range(nbd):
        y0 = -rh + 2 * rh * j / nbd + 0.0015
        y1 = -rh + 2 * rh * (j + 1) / nbd - 0.0015
        ys = _lin(y0, y1, 3)
        right = [(math.sqrt(max(rh * rh - y * y, 0.0)), y) for y in ys]
        left = [(-x, y) for (x, y) in reversed(right)]
        plate(wood, "wood", right + left, 0.03, bev=0.005, steps=1, M=T(rng.uniform(-0.01, 0.01), 0, zh - 0.03))
    # burnt-in brand on the head: ring + '기름' (oil)
    paint = kit.part("paint", smooth=None, recalc=False, occluder=False)
    Mst = T(-0.07, 0.07, zh + 0.0012) @ R("Z", -8)
    sh.stroke_quads(paint, "wood_dark", Mst, [], [(0.0, 0.0, 0.13)], sw=0.013, lift=0.0, ring_seg=20)
    sh.stroke_quads(paint, "wood_dark", Mst, [], [(0.0, 0.0, 0.108)], sw=0.005, lift=0.0, ring_seg=20)
    _paint_word(paint, "wood_dark", Mst, ("gi", "reum"), -0.085, -0.04, 0.08, 0.01, sw=0.12)
    bx, by = 0.12, -0.08
    ring_plate(trim, "brass", circle2d(0.045, 12, cx=bx, cy=by), circle2d(0.03, 12, cx=bx, cy=by), zh - 0.004,
               zh + 0.006, bev=0.003, bev_inner=0.0, steps=1)
    revolve(wood, "wood_dark", [(0.0, zh - 0.01), (0.03, zh - 0.01), (0.03, zh + 0.012), (0.024, zh + 0.018),
                                (0.0, zh + 0.018)], seg=10, M=T(bx, by, 0))

    # brass spigot near the bottom of the front
    zt = 0.25
    Rt = _br_r(zt)
    Ms = T(0, -Rt + 0.004, zt) @ R("X", 90)        # local +Z -> -Y (outward)
    revolve(deco, "brass", [(0.0, -0.012), (0.048, -0.012), (0.048, 0.004), (0.038, 0.013), (0.0, 0.013)], seg=12, M=Ms)
    revolve(deco, "brass", [(0.0, 0.01), (0.019, 0.01), (0.019, 0.07), (0.027, 0.075), (0.027, 0.112),
                            (0.022, 0.118), (0.0, 0.118)], seg=10, M=Ms)
    yb = -Rt + 0.004 - 0.095
    tube(deco, "brass", [(0, yb, zt - 0.01), (0, yb - 0.004, zt - 0.06), (0, yb - 0.012, zt - 0.085)], r=0.013, seg=8,
         radii=[0.015, 0.014, 0.016])
    revolve(deco, "brass_dark", [(0.0, 0.0), (0.009, 0.0), (0.009, 0.045), (0.0, 0.045)], seg=6,
            M=T(0, yb, zt + 0.02))
    tube(deco, "brass_dark", [(-0.05, yb, zt + 0.07), (0.05, yb, zt + 0.07)], r=0.008, seg=6)
    for sx in (-1, 1):
        revolve(deco, "brass_dark", [(0.0, -0.014), (0.012, -0.007), (0.012, 0.007), (0.0, 0.014)], seg=6,
                M=T(sx * 0.055, yb, zt + 0.07) @ R("Y", 90))

    # small curved brass maker's plate with a gear emblem
    zp = 0.56
    Rp = _br_r(zp) + 0.0005
    arc = [(Rp * math.sin(a), -Rp * math.cos(a), zp) for a in _lin(-0.2, 0.2, 4)]
    sweep_profile(deco, "brass", arc, [(math.sin(a), -math.cos(a), 0) for a in _lin(-0.2, 0.2, 4)],
                  round_rect(0.085, 0.005, 0.002, steps=1, u0=-0.0015))
    sh.gear(deco, "brass_dark", 0.022, 6, 0.006, M=T(0, -Rp - 0.004, zp) @ R("X", 90))
    for sx in (-1, 1):
        a = sx * 0.17
        rivet(small, "brass_dark", (Rp * math.sin(a) * 1.008, -Rp * math.cos(a) * 1.008, zp),
              (math.sin(a), -math.cos(a), 0), r=0.008, h=0.005, seg=5)

    built = kit.build_parts(root)
    sh.bake_parts(built, distance=0.25, samples=48, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.25, dark=0.78))
    obj = kit.join_parts(built)
    sh.tint_islands(obj, {"wood", "wood_dark"}, lo=0.76, hi=1.0, seed=9, streak=0.05, streak_freq=10)
    return root


# ---------------------------------------------------------------------------
# prop_signpost
# ---------------------------------------------------------------------------

def _post_profile(a, r, grooves, rng):
    """Square post section (side a) with rounded corners and a V grain groove on some faces."""
    P = [(-a / 2, -a / 2), (a / 2, -a / 2), (a / 2, a / 2), (-a / 2, a / 2)]
    pts, mask = [], []
    for i in range(4):
        p0, p1 = Vector(P[i]), Vector(P[(i + 1) % 4])
        pts.append(tuple(p0))
        mask.append(True)
        if i in grooves:
            e = (p1 - p0).normalized()
            n = Vector((-e.y, e.x))          # inward for CCW
            f = rng.uniform(0.35, 0.65)
            c = p0.lerp(p1, f)
            gw, gd = 0.006, 0.0025
            pts += [tuple(c - e * gw), tuple(c + n * gd), tuple(c + e * gw)]
            mask += [False, False, False]
    return sh.fillet_poly(pts, r, 2, mask=mask)


def build_signpost():
    """Crossroads signpost: grooved dark post with brass ferrule and collar, gear platform carrying a tiny
    glowing lantern on top, three arrow boards (rounded slabs, brass inlay border, brass pictograms
    - clock / crystal / gear - and painted 'lettering' on both faces), stones around the foot."""
    root = empty("prop_signpost", size=0.5)
    rng = random.Random(41)
    kit = Kit("prop_signpost_mesh")
    wood = kit.part("wood", smooth=50)
    trim = kit.part("trim", smooth=50)
    small = kit.part("small", smooth=60, occluder=False)
    rock = kit.part("rock", smooth=70, subdiv=1, zclamp=0.0)
    pebble = kit.part("pebble", smooth=70, zclamp=0.0)
    flat = kit.part("flat", flat=True, occluder=False)
    paint = kit.part("paint", smooth=None, recalc=False, occluder=False)

    a = 0.13
    ztop = 1.98
    prof = _post_profile(a, 0.02, (0, 1, 2, 3), rng)
    zs = [0.0, 0.16, 0.6, 1.1, 1.6, 1.9, ztop]
    loops = []
    for z in zs:
        k = 1.0 - 0.06 * max(0.0, z) / ztop
        loops.append([(x * k, y * k, z) for (x, y) in prof])
    sh.loft(wood, "wood_dark", loops, cap_first=True, cap_last=True)

    # brass ferrule (foot) and collar (top), bolts
    def band(z0, z1, k):
        ao = a * k
        ring_plate(trim, "brass", sh.fillet_poly(_rect(ao + 0.022, ao + 0.022), 0.022, 2),
                   sh.fillet_poly(_rect(ao - 0.004, ao - 0.004), 0.018, 2), z0, z1, bev=0.003, bev_inner=0.0, steps=1)
        for sx, sy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            rivet(small, "brass_dark", (sx * (ao / 2 + 0.011), sy * (ao / 2 + 0.011), (z0 + z1) / 2), (sx, sy, 0),
                  r=0.011, h=0.006)
    band(0.02, 0.15, 1.0)
    band(ztop - 0.09, ztop, 0.945)

    # gear platform + tiny lantern finial
    sh.gear(trim, "brass", 0.098, 10, 0.022, M=T(0, 0, ztop + 0.011))
    plate(trim, "brass", sh.fillet_poly(_rect(0.11, 0.11), 0.016, 1), 0.016, bev=0.005, steps=1, M=T(0, 0, ztop + 0.02))
    zl0, zl1 = ztop + 0.034, ztop + 0.13
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(trim, "brass", (0.013, 0.013, zl1 - zl0), loc=(sx * 0.044, sy * 0.044, (zl0 + zl1) / 2))
    box(flat, "glass", (0.082, 0.082, zl1 - zl0), loc=(0, 0, (zl0 + zl1) / 2))
    revolve(flat, "glow_amber", [(0.0, zl0 + 0.008), (0.02, zl0 + 0.03), (0.014, zl0 + 0.06), (0.0, zl1 - 0.012)], seg=6)
    plate(trim, "brass", sh.fillet_poly(_rect(0.118, 0.118), 0.016, 1), 0.012, bev=0.004, steps=1, M=T(0, 0, zl1))
    revolve(trim, "brass", [(0.0, zl1 + 0.01), (0.085, zl1 + 0.01), (0.055, zl1 + 0.03), (0.02, zl1 + 0.05),
                            (0.0, zl1 + 0.055)], seg=4, phase=math.pi / 4)
    revolve(small, "brass_dark", [(0.0, zl1 + 0.048), (0.014, zl1 + 0.056), (0.014, zl1 + 0.064), (0.004, 2.19),
                                  (0.0, 2.2)], seg=8)

    # arrow boards: (z, direction +-1, length, yaw deg, mounted on front (-1) / back (+1), icon, word)
    # Directions match the field layout once world.ts aims local +X (three.js) at the clock tower:
    # 시계탑 -> +X (north), 마석 -> -Y (three.js +Z = east, aether crystals), 증기 -> +Y (west, steam pipes)
    boards = [(1.78, 1, 0.92, 0.0, -1, "clock", ("si", "gye", "tap")),
              (1.5, 1, 0.84, -90.0, 1, "crystal", ("ma", "seok")),
              (1.22, 1, 0.74, 80.0, 1, "gear", ("jeung", "gi"))]
    bh, bt = 0.2, 0.042
    for (z, d, L, yaw, side, icon, word) in boards:
        tip = bh * 0.55
        raw = [(-0.075, -bh / 2), (L - tip, -bh / 2), (L, 0.0), (L - tip, bh / 2), (-0.075, bh / 2)]
        outline = sh.fillet_poly(raw, [0.016, 0.008, 0.012, 0.008, 0.016], 2)
        tilt = rng.uniform(-2.0, 2.0)
        # board frame: x along the arrow, y up, z through the board thickness (0 .. bt), centred on the
        # plane touching the post's front (side -1) or back (side +1) face
        Mb = R("Z", yaw) @ T(0, side * (a / 2 * 0.97 + bt / 2), z) @ R("Z", 0 if d > 0 else 180) @ R("X", 90) \
            @ R("Z", tilt) @ T(0, 0, -bt / 2)
        slab(wood, "wood", outline, bt, bev=0.006, steps=2, M=Mb)
        for face in (0, 1):
            # Fr: face frame as seen by its viewer (x right, y up, z out of the board, z = 0 on the face)
            if face:
                Fr, mx = Mb @ T(0, 0, bt), 1
            else:
                Fr, mx = Mb @ R("Y", 180), -1
            rw = sh.polygon_ccw([(mx * x, y) for (x, y) in raw])
            ring_prism(trim, "brass", sh.offset_poly(rw, 0.015), sh.offset_poly(rw, 0.025), -0.001, 0.0025, M=Fr)
            ic = Fr @ T(mx * 0.075, 0, 0)
            if icon == "clock":
                ring_prism(trim, "brass", circle2d(0.036, 12), circle2d(0.027, 12), -0.001, 0.0035, M=ic)
                box(small, "brass_dark", (0.006, 0.024, 0.006), M=ic @ T(0, 0.011, 0.0), skip=("-z",))
                box(small, "brass_dark", (0.018, 0.006, 0.006), M=ic @ T(0.008, 0, 0.0), skip=("-z",))
            elif icon == "crystal":
                dia = [(0.0, -0.04), (0.027, 0.0), (0.0, 0.04), (-0.027, 0.0)]
                ring_prism(trim, "brass", dia, sh.offset_poly(dia, 0.008), -0.001, 0.0035, M=ic)
                prism(trim, "brass", [(0.0, -0.016), (0.011, 0.0), (0.0, 0.016), (-0.011, 0.0)], -0.001, 0.0045, M=ic)
            else:
                sh.gear(trim, "brass", 0.03, 6, 0.007, M=ic)
                prism(small, "brass_dark", circle2d(0.01, 6), 0.0, 0.0055, M=ic)
            # painted place name, centred between the pictogram and the arrow tip
            r0, r1 = 0.14, L - tip * 0.85
            em, gap = 0.092, 0.014
            wlen = len(word) * em + (len(word) - 1) * gap
            x0 = (r0 + r1) / 2 - wlen / 2
            if mx < 0:
                x0 = -((r0 + r1) / 2) - wlen / 2
            _paint_word(paint, "wood_dark", Fr, word, x0, -em / 2, em, gap)
        # bolts through the board into the post
        for by in (-0.055, 0.055):
            p = Mb @ Vector((0.0, by, bt + 0.0))
            n = Mb.to_3x3() @ Vector((0, 0, 1))
            rivet(small, "brass_dark", p, n, r=0.012, h=0.007)

    # pinned paper notice on the front of the post (slightly curled), scribbled lines, brass pin
    paper = kit.part("paper", smooth=60, recalc=False, occluder=False)
    zn, k_ = 1.0, 1.0 - 0.06 * 1.0 / ztop
    yp = -(a / 2) * k_ - 0.0015
    Mn = T(0, yp, zn) @ R("X", 90) @ R("Z", 4.0)      # local z -> -Y (out of the post face)
    nx, ny = 3, 3
    W_, H_ = 0.1, 0.14
    grid = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            u, v = i / nx, j / ny
            curl = 0.012 * max(0.0, u - 0.5) * 2 * max(0.0, 0.5 - v) * 2        # lower-right corner lifts
            curl += 0.003 * math.sin(math.pi * u)
            grid[i, j] = paper.bm.verts.new(Mn @ Vector((-W_ / 2 + W_ * u, -H_ / 2 + H_ * v, curl)))
    fq = [paper.bm.faces.new((grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
          for i in range(nx) for j in range(ny)]
    set_mat(paper, fq, "sml_paper")
    lines = [((-0.035, 0.045), (0.03, 0.045)), ((-0.04, 0.02), (0.038, 0.02)), ((-0.04, 0.0), (0.02, 0.0)),
             ((-0.04, -0.02), (0.035, -0.02)), ((-0.04, -0.04), (0.0, -0.04))]
    sh.stroke_quads(paper, "wood_dark", Mn @ T(0, 0, 0.0052), lines, sw=0.006, lift=0.0)
    rivet(small, "brass", Mn @ Vector((0, H_ / 2 - 0.012, 0.004)), Mn.to_3x3() @ Vector((0, 0, 1)), r=0.008, h=0.006, seg=6)

    # stones around the foot: three subdivided rocks (flattened where they meet the ground) + pebbles
    for i, (x, y, r, sc, rz) in enumerate(((0.2, -0.12, 0.14, (1.3, 1.0, 0.95), 20),
                                           (-0.21, 0.12, 0.16, (1.15, 1.3, 0.85), -35),
                                           (-0.14, -0.21, 0.11, (1.2, 1.0, 1.0), 60))):
        sh.blob(rock, "stone", r, loc=(0, 0, r * sc[2] * 0.12), scale=sc, subdiv=2, amount=0.32, seed=100 + i,
                floor=-0.01, M=T(x, y, 0) @ R("Z", rz), freq=2.4)
    for i, (x, y, r) in enumerate(((0.06, 0.24, 0.06), (0.27, 0.1, 0.05))):
        sh.blob(pebble, "stone", r, loc=(x, y, r * 0.3), scale=(1.2, 1.0, 0.8), subdiv=2, amount=0.2, seed=120 + i,
                floor=0.0)

    built = kit.build_parts(root)
    sh.bake_parts(built, distance=0.3, samples=48, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.3, dark=0.75))
    obj = kit.join_parts(built)
    sh.tint_islands(obj, {"wood", "wood_dark"}, lo=0.8, hi=1.0, seed=13, streak=0.12, streak_freq=10)
    sh.tint_islands(obj, {"stone"}, lo=0.75, hi=1.0, seed=17, hue=(0.95, 1.0, 1.06))
    return root


# name, builder, preview kwargs (passed to hp.render_hp)
PROPS = [
    ("prop_rest", build_rest, {}),
    ("prop_chest", build_chest, dict(elevation=25)),
    ("prop_crate", build_crate, {}),
    ("prop_barrel", build_barrel, {}),
    ("prop_signpost", build_signpost, {}),
]

# triangle budget per prop (user-chosen "medium" tier, 2026-10-11)
BUDGET = {
    "prop_rest": 12000,
    "prop_chest": 6000,
    "prop_crate": 3000,
    "prop_barrel": 4000,
    "prop_signpost": 4000,
}
