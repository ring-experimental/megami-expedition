"""Landmark: the stopped clock tower.

"에테르 평원 · 멈춘 시계탑" — the signature landmark of the field. Concept: stone shaft, brass/copper clock stage with
four white faces, black hands, a faint glow_amber ring, patina roof with a lantern and a gear vane.

Story details of this pass: the hands are frozen at 1:50 on every face; an aether-crystal overgrowth
(glow_cyan) jams the movement behind the open belfry arches and has burst the back dial, whose minute
hand slipped; hairline cracks on the front dial; ivy and moss creep up the west side.

Construction: coursed ashlar (individual chamfered stones over a mortar-coloured wall slab with real
openings cut through it), wrapping corner quoins, voussoir arches with keystones, moulded string
courses, corbelled balcony, octagonal brass piers, bell-cast roof with overlapping courses, dormers,
lantern with a bell, ogee cupola and a gear weather vane.

Builders for props.glb (assembled by model_props.py). The builder returns the top-level EMPTY
`prop_clocktower` (origin at its base centre on the ground, z = 0) with two mesh children:
    prop_clocktower_body   stone + metal + decals (10 materials)
    prop_clocktower_glow   glow_amber / glow_cyan (separate: glow meshes don't cast shadows in-game)

Test this group alone (no props.glb export):
    blender -b --factory-startup -P tools/blender/model_props.py -- --group=clocktower --previews [--back]
Test export to a scratch dir:  ... -- --group=clocktower --out=<dir>
Env CLK_FAST=1 -> cheap AO bake (iteration only).
"""
import math
import os
import random
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from mathutils import Matrix, Vector  # noqa: E402,F401
import numpy as np  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_clocktower_helpers as ck  # noqa: E402
from hp_clocktower_helpers import T, R, S, I4, FACE_OUT, frame_side  # noqa: E402

FAST = os.environ.get("CLK_FAST") == "1"

STONE, STONE_D = "clk_stone", "clk_stone_dark"
ROOF, MOSS = "clk_patina", "clk_moss"


def setup_mats():
    """Group-specific materials ('clk_*'); shared palette: brass, brass_dark, copper, black, white,
    wood_dark, glow_amber, glow_cyan  -> 12 materials in total."""
    get_mat(STONE, hex="#958a74", roughness=0.9)
    get_mat(STONE_D, hex="#504a43", roughness=0.95)
    get_mat(ROOF, hex="#5ea692", metallic=0.45, roughness=0.42)
    get_mat(MOSS, hex="#5d8a38", roughness=0.95)


# ---------------------------------------------------------------------------
# layout (metres).  Front = -Y (faces the road / player start), +X = east (steam pipes), -X = west (ivy)
# ---------------------------------------------------------------------------
Z_PL = 0.36            # plinth lower course top
Z_A0 = 0.70            # water-table top = stage A floor = door sill

STAGES = {
    "A": dict(z0=0.70, z1=3.85, hw=2.30, hin=1.92, rows=5, q=0.13, d=0.08, ch=0.045, gap=0.032,
              avg=0.95, L=0.92, S=0.52, qbev=0.045, dv=0.14),
    "B": dict(z0=4.28, z1=6.80, hw=2.20, hin=1.84, rows=5, q=0.095, d=0.055, ch=0.028, gap=0.024,
              avg=0.86, L=0.78, S=0.44, qbev=0.032, dv=0.105),
    "C": dict(z0=7.10, z1=8.62, hw=2.14, hin=1.70, rows=4, q=0.085, d=0.05, ch=0.026, gap=0.022,
              avg=0.84, L=0.72, S=0.40, qbev=0.03, dv=0.095),
}
Z_SLAB0, Z_SLAB1, HW_SLAB = 8.92, 9.14, 2.80
HW_K = 2.06            # clock stage copper wall
Z_CLK = 11.60          # clock centre
Z_FRZ0, Z_FRZ1 = 13.36, 13.56
Z_CORN1 = 13.98
HW_ROOF0 = 2.30
Z_ROOF1, HW_ROOF1 = 16.72, 0.44

HOUR_A, MIN_A = 55.0, 300.0          # frozen at 1:50 (clock angles, degrees clockwise from 12)
BROKEN_SECTOR = (118.0, 188.0)       # back dial burst open between ~4 and ~6 o'clock

DOOR = dict(type="arch", cx=0.0, w=1.36, sill=0.70, zs=2.55, vt=0.30, jw=(0.30, 0.19), nv=9, sill_stone=False)
SLIT = dict(type="arch", cx=0.0, w=0.40, sill=1.95, zs=2.95, vt=0.17, jw=(0.18, 0.12), nv=5)
ROSE = dict(type="round", cx=0.0, zc=5.55, r=0.52, vt=0.24, nv=12)
LANCET = dict(type="arch", cx=0.0, w=0.72, sill=4.62, zs=5.85, vt=0.20, jw=(0.20, 0.14), nv=7)
BELFRY = dict(type="arch", cx=0.0, w=1.20, sill=7.20, zs=7.78, vt=0.18, jw=(0.20, 0.13), nv=9)
OPENINGS = {
    "A": {0: [DOOR], 1: [SLIT], 2: [SLIT], 3: [SLIT]},
    "B": {0: [ROSE], 1: [LANCET], 2: [LANCET], 3: [LANCET]},
    "C": {0: [BELFRY], 1: [BELFRY], 2: [BELFRY], 3: [BELFRY]},
}


def roof_hw(t):
    """Bell-cast roof half width at parameter t (0 = eaves, 1 = lantern)."""
    return HW_ROOF1 + (HW_ROOF0 - HW_ROOF1) * (1 - t) ** 1.2


def roof_z(t):
    return Z_CORN1 + (Z_ROOF1 - Z_CORN1) * t


def roof_t_at(z):
    return (z - Z_CORN1) / (Z_ROOF1 - Z_CORN1)


# ---------------------------------------------------------------------------
# masonry
# ---------------------------------------------------------------------------

def _stone_tint(rng, add=0.0):
    """(brightness, warmth) variation of one stone."""
    t = rng.gauss(0.0, 0.065)
    if rng.random() < 0.09:
        t -= 0.11
    return (max(-0.24, min(0.12, t)) + add, rng.gauss(0.0, 0.035))


def _sub_intervals(segs, cut):
    c0, c1 = cut
    out = []
    for s0, s1 in segs:
        if c1 <= s0 or c0 >= s1:
            out.append((s0, s1))
            continue
        if c0 > s0:
            out.append((s0, c0))
        if c1 < s1:
            out.append((c1, s1))
    return out


def _opening_half(o, za, zb, row):
    """Half width (around o['cx']) the ashlar of row [za, zb] must leave free. Surround stones protrude
    more than the ashlar, so stones may run *under* them (no mortar gaps) but never into the opening."""
    za, zb = za + 0.02, zb - 0.02            # stones are inset by half a joint
    samples = [za + (zb - za) * i / 6 for i in range(7)]
    if o["type"] == "round":
        r, ro = o["r"], o["r"] + o["vt"]
        inner = max((math.sqrt(max(0.0, r * r - (z - o["zc"]) ** 2)) if abs(z - o["zc"]) < r else -1)
                    for z in samples)
        outer = min((math.sqrt(max(0.0, ro * ro - (z - o["zc"]) ** 2)) if abs(z - o["zc"]) < ro else 0.0)
                    for z in samples)
        if inner < 0 and outer <= 0:
            return 0.0
        return max(inner + 0.03, outer * 0.85)
    r = o["w"] / 2
    ro = r + o["vt"]
    zs, sill = o["zs"], o["sill"]
    sill_bot = sill - (0.10 if o.get("sill_stone", True) else 0.0)
    half = 0.0
    if zb > sill_bot + 1e-4 and za < zs:
        half = max(half, r + o["jw"][row % 2] * 0.55)
        if o.get("sill_stone", True) and za < sill:
            half = max(half, r + 0.10)
    if zb > zs and za < zs + ro + 0.12:
        inner = max((math.sqrt(max(0.0, r * r - (z - zs) ** 2)) if zs <= z < zs + r else -1) for z in samples)
        up = [z for z in samples if z >= zs]
        outer = min((math.sqrt(max(0.0, ro * ro - (z - zs) ** 2)) if z < zs + ro else 0.0) for z in up) if up else 0.0
        half = max(half, inner + 0.03, outer * 0.85)
    return half


def _fill_row(p, rng, M, xa, xb, za, zb, excl, st, row):
    """Running-bond course of chamfered ashlar between xa and xb (minus the opening exclusions)."""
    segs = [(xa, xb)]
    for cx, h in excl:
        if h > 0:
            segs = _sub_intervals(segs, (cx - h, cx + h))
    g, avg = st["gap"], st["avg"]
    for s0, s1 in segs:
        if s1 - s0 < 0.12:
            continue
        cuts = [s0]
        x = s0 + (avg * rng.uniform(0.42, 0.62) if row % 2 else avg * rng.uniform(0.8, 1.15))
        while x < s1 - avg * 0.42:
            cuts.append(x)
            x += avg * rng.uniform(0.72, 1.28)
        cuts.append(s1)
        for a, b in zip(cuts, cuts[1:]):
            if b - a < 0.08:
                continue
            d = st["d"] * rng.uniform(0.8, 1.2)
            ck.fbox(p, STONE, a + g / 2, b - g / 2, -d, 0.02, za + g / 2, zb - g / 2,
                    st["ch"] * rng.uniform(0.8, 1.25), M=M, tint=_stone_tint(rng))


def notched_top(x0, x1, z0, z1, cx, r, n=10):
    """Wall band whose top edge has a semicircular notch going down (lower half of a round window)."""
    pts = [(x0, z0), (x1, z0), (x1, z1), (cx + r, z1)]
    for i in range(1, n):
        a = -math.pi * i / n
        pts.append((cx + r * math.cos(a), z1 + r * math.sin(a)))
    pts += [(cx - r, z1), (x0, z1)]
    return pts


def wall_slab(p, M, hw, z0, z1, t, ops):
    """Mortar-coloured wall slab (it shows in the joints between the stones) with real openings. The
    opening reveals are stone-coloured and sit 1.5 cm inside the surround stones -> one continuous soffit."""
    x0, x1 = -hw, hw
    if not ops:
        ck.prism(p, STONE_D, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 0.0, t, M)
        return
    o = ops[0]
    e = 0.015
    if o["type"] == "arch":
        sill = o["sill"]
        if sill > z0 + 1e-3:
            ck.prism(p, STONE_D, [(x0, z0), (x1, z0), (x1, sill), (x0, sill)], 0.0, t, M)
        ck.prism(p, STONE_D, ck.notched_wall(x0, x1, sill, z1, [(o["cx"], o["w"] - 2 * e, o["zs"])], n=12), 0.0, t, M,
                 side_mat=STONE)
    else:
        zc, r = o["zc"], o["r"] - e
        ck.prism(p, STONE_D, notched_top(x0, x1, z0, zc, o["cx"], r, n=10), 0.0, t, M, side_mat=STONE)
        ck.prism(p, STONE_D, ck.notched_wall(x0, x1, zc, z1, [(o["cx"], 2 * r, zc)], n=10), 0.0, t, M,
                 side_mat=STONE)


def voussoirs(p, rng, M, cx, zc, r, ro, a0, a1, n, dv, depth_in, key=None, sub=2, gap=0.025, ch=0.022):
    """Ring of wedge stones between radii r and ro, angles a0..a1 (radians, 0 = +x, CCW)."""
    for j in range(n):
        b0 = a0 + (a1 - a0) * j / n
        b1 = a0 + (a1 - a0) * (j + 1) / n
        gi, go = gap / (2 * r), gap / (2 * ro)
        is_key = key is not None and j == key
        ro_j = ro + (0.09 if is_key else 0.0)
        pts = []
        for i in range(sub + 1):
            a = b0 + gi + (b1 - b0 - 2 * gi) * i / sub
            pts.append((cx + r * math.cos(a), zc + r * math.sin(a)))
        for i in range(sub + 1):
            a = b1 - go - (b1 - b0 - 2 * go) * i / sub
            pts.append((cx + ro_j * math.cos(a), zc + ro_j * math.sin(a)))
        ck.chamfer_prism(p, STONE, pts, -(dv + (0.035 if is_key else 0.0)), depth_in, ch, M=M,
                         tint=_stone_tint(rng, 0.05))


def opening_surround(p, rng, M, o, st):
    rows, z0, z1 = st["rows"], st["z0"], st["z1"]
    h = (z1 - z0) / rows
    dv, g = st["dv"], st["gap"]
    t = st["hw"] - st["hin"]
    if o["type"] == "round":
        voussoirs(p, rng, M, o["cx"], o["zc"], o["r"], o["r"] + o["vt"], -math.pi / 2, 1.5 * math.pi, o["nv"],
                  dv, 0.06, key=o["nv"] // 2, sub=2)
        return
    r = o["w"] / 2
    cx = o["cx"]
    for i in range(rows):
        za, zb = max(z0 + i * h, o["sill"]), min(z0 + (i + 1) * h, o["zs"])
        if zb - za < 0.08:
            continue
        jw = o["jw"][i % 2]
        for s in (-1, 1):
            xa, xb = sorted((cx + s * r, cx + s * (r + jw)))
            ck.fbox(p, STONE, xa, xb, -dv, 0.06, za + g / 2, zb - g / 2, 0.024, M=M, tint=_stone_tint(rng, 0.05))
    voussoirs(p, rng, M, cx, o["zs"], r, r + o["vt"], 0.0, math.pi, o["nv"], dv, 0.06, key=o["nv"] // 2,
              sub=2 if r > 0.65 else 1)
    if o.get("sill_stone", True):
        ck.fbox(p, STONE, cx - r - 0.13, cx + r + 0.13, -(dv + 0.05), t - 0.01, o["sill"] - 0.11, o["sill"], 0.025,
                M=M, tint=0.03)


def stage_walls(p, rng, st, openings):
    hw, hin, z0, z1, rows = st["hw"], st["hin"], st["z0"], st["z1"], st["rows"]
    t = hw - hin
    h = (z1 - z0) / rows
    g = st["gap"]
    if st.get("core", True):
        ck.box_xyz(p, STONE_D, -hin - 0.005, hin + 0.005, -hin - 0.005, hin + 0.005, z0, z1)
    # corner quoins (long/short alternating, wrapping the corner)
    for i in range(rows):
        za, zb = z0 + i * h + g / 2, z0 + (i + 1) * h - g / 2
        E0 = st["L"] if i % 2 == 0 else st["S"]
        E1 = st["S"] if i % 2 == 0 else st["L"]
        for sx in (-1, 1):
            for sy in (-1, 1):
                xa, xb = sorted((sx * (hw - E0), sx * (hw + st["q"])))
                ya, yb = sorted((sy * (hw - E1), sy * (hw + st["q"])))
                ck.box_xyz(p, STONE, xa, xb, ya, yb, za, zb, bev=st["qbev"], seg=1, tint=_stone_tint(rng, 0.06))
    for k in range(4):
        M = frame_side(k, hw)
        ops = openings.get(k, [])
        wall_slab(p, M, hw, z0, z1, t, ops)
        for i in range(rows):
            za, zb = z0 + i * h, z0 + (i + 1) * h
            E = (st["L"] if i % 2 == 0 else st["S"]) if k % 2 == 0 else (st["S"] if i % 2 == 0 else st["L"])
            excl = [(o["cx"], _opening_half(o, za, zb, i)) for o in ops]
            _fill_row(p, rng, M, -hw + E * 0.6, hw - E * 0.6, za, zb, excl, st, i)
        for o in ops:
            opening_surround(p, rng, M, o, st)


def string_course(p, z0, z1, hw_lo, hw_hi, proj):
    """Moulded string course: fillet, cove, corona and a sloped wash up to the set-back upper stage."""
    hz = z1 - z0
    prof = [(z0, hw_hi - 0.12), (z0, hw_lo + 0.10), (z0 + hz * 0.10, hw_lo + 0.13),
            (z0 + hz * 0.22, hw_lo + proj * 0.62), (z0 + hz * 0.34, hw_lo + proj * 0.88),
            (z0 + hz * 0.40, hw_lo + proj), (z0 + hz * 0.58, hw_lo + proj),
            (z0 + hz * 0.64, hw_lo + proj - 0.03), (z1, hw_hi + 0.01), (z1, hw_hi - 0.12)]
    ck.rlathe(p, STONE, prof, tints=[0.0, -0.04, 0.0, 0.03, 0.05, 0.06, 0.07, 0.07, -0.06, -0.06])


# ---------------------------------------------------------------------------
# base + shaft
# ---------------------------------------------------------------------------

def build_base(p, rng):
    """Plinth lower course (big rough blocks), sloped water table, front steps with cheek walls."""
    ck.box_xyz(p, STONE_D, -2.70, 2.70, -2.70, 2.70, 0.0, Z_PL)
    for k in range(4):
        M = frame_side(k, 2.70)
        segs = [(-2.84, 2.84)] if k % 2 == 0 else [(-2.62, 2.62)]
        if k == 0:
            segs = _sub_intervals(segs, (-1.24, 1.24))
        for s0, s1 in segs:
            n = max(1, round((s1 - s0) / 0.95))
            cuts = [s0] + [s0 + (s1 - s0) * (i + rng.uniform(-0.18, 0.18)) / n for i in range(1, n)] + [s1]
            for a, b in zip(cuts, cuts[1:]):
                ck.fbox(p, STONE_D, a + 0.02, b - 0.02, -0.12, 0.25, 0.0, Z_PL - 0.02, 0.05, M=M,
                        tint=_stone_tint(rng, 0.05))
    # water table (sloped wash) — per side; the front run is broken by the steps
    prof = [(Z_PL - 0.02, 0.0), (Z_PL - 0.02, 0.32), (Z_PL + 0.02, 0.345), (Z_PL + 0.13, 0.345),
            (Z_PL + 0.16, 0.32), (Z_A0, 0.14), (Z_A0, 0.0)]
    hwA = STAGES["A"]["hw"]
    for k in range(4):
        M = frame_side(k, hwA)
        if k == 0:
            ck.mold_run(p, STONE, prof, -hwA, -0.98, M=M, miter0=True, tint=0.03)
            ck.mold_run(p, STONE, prof, 0.98, hwA, M=M, miter1=True, tint=0.03)
        else:
            ck.mold_run(p, STONE, prof, -hwA, hwA, M=M, miter0=True, miter1=True, tint=0.03)
    # steps + landing + cheek walls
    M = frame_side(0, hwA)
    th = Z_A0 / 3
    for i, (y0, y1) in enumerate(((-0.78, -0.54), (-0.54, -0.30), (-0.30, 0.05))):
        ck.box_xyz(p, STONE_D if i < 2 else STONE, -0.98, 0.98, y0, y1, 0.0, th * (i + 1), M=M, bev=0.03, seg=1,
                   tint=0.06 - 0.04 * i)
    for s in (-1, 1):
        prof2 = [(0.08, 0.0), (-0.82, 0.0), (-0.82, 0.30), (-0.76, 0.34), (-0.30, 0.80), (0.08, 0.80)]
        ck.prism_x(p, STONE, prof2, s * 0.98, s * 1.26, M=M, bev=0.025, seg=1, tint=0.02)


def build_shaft(p, rng):
    for name in ("A", "B", "C"):
        st = STAGES[name]
        if name == "C":
            st = dict(st, core=False)          # open belfry chamber
        stage_walls(p, rng, st, OPENINGS[name])
    A, B, C = STAGES["A"], STAGES["B"], STAGES["C"]
    ck.box_xyz(p, STONE_D, -1.95, 1.95, -1.95, 1.95, A["z1"] - 0.01, B["z0"] + 0.01)
    ck.box_xyz(p, STONE_D, -1.88, 1.88, -1.88, 1.88, B["z1"] - 0.01, C["z0"])
    ck.box_xyz(p, STONE_D, -1.75, 1.75, -1.75, 1.75, C["z1"], Z_SLAB0 + 0.02)
    string_course(p, A["z1"], B["z0"], A["hw"], B["hw"], 0.25)
    string_course(p, B["z1"], C["z0"], B["hw"], C["hw"], 0.19)
    # corbel band + consoles under the balcony
    ck.rlathe(p, STONE, [(C["z1"] - 0.02, 2.0), (C["z1"] - 0.02, 2.22), (C["z1"] + 0.05, 2.25),
                         (C["z1"] + 0.07, 2.21), (Z_SLAB0, 2.18), (Z_SLAB0, 2.0)], tints=[0, 0, 0.05, 0.05, -0.04, 0])
    zb = C["z1"] - 0.10
    prof = [(0.06, zb), (0.06, Z_SLAB0 + 0.01), (-0.64, Z_SLAB0 + 0.01), (-0.64, Z_SLAB0 - 0.05)]
    for i in range(1, 7):
        a = i / 6 * math.pi / 2
        prof.append((-0.06 - 0.56 * math.cos(a), Z_SLAB0 - 0.05 - (Z_SLAB0 - 0.05 - zb) * math.sin(a)))
    for k in range(4):
        M = frame_side(k, C["hw"])
        for x in (-1.80, -1.08, -0.36, 0.36, 1.08, 1.80):
            ck.prism_x(p, STONE, prof, x - 0.11, x + 0.11, M=M, tint=0.04 + rng.uniform(-0.04, 0.03))
        Mc = Matrix.Rotation(math.radians(90 * k + 45), 4, "Z") @ T(0, -C["hw"] * math.sqrt(2) + 0.12, 0)
        profc = [(y * 1.45 if y < 0 else y, z) for (y, z) in prof]
        ck.prism_x(p, STONE, profc, -0.13, 0.13, M=Mc, tint=0.06)
    # balcony slab with moulded edge
    ck.rlathe(p, STONE, [(Z_SLAB0, 1.9), (Z_SLAB0, HW_SLAB - 0.06), (Z_SLAB0 + 0.04, HW_SLAB),
                         (Z_SLAB1 - 0.07, HW_SLAB), (Z_SLAB1 - 0.03, HW_SLAB - 0.02), (Z_SLAB1, HW_SLAB - 0.05),
                         (Z_SLAB1, 1.9)], tints=[0, -0.06, 0.03, 0.05, 0.06, 0.04, 0.0])


# ---------------------------------------------------------------------------
# door + lanterns
# ---------------------------------------------------------------------------

def build_door(p, pg, rng):
    A = STAGES["A"]
    M = frame_side(0, A["hw"])
    o = DOOR
    r, zs, z0 = o["w"] / 2, o["zs"], o["sill"]
    yb = 0.22
    for s in (-1, 1):
        for i in range(4):                                   # planks
            xa, xb = sorted((s * (0.006 + i * 0.168), s * (0.006 + (i + 1) * 0.168 - 0.008)))
            ck.fbox(p, "wood_dark", xa, xb, yb, yb + 0.08, z0 + 0.01, zs - 0.01, 0.014, M=M,
                    tint=rng.uniform(-0.14, 0.08))
        for zz in (0.98, 1.66, 2.30):                        # iron straps, fleur ends, studs
            xa, xb = sorted((s * 0.06, s * 0.66))
            ck.fbox(p, "black", xa, xb, yb - 0.022, yb + 0.004, zz - 0.04, zz + 0.04, 0.008, M=M)
            ck.chamfer_prism(p, "black", [(s * 0.02, zz), (s * 0.075, zz - 0.07), (s * 0.13, zz), (s * 0.075, zz + 0.07)],
                             yb - 0.024, yb + 0.004, 0.006, M=M)
            for j in range(2):
                stud(p, M @ T(s * (0.26 + j * 0.24), yb - 0.022, zz) @ FACE_OUT)
        Mr = M @ T(s * 0.13, yb - 0.01, 1.48)                # ring pulls
        ck.lathe_m(p, "brass", [(0.0, 0.065), (0.014, 0.06), (0.024, 0.028), (0.03, 0.0)], seg=10, M=Mr @ FACE_OUT,
                   cap0=False)
        ck.torus_m(p, "brass", 0.072, 0.012, seg=14, seg2=5, M=Mr @ T(0, -0.03, -0.068) @ FACE_OUT)
    # transom + fanlight with a brass sunburst
    ck.fbox(p, "brass_dark", -r, r, yb - 0.04, yb + 0.1, zs - 0.04, zs + 0.04, 0.012, M=M)
    ck.poly2d(p, "black", ck.arch_outline(0, zs, 2 * r, zs, n=20, close_bottom=False), yb + 0.06, M)
    ck.torus_m(p, "brass", r * 0.62, 0.022, seg=14, seg2=5, M=M @ T(0, yb + 0.02, zs) @ FACE_OUT, arc=(0, 180))
    for i in range(5):
        a = math.radians(30 + 30 * i)
        L = r - 0.03
        ck.cbox(p, "brass", (L, 0.03, 0.025), loc=(math.cos(a) * L / 2, yb + 0.03, zs + math.sin(a) * L / 2), M=M,
                rot=(0, -math.degrees(a), 0))
    ck.gear(p, "brass", 0.15, 0.19, 10, 0.04, M=M @ T(0, yb, zs) @ FACE_OUT, back=False)
    ck.fbox(p, "brass_dark", -r, r, -0.06, yb + 0.06, z0 - 0.01, z0 + 0.025, 0.01, M=M)      # threshold
    ro = r + o["vt"]
    ck.gear(p, "brass", 0.085, 0.115, 8, 0.03, M=M @ T(0, -A["dv"] - 0.05, zs + ro - 0.02) @ FACE_OUT, back=False)
    for s in (-1, 1):
        wall_lantern(p, pg, M, s * 1.22, 2.32)


def stud(p, M):
    ck.lathe_m(p, "black", [(0.0, 0.02), (0.012, 0.014), (0.02, 0.0)], seg=4, M=M, phase=math.pi / 4, cap0=False)


def wall_lantern(p, pg, M, x, z):
    """Wall bracket lantern with a glow_cyan aether bulb (matches the street lamps)."""
    yw = -STAGES["A"]["d"] - 0.005
    ck.fbox(p, "black", x - 0.07, x + 0.07, yw - 0.03, yw + 0.03, z + 0.02, z + 0.30, 0.01, M=M)
    pts = [(x, yw - 0.02, z + 0.16), (x, -0.30, z + 0.16)] + ck.bend_pts((x, -0.30, z + 0.16), (x, -0.44, z + 0.16),
                                                                        (x, -0.44, z + 0.02), 0.08, n=3)
    ck.tube(p, "black", pts, r=0.016, seg=6, M=M)
    ck.torus_m(p, "black", 0.06, 0.01, seg=8, seg2=4, M=M @ T(x, -0.2, z + 0.10) @ R("Y", 90), arc=(0, 270))
    c = M @ T(x, -0.44, z - 0.14)
    ck.lathe_m(p, "brass", [(0.10, 0.0), (0.10, 0.12), (0.12, 0.125), (0.14, 0.11), (0.17, 0.035), (0.19, 0.0)],
               seg=6, M=c, phase=math.pi / 6)
    ck.lathe_m(p, "brass", [(-0.21, 0.0), (-0.16, 0.03), (-0.13, 0.06), (-0.11, 0.115), (-0.10, 0.115),
                            (-0.10, 0.0)], seg=6, M=c, phase=math.pi / 6)
    ck.lathe_m(pg, "glow_cyan", [(-0.10, 0.0), (-0.10, 0.075), (0.10, 0.085), (0.10, 0.0)], seg=6, M=c,
               phase=math.pi / 6)
    for j in range(6):
        a = math.pi / 6 + j * math.pi / 3
        ck.cbox(p, "brass", (0.016, 0.016, 0.2), loc=(0.098 * math.cos(a), 0.098 * math.sin(a), 0.0), M=c)


# ---------------------------------------------------------------------------
# windows
# ---------------------------------------------------------------------------

def _clip_seg_to_rect(a, b, x0, x1, z0, z1):
    """Liang-Barsky clip of segment a-b (2D Vectors) to a rectangle; returns (p, q) or None."""
    dx, dz = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p_, q_ in ((-dx, a.x - x0), (dx, x1 - a.x), (-dz, a.y - z0), (dz, z1 - a.y)):
        if abs(p_) < 1e-12:
            if q_ < 0:
                return None
            continue
        t = q_ / p_
        if p_ < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    pa = Vector((a.x + dx * t0, a.y + dz * t0))
    pb = Vector((a.x + dx * t1, a.y + dz * t1))
    if (pb - pa).length < 0.03:
        return None
    return (tuple(pa), tuple(pb))


def build_windows(p, pg, rng):
    A, B = STAGES["A"], STAGES["B"]
    # slit windows (stage A sides/back): dark pane + iron bars
    for k in (1, 2, 3):
        M = frame_side(k, A["hw"])
        o = SLIT
        t = A["hw"] - A["hin"]
        r = o["w"] / 2
        ck.poly2d(p, "black", ck.arch_outline(0, o["sill"], o["w"], o["zs"], n=8), t - 0.03, M)
        for xx in (-0.07, 0.07):
            ck.box_xyz(p, "black", xx - 0.013, xx + 0.013, t - 0.16, t - 0.13, o["sill"], o["zs"] + 0.15, M=M)
        ck.box_xyz(p, "black", -r, r, t - 0.16, t - 0.13, o["sill"] + 0.55, o["sill"] + 0.58, M=M)
    # lancets (stage B sides/back): dark leaded glass in a brass frame
    for k in (1, 2, 3):
        M = frame_side(k, B["hw"])
        o = LANCET
        t = B["hw"] - B["hin"]
        r = o["w"] / 2
        yp = t - 0.07
        ck.poly2d(p, "black", ck.arch_outline(0, o["sill"], o["w"], o["zs"], n=12), yp + 0.02, M)
        ck.torus_m(p, "brass_dark", r - 0.02, 0.022, seg=12, seg2=4, M=M @ T(0, yp, o["zs"]) @ FACE_OUT, arc=(0, 180))
        for s in (-1, 1):
            ck.box_xyz(p, "brass_dark", s * (r - 0.04), s * (r - 0.0), yp - 0.02, yp + 0.02, o["sill"], o["zs"], M=M)
        ck.box_xyz(p, "brass_dark", -0.018, 0.018, yp - 0.025, yp + 0.02, o["sill"], o["zs"] + r - 0.03, M=M)
        ck.box_xyz(p, "brass_dark", -r, r, yp - 0.025, yp + 0.02, o["zs"] - 0.02, o["zs"] + 0.02, M=M)
        h0, h1 = o["sill"], o["zs"]
        for i in range(-4, 6):                               # leaded diamond lattice
            for sgn in (-1, 1):
                a = Vector((i * 0.17 * sgn - 0.5 * sgn, h0))
                b = a + Vector((sgn * 1.0, 1.0)) * 1.3
                seg = _clip_seg_to_rect(a, b, -r + 0.02, r - 0.02, h0 + 0.01, h1 - 0.02)
                if seg:
                    ck.bar2d(p, "brass_dark", seg[0], seg[1], 0.01, yp + 0.012, M)
    # rose window (stage B front): amber glass behind brass gear tracery
    M = frame_side(0, B["hw"])
    o = ROSE
    t = B["hw"] - B["hin"]
    zc, r = o["zc"], o["r"]
    ck.disc(pg, "glow_amber", r + 0.01, t - 0.04, M=M @ T(0, 0, zc), seg=24)
    ck.gear_wheel(p, "brass", r * 0.66, 14, 0.05, M=M @ T(0, t - 0.16, zc) @ FACE_OUT, spokes=6, rim=0.2, hub=0.26,
                  tooth=0.05, back=False)
    ck.torus_m(p, "brass_dark", r - 0.03, 0.03, seg=24, seg2=4, M=M @ T(0, t - 0.12, zc) @ FACE_OUT)
    for i in range(12):
        a = 2 * math.pi * i / 12
        ck.cbox(p, "brass_dark", (0.03, 0.03, 0.12), loc=(math.cos(a) * (r - 0.1), t - 0.13, zc + math.sin(a) * (r - 0.1)),
                M=M, rot=(0, -math.degrees(a) + 90, 0))


# ---------------------------------------------------------------------------
# belfry: the jammed movement
# ---------------------------------------------------------------------------

def crystal(p, mat, base, direction, length, r, seg=6, spin=0.0):
    """Aether crystal shard: hexagonal prism tapering to a point, from base along direction."""
    d = Vector(direction).normalized()
    q = d.to_track_quat("Z", "Y")
    M = Matrix.Translation(Vector(base)) @ q.to_matrix().to_4x4() @ Matrix.Rotation(spin, 4, "Z")
    h = length * 0.72
    ck.lathe_m(p, mat, [(-0.02, 0.0), (-0.02, r * 0.75), (h, r), (length, 0.0)], seg=seg, M=M)


def build_belfry(p, pg, rng):
    """Open belfry stage: the clock movement behind the arches, jammed by an aether-crystal growth."""
    C = STAGES["C"]
    zc = 7.84
    ck.box_xyz(p, "black", -0.56, 0.56, -0.56, 0.56, C["z0"], C["z1"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            ck.box_xyz(p, "brass_dark", sx * 0.56 - 0.05, sx * 0.56 + 0.05, sy * 0.56 - 0.05, sy * 0.56 + 0.05,
                       C["z0"], C["z1"])
    for k in range(4):
        M = frame_side(k, C["hw"])
        yg = C["hw"] - 0.66
        side = 1 if k % 2 == 0 else -1
        ck.gear_wheel(p, "brass", 0.47, 16, 0.06, M=M @ T(0, yg, zc) @ FACE_OUT, spokes=4, rim=0.16, hub=0.2,
                      tooth=0.075, hub_mat="brass_dark", phase=rng.uniform(0, 0.3), back=False)
        ang = math.radians(42 * side)
        dc = 0.47 + 0.16 + 0.06
        px, pz = math.sin(ang) * dc, zc + math.cos(ang) * dc
        ck.gear(p, "brass_dark", 0.16, 0.22, 9, 0.08, M=M @ T(px, yg - 0.05, pz) @ FACE_OUT, back=False)
        ck.cbox(p, "brass", (0.05, 0.05, C["z1"] - pz), loc=(px, yg + 0.02, (pz + C["z1"]) / 2), M=M)
    # the jam: crystal growth spilling over the front sill ...
    M = frame_side(0, C["hw"])
    R3 = M.to_3x3()
    base = M @ Vector((0.16, 0.34, BELFRY["sill"] - 0.02))
    for dvec, L, rr in (((0.25, -0.7, 0.55), 0.62, 0.075), ((-0.1, -0.9, 0.35), 0.55, 0.065),
                        ((0.5, -0.6, 0.3), 0.42, 0.055), ((0.05, -0.3, 1.0), 0.66, 0.07),
                        ((-0.4, -0.5, 0.6), 0.38, 0.05), ((0.3, -0.95, 0.05), 0.48, 0.05)):
        crystal(pg, "glow_cyan", base + R3 @ Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0)),
                R3 @ Vector(dvec), L, rr, spin=rng.uniform(0, 1))
    # ... and wedged into the wheel / pinion mesh point
    mesh_pt = M @ Vector((math.sin(math.radians(42)) * 0.52, C["hw"] - 0.75, zc + math.cos(math.radians(42)) * 0.52))
    for dvec, L, rr in (((0.2, -1.0, 0.3), 0.36, 0.045), ((-0.3, -1.0, 0.1), 0.3, 0.04), ((0.5, -0.8, -0.2), 0.26, 0.035)):
        crystal(pg, "glow_cyan", mesh_pt, R3 @ Vector(dvec), L, rr, spin=rng.uniform(0, 1))


# ---------------------------------------------------------------------------
# balcony railing
# ---------------------------------------------------------------------------

def post(p, x, y, z0, z1, w=0.07):
    ck.box_xyz(p, "brass_dark", x - w / 2, x + w / 2, y - w / 2, y + w / 2, z0, z1 + 0.02)
    ck.lathe_m(p, "brass", [(z1 + 0.02, w * 0.62), (z1 + 0.05, w * 0.4), (z1 + 0.09, w * 0.64),
                            (z1 + 0.13, w * 0.5), (z1 + 0.16, 0.0)], seg=8 if w > 0.08 else 6, M=T(x, y, 0),
               phase=math.pi / 8, cap0=False)


def build_balcony_rail(p):
    z0, z1 = Z_SLAB1, Z_SLAB1 + 0.74
    hr = HW_SLAB - 0.09
    for sx in (-1, 1):
        for sy in (-1, 1):
            post(p, sx * hr, sy * hr, z0, z1, w=0.1)
    for k in range(4):
        M = frame_side(k, hr)
        for x in (-0.92, 0.92):
            c = M @ Vector((x, 0, 0))
            post(p, c.x, c.y, z0, z1)
        ck.tube(p, "brass", [(-hr, 0, z1 - 0.02), (hr, 0, z1 - 0.02)], r=0.03, seg=8, M=M, cap0=False, cap1=False)
        ck.box_xyz(p, "black", -hr, hr, -0.02, 0.02, z0 + 0.07, z0 + 0.11, M=M)
        ck.box_xyz(p, "black", -hr, hr, -0.015, 0.015, z1 - 0.12, z1 - 0.09, M=M)
        n = 24
        for i in range(1, n):
            x = -hr + 2 * hr * i / n
            if any(abs(x - xp) < 0.07 for xp in (-0.92, 0.92)):
                continue
            ck.tube(p, "black", [(x, 0, z0 + 0.09), (x, 0, z1 - 0.06)], r=0.0155, seg=4, M=M, cap0=False, cap1=False)
        ck.torus_m(p, "black", 0.13, 0.014, seg=12, seg2=3, M=M @ T(0.0, 0, (z0 + z1) / 2 - 0.02) @ FACE_OUT)


# ---------------------------------------------------------------------------
# clock stage + faces
# ---------------------------------------------------------------------------

def build_clock_stage(p, pg, rng):
    z0 = Z_SLAB1
    ck.box_xyz(p, "copper", -HW_K, HW_K, -HW_K, HW_K, z0, Z_FRZ1)
    ck.rlathe(p, "brass_dark", [(z0, 1.9), (z0, HW_K + 0.14), (z0 + 0.12, HW_K + 0.14), (z0 + 0.16, HW_K + 0.09),
                                (z0 + 0.22, HW_K + 0.06), (z0 + 0.22, 1.9)])
    ck.rlathe(p, "brass_dark", [(9.76, 1.9), (9.76, HW_K + 0.04), (9.82, HW_K + 0.05), (9.84, HW_K + 0.03),
                                (9.84, 1.9)])
    ck.rlathe(p, "brass_dark", [(Z_FRZ0, 1.9), (Z_FRZ0, HW_K + 0.03), (Z_FRZ1, HW_K + 0.03), (Z_FRZ1, 1.9)])
    ck.rlathe(p, "brass", [(Z_FRZ1, 1.9), (Z_FRZ1, HW_K + 0.05), (Z_FRZ1 + 0.10, HW_K + 0.05),
                           (Z_FRZ1 + 0.10, HW_K + 0.16), (Z_FRZ1 + 0.14, HW_K + 0.20), (Z_FRZ1 + 0.20, HW_K + 0.32),
                           (Z_FRZ1 + 0.26, HW_K + 0.44), (Z_FRZ1 + 0.31, HW_K + 0.52), (Z_FRZ1 + 0.36, HW_K + 0.56),
                           (Z_CORN1 - 0.03, HW_K + 0.56), (Z_CORN1, HW_K + 0.54), (Z_CORN1, 1.9)],
              tints=[0, 0, -0.1, -0.1, -0.05, 0, 0.02, 0.04, 0.05, 0.05, 0.05, 0])
    for k in range(4):                                        # dentils under the cornice
        M = frame_side(k, HW_K + 0.05)
        for i in range(13):
            x = -1.92 + i * 0.32
            ck.box_xyz(p, "brass", x - 0.065, x + 0.065, -0.09, 0.0, Z_FRZ1, Z_FRZ1 + 0.095, M=M)
    for sx in (-1, 1):                                        # octagonal corner piers
        for sy in (-1, 1):
            prof = [(z0, 0.0), (z0, 0.30), (z0 + 0.34, 0.30), (z0 + 0.40, 0.245), (10.72, 0.245),
                    (10.75, 0.272), (10.80, 0.245), (12.52, 0.245), (12.55, 0.272), (12.60, 0.245),
                    (Z_FRZ0 - 0.12, 0.245), (Z_FRZ0 - 0.05, 0.29), (Z_FRZ1, 0.30), (Z_FRZ1, 0.0)]
            ck.lathe_m(p, "brass_dark", prof, seg=8, M=T(sx * (HW_K + 0.04), sy * (HW_K + 0.04), 0),
                       phase=math.pi / 8)
    for k in range(4):
        M = frame_side(k, HW_K)
        for s in (-1, 1):
            ck.fbox(p, "brass_dark", s * 1.86 - 0.05, s * 1.86 + 0.05, -0.03, 0.0, 9.84, Z_FRZ0, 0.012, M=M)
        clock_face(p, pg, frame_side(k, HW_K, Z_CLK), k, rng)


def hand(p, kind, angle_deg, y_back, y_front, F):
    """Black ornate hand + white 'pierced' dots (decals), rotated clockwise by angle_deg."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)

    def rot(x, z):
        return (x * ca + z * sa, -x * sa + z * ca)
    ck.prism(p, "black", [rot(x, z) for x, z in ck.hand_outline(kind)], y_front, y_back, F, cap_back=False)
    holes = ((0.0, 0.556, 0.044), (0.0, -0.20, 0.032)) if kind == "hour" else ((0.0, 0.965, 0.022), (0.0, -0.28, 0.026))
    for hx, hz, hr in holes:
        cx, cz = rot(hx, hz)
        ck.disc(p, "white", hr, y_front - 0.002, M=F @ T(cx, 0, cz), seg=10)


def clock_face(p, pg, F, k, rng):
    broken = k == 2
    Fo = F @ FACE_OUT                      # local Z = out of the wall
    ck.gear(p, "brass", 1.60, 1.76, 24, 0.10, r_in=1.36, M=Fo @ T(0, 0, 0.05), back=False, inner=False,
            phase=math.pi / 24)
    ck.lathe_m(p, "brass", [(0.10, 1.585), (0.185, 1.56), (0.205, 1.46), (0.13, 1.385)], seg=40, M=Fo, closed=True)
    y_dial = -0.11
    if not broken:
        ck.lathe_m(p, "white", [(0.0, 1.31), (0.11, 1.31), (0.11, 0.0)], seg=40, M=Fo, cap0=False)
    else:
        a0, a1 = BROKEN_SECTOR
        pts = []
        n = 40
        for i in range(n + 1):
            c = math.radians(a1 + (360 - (a1 - a0)) * i / n)
            pts.append((1.31 * math.sin(c), 1.31 * math.cos(c)))
        jr = random.Random(5)
        for i in range(1, 9):
            c = math.radians(a0 + (a1 - a0) * i / 9)
            rr = 0.42 + 0.35 * abs(math.sin(i * 1.7)) + jr.uniform(-0.08, 0.08) + (0.12 if i % 2 else 0.0)
            pts.append((rr * math.sin(c), rr * math.cos(c)))
        ck.prism(p, "white", pts, y_dial, 0.0, F)
        # dark interior, a buried wheel, crystals bursting out
        ck.disc(p, "black", 1.32, -0.004, M=F, seg=32)
        ck.gear_wheel(p, "brass", 0.42, 16, 0.05, M=F @ T(0.38, -0.05, -0.72) @ FACE_OUT, spokes=5, rim=0.18,
                      tooth=0.06, hub_mat="brass_dark", back=False)
        base = F @ Vector((0.55, -0.02, -0.82))
        R3 = F.to_3x3()
        for dvec, L, rr in (((0.5, -1.0, -0.4), 0.72, 0.085), ((0.9, -0.6, -0.1), 0.55, 0.07),
                            ((0.1, -1.0, -0.8), 0.6, 0.075), ((0.7, -0.9, 0.35), 0.42, 0.055),
                            ((-0.2, -1.0, -0.3), 0.38, 0.05), ((1.0, -0.4, -0.7), 0.46, 0.06)):
            crystal(pg, "glow_cyan", base, R3 @ Vector(dvec), L, rr, spin=rng.uniform(0, 1))
        # dial shards fallen onto the balcony
        for i in range(5):
            sx, sy = rng.uniform(-1.1, 1.1), rng.uniform(-0.55, -0.15)
            c = F @ Vector((sx, sy, Z_SLAB1 + 0.005 - Z_CLK))
            ck.prism(p, "white", [(0, 0), (rng.uniform(0.12, 0.22), rng.uniform(-0.04, 0.04)),
                                  (rng.uniform(0.02, 0.1), rng.uniform(0.08, 0.15))], -0.006, 0.006,
                     T(*c) @ R("Z", rng.uniform(0, 360)) @ R("X", 90))
    yd = y_dial - 0.008                     # decals just in front of the dial

    def in_hole(c_deg):
        return broken and BROKEN_SECTOR[0] - 3 <= c_deg % 360 <= BROKEN_SECTOR[1] + 3

    if broken:                              # the faint amber ring, broken where the dial burst
        ck.disc(pg, "glow_amber", 1.395, yd, M=F, seg=44, r_in=1.31, a0=BROKEN_SECTOR[1] + 4, a1=BROKEN_SECTOR[0] + 356)
    else:
        ck.disc(pg, "glow_amber", 1.395, yd, M=F, seg=56, r_in=1.31)
    for r_out, r_in in ((0.86, 0.845), (1.225, 1.208)):
        if broken:
            ck.disc(p, "black", r_out, yd, M=F, seg=36, r_in=r_in, a0=BROKEN_SECTOR[1] + 3, a1=BROKEN_SECTOR[0] + 357)
        else:
            ck.disc(p, "black", r_out, yd, M=F, seg=44, r_in=r_in)
    for i in range(60):                     # minute track
        c = 6.0 * i
        if in_hole(c):
            continue
        u = Vector((math.sin(math.radians(c)), math.cos(math.radians(c))))
        if i % 5 == 0:
            ck.bar2d(p, "black", u * 1.118, u * 1.208, 0.03, yd, F)
        else:
            ck.bar2d(p, "black", u * 1.13, u * 1.20, 0.011, yd, F)
    names = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for i, nm in enumerate(names):          # radial roman numerals
        c = 30.0 * i
        if in_hole(c):
            continue
        u = Vector((math.sin(math.radians(c)), math.cos(math.radians(c))))
        ck.numeral(p, "black", nm, u * 0.875, u, 0.205, 0.03, yd, F)
    hand(p, "hour", HOUR_A, -0.125, -0.145, F)
    hand(p, "minute", 196.0 if broken else MIN_A, -0.15, -0.168, F)
    ck.lathe_m(p, "brass", [(0.11, 0.105), (0.15, 0.09), (0.18, 0.055), (0.195, 0.03), (0.2, 0.0)], seg=12, M=Fo,
               cap0=False)
    ck.lathe_m(p, "black", [(0.195, 0.032), (0.215, 0.032), (0.228, 0.016), (0.234, 0.0)], seg=8, M=Fo)
    if k == 0:
        cracks(p, F, yd - 0.001, Vector((0.46, -0.52)), seed=11)
    for sx in (-1, 1):                      # spandrel gears (top corners) and bosses (bottom corners)
        Ms = F @ T(sx * 1.6, -0.03, 1.52) @ FACE_OUT
        ck.gear(p, "brass", 0.13, 0.18, 8, 0.05, M=Ms, phase=rng.uniform(0, 1), back=False)
        ck.lathe_m(p, "brass_dark", [(0.025, 0.065), (0.06, 0.05), (0.075, 0.0)], seg=8, M=Ms, cap0=False)
        ck.lathe_m(p, "brass", [(0.0, 0.1), (0.03, 0.09), (0.06, 0.05), (0.07, 0.0)], seg=8,
                   M=F @ T(sx * 1.62, 0.0, -1.55) @ FACE_OUT, cap0=False)


def cracks(p, F, y, origin, seed=0):
    """Hairline cracks radiating from a small impact chip (black decal strips)."""
    rng = random.Random(seed)
    for i in range(6):
        ang = 2 * math.pi * i / 6 + rng.uniform(-0.35, 0.35)
        pos = Vector(origin)
        w = 0.013
        for j in range(rng.randint(3, 5)):
            ang += rng.uniform(-0.45, 0.45)
            nxt = pos + Vector((math.cos(ang), math.sin(ang))) * rng.uniform(0.08, 0.19)
            if nxt.length > 1.28:
                break
            ck.bar2d(p, "black", pos, nxt, w, y, F)
            if j == 1 and rng.random() < 0.5:
                b_ang = ang + rng.choice((-1, 1)) * rng.uniform(0.6, 1.1)
                bp = pos + (nxt - pos) * 0.5
                bn = bp + Vector((math.cos(b_ang), math.sin(b_ang))) * rng.uniform(0.07, 0.13)
                if bn.length < 1.28:
                    ck.bar2d(p, "black", bp, bn, w * 0.6, y, F)
            pos = nxt
            w = max(0.005, w * 0.75)
    ck.disc(p, "black", 0.03, y, M=F @ T(origin.x, 0, origin.y), seg=7)


# ---------------------------------------------------------------------------
# roof, dormers, lantern, cupola, spire
# ---------------------------------------------------------------------------

def build_roof(p, pg, rng):
    n = 13                                  # overlapping courses (sawtooth profile), mitred hips
    prof = [(Z_CORN1 - 0.05, 0.0), (Z_CORN1 - 0.05, roof_hw(0.0) + 0.06)]
    tints = [0.0, -0.05]
    for i in range(n):
        ta, tb = i / n, (i + 1) / n
        prof.append((roof_z(ta), roof_hw(ta) + 0.05))
        prof.append((roof_z(tb) - 0.025, roof_hw(tb) + 0.012))
        tints += [-0.07 + 0.008 * i, 0.03 + 0.005 * i]
    prof.append((Z_ROOF1, 0.0))
    tints.append(0.1)
    ck.rlathe(p, ROOF, prof, tints=tints, cap1=False)
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):       # brass hip rolls
        pts = []
        for i in range(13):
            t = i / 12 * 0.985
            h = roof_hw(t) + 0.055
            pts.append((sx * h, sy * h, roof_z(t) + 0.03))
        ck.tube(p, "brass", pts, r=0.042, seg=6)
    for k in range(4):
        dormer(p, pg, k)
    for sx in (-1, 1):                                       # corner pinnacles on the cornice
        for sy in (-1, 1):
            Mp = T(sx * 2.49, sy * 2.49, Z_CORN1)
            ck.lathe_m(p, "brass_dark", [(0.0, 0.0), (0.0, 0.13), (0.12, 0.13), (0.15, 0.10), (0.42, 0.09),
                                         (0.46, 0.12), (0.5, 0.12), (0.5, 0.0)], seg=4, M=Mp, phase=math.pi / 4)
            ck.lathe_m(p, ROOF, [(0.5, 0.14), (0.56, 0.12), (0.95, 0.0)], seg=4, M=Mp, phase=math.pi / 4)
            ck.lathe_m(p, "brass", [(0.92, 0.0), (0.92, 0.02), (0.97, 0.045), (1.02, 0.02), (1.12, 0.0)], seg=6, M=Mp)
    # lantern (octagonal arcade with the bell)
    z = Z_ROOF1
    ck.lathe_m(p, "brass_dark", [(z - 0.06, 0.0), (z - 0.06, 0.66), (z + 0.04, 0.68), (z + 0.08, 0.64),
                                 (z + 0.10, 0.6), (z + 0.10, 0.0)], seg=8, phase=math.pi / 8)
    zt = z + 0.50
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 8
        ck.lathe_m(p, "brass", [(z + 0.10, 0.06), (z + 0.15, 0.04), (zt - 0.07, 0.032), (zt - 0.03, 0.055),
                                (zt, 0.055)], seg=6, M=T(0.53 * math.cos(a), 0.53 * math.sin(a), 0), cap0=False,
                   cap1=False)
    ck.lathe_m(p, "brass_dark", [(zt, 0.0), (zt, 0.62), (zt + 0.05, 0.66), (zt + 0.11, 0.66), (zt + 0.13, 0.6),
                                 (zt + 0.13, 0.0)], seg=8, phase=math.pi / 8)
    zb = zt - 0.03
    ck.lathe_m(p, "brass", [(zb - 0.31, 0.0), (zb - 0.31, 0.2), (zb - 0.30, 0.235), (zb - 0.285, 0.24),
                            (zb - 0.25, 0.2), (zb - 0.16, 0.145), (zb - 0.06, 0.125), (zb - 0.02, 0.09), (zb, 0.0)], seg=14)
    ck.lathe_m(p, "black", [(zb - 0.37, 0.0), (zb - 0.37, 0.04), (zb - 0.33, 0.05), (zb - 0.29, 0.0)], seg=6)
    zd = zt + 0.13                                           # ogee cupola
    prof = [(zd, 0.0), (zd, 0.6), (zd + 0.05, 0.62), (zd + 0.12, 0.6), (zd + 0.19, 0.54), (zd + 0.27, 0.43),
            (zd + 0.34, 0.3), (zd + 0.39, 0.19), (zd + 0.43, 0.11), (zd + 0.47, 0.065), (zd + 0.50, 0.0)]
    ck.lathe_m(p, ROOF, prof, seg=16, tints=[0, -0.06, 0.0, 0.02, 0.04, 0.05, 0.06, 0.06, 0.07, 0.08, 0.08])
    zs_ = zd + 0.48                                          # spire + gear weather vane
    ck.lathe_m(p, "brass", [(zs_, 0.06), (zs_ + 0.04, 0.08), (zs_ + 0.08, 0.06), (zs_ + 0.11, 0.028),
                            (zs_ + 0.33, 0.02), (zs_ + 0.36, 0.045), (zs_ + 0.40, 0.05), (zs_ + 0.44, 0.045),
                            (zs_ + 0.46, 0.018), (zs_ + 0.57, 0.0)], seg=8, cap0=False)
    Mv = T(0, 0, zs_ + 0.22) @ R("Z", 28)
    ck.gear(p, "brass", 0.11, 0.15, 10, 0.025, r_in=0.06, M=Mv @ T(0.33, 0, 0) @ R("X", 90))
    ck.prism(p, "brass", [(-0.44, 0.0), (-0.3, -0.075), (-0.3, -0.022), (0.24, -0.022), (0.24, 0.022),
                          (-0.3, 0.022), (-0.3, 0.075)], -0.012, 0.012, Mv)


def dormer(p, pg, k):
    hwd = roof_hw(roof_t_at(14.22))
    M = frame_side(k, hwd - 0.02)
    w, z0, z1, zr = 0.44, 13.98, 14.82, 15.18
    ck.chamfer_prism(p, "brass_dark", [(-w, z0), (w, z0), (w, z1), (0, zr), (-w, z1)], 0.0, 1.5, 0.02, M=M)
    for s in (-1, 1):                                        # gable roof slabs with overhang
        a = Vector((s * (w + 0.1), z1 - 0.06))
        b = Vector((0.0, zr + 0.05))
        d = (b - a).normalized()
        nrm = Vector((-d.y, d.x)) * (0.05 if s < 0 else -0.05)
        ck.prism(p, ROOF, [tuple(a), tuple(b), tuple(b + nrm), tuple(a + nrm)], -0.09, 1.6, M, tint=0.04)
    ck.lathe_m(p, "brass", [(zr + 0.05, 0.04), (zr + 0.1, 0.05), (zr + 0.14, 0.03), (zr + 0.28, 0.0)], seg=6,
               M=M @ T(0, -0.07, 0), cap0=False)
    zc = 14.54                                               # oculus
    ck.torus_m(p, "brass", 0.17, 0.035, seg=16, seg2=4, M=M @ T(0, -0.02, zc) @ FACE_OUT)
    ck.disc(pg, "glow_amber", 0.15, -0.005, M=M @ T(0, 0, zc), seg=12)
    ck.box_xyz(p, "brass", -0.16, 0.16, -0.035, 0.0, zc - 0.012, zc + 0.012, M=M)
    ck.box_xyz(p, "brass", -0.012, 0.012, -0.035, 0.0, zc - 0.16, zc + 0.16, M=M)


# ---------------------------------------------------------------------------
# steam pipes (east side)
# ---------------------------------------------------------------------------

def build_pipes(p, rng):
    A, B, C = STAGES["A"], STAGES["B"], STAGES["C"]
    M = frame_side(1, A["hw"])
    yp = -0.42
    Mt = M @ T(1.27, yp, 1.22) @ R("Y", 90)                   # manifold tank on wall brackets
    ck.lathe_m(p, "brass", [(-0.47, 0.0), (-0.46, 0.09), (-0.43, 0.16), (-0.39, 0.19), (0.39, 0.19), (0.43, 0.16),
                            (0.46, 0.09), (0.47, 0.0)], seg=14, M=Mt)
    for zz in (-0.3, 0.0, 0.3):
        ck.lathe_m(p, "brass_dark", [(zz - 0.03, 0.2), (zz + 0.03, 0.2)], seg=14, M=Mt, cap0=False, cap1=False)
    for xx in (0.98, 1.56):
        ck.box_xyz(p, "black", xx - 0.03, xx + 0.03, yp + 0.05, 0.02, 0.98, 1.06, M=M)
        ck.box_xyz(p, "black", xx - 0.03, xx + 0.03, yp - 0.05, yp + 0.08, 0.96, 1.06, M=M)
    Mg = M @ T(1.02, yp - 0.2, 1.3)                           # pressure gauge
    ck.lathe_m(p, "brass", [(-0.04, 0.03), (0.0, 0.03), (0.0, 0.1), (0.035, 0.1), (0.045, 0.085),
                            (0.045, 0.0)], seg=14, M=Mg @ FACE_OUT, cap0=False)
    ck.disc(p, "white", 0.083, -0.047, M=Mg, seg=14)
    ck.bar2d(p, "black", (0.0, 0.0), (0.055, 0.03), 0.01, -0.049, Mg)
    for i in range(7):
        u = Vector((math.sin(math.radians(-120 + 40 * i)), math.cos(math.radians(-120 + 40 * i))))
        ck.bar2d(p, "black", u * 0.06, u * 0.075, 0.007, -0.049, Mg)
    Mw = M @ T(1.74, yp, 1.22) @ R("Y", 90)                   # valve wheel on the tank's end cap
    ck.lathe_m(p, "brass_dark", [(-0.02, 0.035), (0.1, 0.035), (0.1, 0.0)], seg=8, M=Mw, cap0=False)
    Mww = Mw @ T(0, 0, 0.1)
    ck.torus_m(p, "black", 0.11, 0.014, seg=14, seg2=4, M=Mww)
    for i in range(3):
        ck.cbox(p, "black", (0.22, 0.016, 0.016), M=Mww, rot=(0, 0, 60 * i))
    ck.lathe_m(p, "brass", [(-0.02, 0.0), (-0.02, 0.03), (0.03, 0.025), (0.04, 0.0)], seg=8, M=Mww)
    ck.tube(p, "copper", [(1.27, yp, 1.05), (1.27, yp, 0.36)], r=0.05, seg=8, M=M)
    ck.lathe_m(p, "brass_dark", [(0.33, 0.0), (0.33, 0.09), (0.39, 0.09), (0.42, 0.065), (0.42, 0.0)], seg=8,
               M=M @ T(1.27, yp, 0))
    for x, r, ztop, ywall in ((1.02, 0.085, 8.30, A["hw"] - C["hw"]), (1.50, 0.065, 6.35, A["hw"] - B["hw"])):
        pts = [(x, yp, 1.38)] + ck.bend_pts((x, yp, 1.38), (x, yp, ztop), (x, ywall + 0.1, ztop), 0.22, n=5) + \
              [(x, ywall + 0.12, ztop)]
        ck.tube(p, "copper", pts, r=r, seg=10, M=M)
        for zz in ((3.2, 5.3) if r > 0.07 else (4.6,)):    # flanges
            ck.lathe_m(p, "brass", [(-0.05, r + 0.04), (-0.03, r + 0.05), (0.03, r + 0.05), (0.05, r + 0.04)],
                       seg=10, M=M @ T(x, yp, zz), cap0=False, cap1=False)
        ck.lathe_m(p, "brass_dark", [(-0.03, 0.0), (-0.03, r + 0.06), (0.03, r + 0.06), (0.03, 0.0)], seg=10,
                   M=M @ T(x, ywall - 0.04, ztop) @ R("X", 90))
        for zz in ((2.4, 4.75, 7.75) if r > 0.07 else (2.6, 5.4)):            # clamps + wall brackets
            ywz = 0.0 if zz < A["z1"] else (A["hw"] - (B["hw"] if zz < B["z1"] + 0.3 else C["hw"]))
            ck.torus_m(p, "black", r + 0.018, 0.016, seg=10, seg2=3, M=M @ T(x, yp, zz))
            ck.box_xyz(p, "black", x - 0.022, x + 0.022, yp + r + 0.02, ywz - 0.06, zz - 0.022, zz + 0.022, M=M)
            ck.fbox(p, "black", x - 0.07, x + 0.07, ywz - 0.085, ywz - 0.04, zz - 0.07, zz + 0.07, 0.01, M=M)


# ---------------------------------------------------------------------------
# ivy + moss
# ---------------------------------------------------------------------------

def _outer_hw(z):
    """Approximate outer half width of the masonry (incl. string courses) at height z."""
    A, B, C = STAGES["A"], STAGES["B"], STAGES["C"]
    if z < A["z1"] - 0.05:
        return A["hw"] + A["d"] + 0.01
    if z < B["z0"] + 0.05:
        return A["hw"] + 0.27
    if z < B["z1"] - 0.05:
        return B["hw"] + B["d"] + 0.01
    if z < C["z0"] + 0.05:
        return B["hw"] + 0.21
    return C["hw"] + C["d"] + 0.01


def build_ivy(p, rng):
    """Ivy climbing the west face (side 3) and the back near the west corner; moss on the ledges."""
    A = STAGES["A"]
    plants = [(3, 0.9, 5.6, 4), (3, -1.0, 3.0, 3), (2, -1.2, 4.4, 3)]
    for k, x0, height, nb in plants:
        M = frame_side(k, A["hw"])
        R3 = M.to_3x3()
        for b in range(nb):
            x = x0 + rng.uniform(-0.2, 0.2)
            z = 0.55
            pts = [(x, -0.2, 0.40)]
            ang = rng.uniform(-0.6, 0.6)
            ztop = height * rng.uniform(0.5, 1.0)
            while z < ztop:
                ang = max(-0.9, min(0.9, ang + rng.uniform(-0.5, 0.5)))
                if abs(x + math.sin(ang) * 0.3) > A["hw"] - 0.45:
                    ang = -ang
                x += math.sin(ang) * 0.3
                z += 0.3 + rng.uniform(0, 0.1)
                pts.append((x, A["hw"] - _outer_hw(z) - 0.025, z))
            if len(pts) < 3:
                continue
            nn = len(pts)
            ck.tube(p, "wood_dark", pts, r=0.02, seg=3, M=M, radii=[0.024 - 0.014 * i / nn for i in range(nn)])
            for i in range(1, nn):                         # leaf clusters along the stem
                pa, pb = Vector(pts[i - 1]), Vector(pts[i])
                taper = 1.2 - 0.55 * i / nn
                for j in range(6):
                    c = pa.lerp(pb, rng.random())
                    side = rng.choice((-1, 1))
                    base = c + Vector((side * rng.uniform(0.0, 0.16), -rng.uniform(0.0, 0.04), rng.uniform(-0.06, 0.06)))
                    base.y = min(base.y, A["hw"] - _outer_hw(base.z) - 0.015)
                    dirv = Vector((side * rng.uniform(0.2, 1.0), -rng.uniform(0.1, 0.5), rng.uniform(-0.8, 0.5)))
                    nrm = Vector((rng.uniform(-0.35, 0.35), -1.0, rng.uniform(0.0, 0.7)))
                    f = ck.leaf_quad(p, MOSS, M @ base, R3 @ dirv, R3 @ nrm, rng.uniform(0.11, 0.18) * taper)
                    ck.set_tint(p, f.verts, rng.uniform(-0.32, 0.1))
    # moss cushions on the ledges (mostly the shaded west / north side)
    ledges = ((0.60, 2.53, 0.06), (Z_PL + 0.01, 2.71, 0.05), (4.20, 2.37, 0.05), (7.05, 2.22, 0.045),
              (Z_SLAB1 + 0.01, 2.62, 0.045))
    for _ in range(12):
        k = rng.choice((3, 3, 3, 2, 2, 0))
        z, hw_abs, th = rng.choice(ledges)
        x = rng.uniform(-2.0, 2.0)
        if k == 0 and abs(x) < 1.35:
            continue
        M = frame_side(k, hw_abs)
        for j in range(rng.randint(2, 3)):                 # cluster of overlapping flattened lumps
            c = M @ Vector((x + rng.uniform(-0.2, 0.2), rng.uniform(-0.03, 0.05), z))
            Mm = T(*c) @ R("Z", 90 * k + rng.uniform(-30, 30)) @ S(rng.uniform(0.1, 0.24), rng.uniform(0.06, 0.12), th)
            moss_lump(p, Mm, rng)


def moss_lump(p, M, rng):
    r = bmesh.ops.create_icosphere(p.bm, subdivisions=1, radius=1.0, matrix=I4)
    vs = r["verts"]
    for v in vs:
        v.co = v.co * (1 + rng.uniform(-0.18, 0.18))
        if v.co.z < -0.3:
            v.co.z = -0.3
        v.co = M @ v.co
    ck.set_mat(p, ck._faces_of(vs), MOSS)
    ck.set_tint(p, vs, rng.uniform(-0.12, 0.08))


# ---------------------------------------------------------------------------
# finishing
# ---------------------------------------------------------------------------

def _grime(pw, n):
    """Vertex-colour multiplier on top of the AO: damp/dirt near the ground, sun-bleached higher up."""
    z = pw.z
    t = 1.0
    if z < 1.5:
        t *= 0.80 + 0.20 * (z / 1.5) ** 0.7
    t *= 0.97 + 0.05 * min(1.0, z / 14.0)
    return (t, t * 0.995, t * 0.985)


def apply_tint(obj):
    """Multiply the per-vertex 'clk_tint' variation into the baked AO colours, then drop the attribute."""
    me = obj.data
    if ck.TINT not in me.attributes:
        if ck.WARM in me.attributes:
            me.attributes.remove(me.attributes[ck.WARM])
        return
    if hp.AO_ATTR in me.color_attributes:
        tv = np.zeros(len(me.vertices), dtype=np.float32)
        me.attributes[ck.TINT].data.foreach_get("value", tv)
        nl = len(me.loops)
        lv = np.empty(nl, dtype=np.int64)
        me.loops.foreach_get("vertex_index", lv)
        col = me.color_attributes[hp.AO_ATTR]
        c = np.empty(nl * 4, dtype=np.float32)
        col.data.foreach_get("color", c)
        c = c.reshape(nl, 4)
        c[:, :3] *= (1.0 + tv[lv])[:, None]
        if ck.WARM in me.attributes:
            wv = np.zeros(len(me.vertices), dtype=np.float32)
            me.attributes[ck.WARM].data.foreach_get("value", wv)
            w = wv[lv]
            c[:, 0] *= 1.0 + w
            c[:, 2] *= 1.0 - 1.3 * w
        c[:, :3] = np.clip(c[:, :3], 0.0, 1.0)
        col.data.foreach_set("color", c.ravel())
    me.attributes.remove(me.attributes[ck.TINT])
    if ck.WARM in me.attributes:
        me.attributes.remove(me.attributes[ck.WARM])


def _section(name, parts, prev):
    cur = sum(sum(len(f.verts) - 2 for f in q.bm.faces) for q in parts)
    print(f"[clk] {name:14s} {cur - prev:6d} tris")
    return cur


def build_clocktower():
    root = empty("prop_clocktower", size=0.5)
    rng = random.Random(1907)
    p = ck.new_part("prop_clocktower_body")       # stone + metal + decals (explicit winding, no recalc)
    pg = ck.new_part("prop_clocktower_glow")
    parts = (p, pg)
    n = 0
    for name, fn, args in (("base", build_base, (p, rng)), ("shaft", build_shaft, (p, rng)),
                           ("door", build_door, (p, pg, rng)), ("windows", build_windows, (p, pg, rng)),
                           ("belfry", build_belfry, (p, pg, rng)), ("rail", build_balcony_rail, (p,)),
                           ("clock stage", build_clock_stage, (p, pg, rng)), ("roof", build_roof, (p, pg, rng)),
                           ("pipes", build_pipes, (p, rng)), ("ivy", build_ivy, (p, rng))):
        fn(*args)
        n = _section(name, parts, n)
    body = ck.build_part(p, root, recalc=False)
    glow = ck.build_part(pg, root, recalc=False)
    hp.weighted_normals(body, weight=50)
    hp.smooth_obj(glow, angle=35)
    bpy.context.view_layer.update()
    if FAST:
        hp.bake_tree_ao(root, samples=6, distance=1.4, strength=0.85, floor=0.3, ground=0.0, tint=_grime)
    else:
        hp.bake_tree_ao(root, samples=32, distance=1.5, strength=0.88, floor=0.28, ground=0.0, tint=_grime)
    apply_tint(body)
    apply_tint(glow)
    return root


# name, builder, preview kwargs (passed to hp.render_hp)
PROPS = [
    ("prop_clocktower", build_clocktower, {"size": 900, "elevation": 14}),
]

# triangle budget per prop (user-chosen "medium" tier, 2026-10-11)
BUDGET = {
    "prop_clocktower": 40000,
}
