"""Strongbox Tortoise (금고 거북) — chapter-1 mini-boss, archetype **beetle**. Hi-poly.
~2.6 m long, ~1.6 m tall. Exports public/models/strongbox_tortoise.glb.

A bank vault that woke up as a tortoise: black-steel strongbox shell with gold ornamental trim,
round vault door with a combination dial on the front (steam leaks from the door seam), riveted
cast-iron head / legs, small amber indicator-lamp eyes. Wide, low, boxy.

Skeleton (beetle archetype conventions, src/anim/rig.ts), armature object 'root':
  body (root bone, z=0.90) > head > horn                 horn = the lower beak / jaw (attack snaps it shut)
                           > shell_L, shell_R            the two lid halves of the vault, hinged at the
                                                         top-front midline (open in a V when stunned ->
                                                         coin hoard inside)
                           > dial                        combination dial on the vault door (spins
                                                         around its local forward axis)
                           > leg_FL > leg_FL_2, leg_BL > leg_BL_2 (and _R)   four stumpy cast-iron legs
                           > leg_ML > leg_ML_2 (and _R)  the "middle legs" are the gold side knocker
                                                         handles: boss + ring that swings with the gait
  rigid: steam_point (empty, child of body) at the top of the vault-door seam.
The head is modelled with a telescoping neck reaching back into a dark slot in the shell, so
rig.pos('head', 0, 0, -0.4) retracts it into the vault.

Usage: blender -b --factory-startup -P tools/blender/model_strongbox_tortoise.py [-- out=<dir>] [quick]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import hp_helpers as hp  # noqa: E402
from common import empty, get_mat, reset_scene  # noqa: E402
from hp_beetle_helpers import (BoneBuilder, _face, bake_ao_open, ball, bolt, box_m, catmull, dome,  # noqa: E402
                               gear_ring, grid_faces, grid_rows, lathe_m, mtx, resample, set_mat, sp, sweep, torus_m)
from rig_helpers import pose_world, reset_pose, rig_from_parts  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "quick" in ARGS
OUT = next((a.split("=", 1)[1] for a in ARGS if a.startswith("out=")), hp.PREVIEW_DIR)
os.makedirs(OUT, exist_ok=True)

reset_scene()
root = empty("root")
V = Vector

# ---- materials (9) ---------------------------------------------------------------------------
STL = "vault_steel"       # shell
GLD = "vault_gold"        # ornamental trim, coins, beak tip
CST = "cast_iron"         # head, legs
DRK = "vault_dark"        # recesses, slot, inner floor, mouth
STE = "steel"             # bolts, dial knob, bezels
GDK = "brass_dark"        # darker gold for engraved inlays / lid undersides
GLW = "glow_amber"        # indicator-lamp eyes
NUM = "white"             # dial numerals
BLK = "black"             # dial face
get_mat(STL, hex="#2b2e34", metallic=0.78, roughness=0.36)
get_mat(GLD, hex="#d4a83a", metallic=1.0, roughness=0.26)
get_mat(CST, hex="#4a4a4f", metallic=0.62, roughness=0.58)
get_mat(DRK, hex="#141518", metallic=0.4, roughness=0.7)
for _m in (STE, GDK, GLW, NUM, BLK):
    get_mat(_m)

ROUND = 75.0
HARD = 34.0

# ---- key dimensions / pivots ---------------------------------------------------------------
BX = 0.92                       # half width of the vault
BY0, BY1 = -0.90, 0.98          # front / back face
BZ0, BZ1 = 0.42, 1.26           # bottom / top of the box (lids sit on top up to LZ)
LZ = 1.45
BODY_P = V((0, 0, 0.84))
LID_P = V((0, BY0, BZ1))        # lid hinge: top-front midline
DOOR_C = V((0, BY0, 1.0))       # vault door centre (on the front face)
DOOR_R = 0.22
DIAL_P = V((0, BY0 - 0.085, DOOR_C.z))
HEAD_P = V((0, -0.86, 0.56))
HC = V((0, -1.43, 0.64))        # head capsule centre
HR = V((0.30, 0.30, 0.215))
JAW_P = V((0, -1.21, 0.52))
RING_Y, RING_Z = 0.04, 0.98     # side knocker ring mount

LEGS = {   # hip, knee, foot centre (left side; right mirrored)
    "F": (V((0.62, -0.55, 0.50)), V((1.00, -0.66, 0.40)), V((1.06, -0.72, 0.0))),
    "B": (V((0.62, 0.66, 0.50)), V((1.00, 0.76, 0.40)), V((1.06, 0.82, 0.0))),
}


def mirror(v, s):
    return V((v[0] * s, v[1], v[2]))


def bevel(w, seg=2, angle=30.0):
    return dict(width=w, segments=seg, angle=angle)


def rivet_row(p, mat, a, b, n, normal, r=0.016):
    for i in range(n):
        f = i / (n - 1) if n > 1 else 0.5
        dome(p, mat, a.lerp(b, f), normal, r, seg=6)


def frame_bars(p, mat, plane, c, w, h, bar, depth):
    """Rectangular raised frame of 4 bars on an axis-aligned face.
    plane: ('y', y_face, outward_sign) or ('x', x_face, outward_sign); c = (u, z) centre on the face."""
    ax, f, sg = plane
    out = f + sg * depth * 0.5
    u, z = c
    bars = [((w, bar), (u, z + h / 2)), ((w, bar), (u, z - h / 2)),
            ((bar, h - bar), (u - w / 2 + bar / 2, z)), ((bar, h - bar), (u + w / 2 - bar / 2, z))]
    for (sw, sh), (cu, cz) in bars:
        if ax == "y":
            p.box(mat, size=(sw, depth, sh), loc=(cu, out, cz))
        else:
            p.box(mat, size=(depth, sw, sh), loc=(out, cu, cz))


# =============================================================================================
# BODY — the vault
# =============================================================================================
def build_body(parent):
    bb = BoneBuilder("body", BODY_P)
    shell = bb.piece(smooth=HARD, bevel=bevel(0.055, 3))
    trim = bb.piece(smooth=HARD, bevel=bevel(0.012, 1))
    fine = bb.piece(smooth=HARD, bevel=bevel(0.006, 1))
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    yc = (BY0 + BY1) / 2
    ylen = BY1 - BY0
    # --- main box ---
    shell.box(STL, size=(2 * BX, ylen, BZ1 - BZ0), loc=(0, yc, (BZ0 + BZ1) / 2))
    # cast-iron belly plate (plastron) + a low plinth band
    shell.box(CST, size=(2 * BX - 0.22, ylen - 0.2, 0.08), loc=(0, yc, BZ0 - 0.03))
    # --- gold corner caps (8) + vertical edge strips ---
    for sx in (1, -1):
        for yy, sy in ((BY0, -1), (BY1, 1)):
            for zz, sz in ((BZ1, 1),):
                c = V((sx * (BX - 0.105), yy - sy * 0.105, zz - sz * 0.105))
                trim.box(GLD, size=(0.25, 0.25, 0.25), loc=c)
                # rosette rivet on each cap face
                dome(rnd, GDK, V((sx * (BX + 0.02), c.y, c.z)), V((sx, 0, 0)), 0.03, seg=8)
                dome(rnd, GDK, V((c.x, yy + sy * 0.02, c.z)), V((0, sy, 0)), 0.03, seg=8)
            ex = V((sx * (BX - 0.04), yy - sy * 0.04, (BZ0 + 0.1 + BZ1 - 0.2) / 2))
            trim.box(GLD, size=(0.11, 0.11, BZ1 - 0.2 - BZ0 - 0.1), loc=ex)
    # --- carapace flange: overhanging marginal rim around the bottom, gold edge bead ---
    flange = bb.piece(smooth=HARD, bevel=bevel(0.03, 2))
    flange.box(STL, size=(2 * BX + 0.18, ylen + 0.18, 0.09), loc=(0, yc, BZ0 + 0.035))
    trim.box(GLD, size=(2 * BX + 0.2, ylen + 0.2, 0.03), loc=(0, yc, BZ0 + 0.095))
    for sx in (1, -1):        # scallop notches over the legs (marginal scutes)
        for yy in (LEGS["F"][1].y, LEGS["B"][1].y, 0.05):
            dome(rnd, GDK, V((sx * (BX + 0.095), yy, BZ0 + 0.035)), (sx, 0, 0), 0.03, seg=8)
    # top edge band (just under the lids) all around
    for sx in (1, -1):
        trim.box(GLD, size=(0.045, ylen - 0.42, 0.05), loc=(sx * (BX + 0.01), yc, BZ1 - 0.06))
    trim.box(GLD, size=(2 * BX - 0.42, 0.045, 0.05), loc=(0, BY1 + 0.01, BZ1 - 0.06))

    # --- front: recessed panel frame, vault door, head slot ---
    # door: dark seam ring, gold bezel, steel door slab with radial bolts, hinges, handle
    M = mtx(DOOR_C, (0, -1, 0), (1, 0, 0))
    lathe_m(hard, DRK, [(DOOR_R + 0.035, -0.01), (DOOR_R + 0.035, 0.012), (DOOR_R - 0.02, 0.012),
                        (DOOR_R - 0.02, -0.01)], M, seg=40, cap=(False, False))           # seam
    lathe_m(rnd, GLD, [(DOOR_R + 0.04, 0.0), (DOOR_R + 0.085, 0.012), (DOOR_R + 0.09, 0.03),
                       (DOOR_R + 0.07, 0.048), (DOOR_R + 0.04, 0.05), (DOOR_R + 0.03, 0.035),
                       (DOOR_R + 0.03, 0.0)], M, seg=44, cap=(False, False))                # bezel
    lathe_m(hard, STL, [(DOOR_R, 0.0), (DOOR_R, 0.045), (DOOR_R - 0.025, 0.062), (0.14, 0.062),
                        (0.14, 0.05), (0.0, 0.05)], M, seg=40, cap=(False, False))         # door slab
    torus_m(rnd, GLD, M @ Matrix.Translation((0, 0, 0.062)), 0.19, 0.012, seg=32, seg2=5)  # inner ring
    for k in range(12):                                                                     # bolts
        a = 2 * math.pi * (k + 0.5) / 12
        q = M @ V((math.cos(a) * (DOOR_R - 0.045), math.sin(a) * (DOOR_R - 0.045), 0.05))
        bolt(rnd, STE, q, (0, -1, 0), 0.02, 0.018, seg=6)
    for k in range(4):                                                                      # bolt bars
        a = 2 * math.pi * k / 4 + math.pi / 4
        d = V((math.cos(a), 0, math.sin(a)))
        sweep(rnd, GLD, [DOOR_C + d * 0.15 + V((0, -0.065, 0)), DOOR_C + d * 0.235 + V((0, -0.065, 0))],
              0.012, seg=6)
    # dial bezel (fixed) with an index notch at the top
    Md = mtx(DOOR_C + V((0, -0.062, 0)), (0, -1, 0), (1, 0, 0))
    lathe_m(rnd, GLD, [(0.135, -0.004), (0.14, 0.012), (0.128, 0.026), (0.118, 0.024), (0.118, 0.0)],
            Md, seg=36, cap=(False, False))
    lathe_m(rnd, GLD, [(0.018, 0.0), (0.0, 0.03)], mtx(DOOR_C + V((0, -0.08, 0.142)), (0, 0, -1)), seg=6,
            cap=(False, False))
    # hinges (character's left = +X side of the door) and lever handle (right)
    for z in (DOOR_C.z + 0.17, DOOR_C.z - 0.17):
        rnd.cyl(GLD, r=0.032, h=0.10, seg=12, loc=(DOOR_R + 0.065, BY0 - 0.06, z))
        fine.box(GDK, size=(0.11, 0.025, 0.06), loc=(DOOR_R + 0.02, BY0 - 0.05, z))
    sweep(rnd, GLD, [V((-0.20, BY0 - 0.065, DOOR_C.z - 0.06)), V((-0.20, BY0 - 0.12, DOOR_C.z - 0.06)),
                     V((-0.21, BY0 - 0.13, DOOR_C.z - 0.20))], 0.016, seg=8)
    ball(rnd, GLD, V((-0.21, BY0 - 0.13, DOOR_C.z - 0.215)), 0.03, seg=10, rings=6)
    # head slot: dark recessed mouth with a gold surround
    slot = bb.piece(smooth=HARD, bevel=bevel(0.03, 2))
    slot.box(DRK, size=(0.50, 0.03, 0.22), loc=(0, BY0 - 0.004, 0.56))
    trim.box(GLD, size=(0.62, 0.05, 0.045), loc=(0, BY0 - 0.02, 0.69))                  # lintel
    for sx in (1, -1):
        trim.box(GLD, size=(0.05, 0.05, 0.25), loc=(sx * 0.29, BY0 - 0.02, 0.565))
        dome(rnd, GDK, V((sx * 0.29, BY0 - 0.047, 0.69)), (0, -1, 0), 0.025, seg=8)
    # front rivet rows left / right of the door
    for sx in (1, -1):
        rivet_row(rnd, GLD, V((sx * 0.55, BY0 - 0.005, 0.62)), V((sx * 0.55, BY0 - 0.005, 1.12)), 5, (0, -1, 0))

    # --- sides: raised panel + frame, gold rosette where the knocker ring hangs ---
    for sx in (1, -1):
        fine.box(STL, size=(0.035, 1.24, 0.58), loc=(sx * (BX + 0.012), yc, 0.83))
        frame_bars(trim, GLD, ("x", BX + 0.03, sx), (yc, 0.83), 1.30, 0.64, 0.04, 0.025)
        rivet_row(rnd, GLD, V((sx * (BX + 0.045), yc - 0.55, 1.12)), V((sx * (BX + 0.045), yc + 0.55, 1.12)), 7,
                  (sx, 0, 0))
        rivet_row(rnd, GLD, V((sx * (BX + 0.045), yc - 0.55, 0.54)), V((sx * (BX + 0.045), yc + 0.55, 0.54)), 7,
                  (sx, 0, 0))
        # escutcheon plate behind the knocker ring
        Mp = mtx(V((sx * (BX + 0.03), RING_Y, RING_Z - 0.05)), (sx, 0, 0), (0, 1, 0))
        lathe_m(rnd, GDK, [(0.105, 0.0), (0.10, 0.012), (0.08, 0.02), (0.0, 0.022)], Mp, seg=8,
                cap=(False, False))

    # --- back: big gold keyhole escutcheon + frame ---
    frame_bars(trim, GLD, ("y", BY1, 1), (0, 0.84), 1.18, 0.62, 0.04, 0.03)
    Mk = mtx(V((0, BY1 + 0.012, 0.88)), (0, 1, 0), (1, 0, 0))
    lathe_m(rnd, GLD, [(0.16, 0.0), (0.165, 0.014), (0.15, 0.026), (0.0, 0.03)], Mk, seg=28, cap=(False, False))
    hard.cyl(DRK, r=0.04, h=0.03, seg=12, loc=(0, BY1 + 0.03, 0.92), rot=(90, 0, 0))
    hard.box(DRK, size=(0.035, 0.03, 0.11), loc=(0, BY1 + 0.03, 0.85))
    for k in range(8):
        a = 2 * math.pi * k / 8
        dome(rnd, GDK, Mk @ V((math.cos(a) * 0.205, math.sin(a) * 0.205, 0.0)), (0, 1, 0), 0.02, seg=6)

    # --- top: dark inner floor + coin hoard (hidden by the closed lids) ---
    hard.box(DRK, size=(2 * BX - 0.24, ylen - 0.26, 0.012), loc=(0, yc, BZ1 + 0.002))
    rnd2 = bb.piece(smooth=60)
    rnd2.sphere(GLD, r=1.0, seg=20, rings=10, loc=(0, yc + 0.04, BZ1 - 0.02), scale=(0.52, 0.66, 0.125))
    rr = random.Random(5)
    for i in range(16):
        a = rr.uniform(0, 2 * math.pi)
        d = math.sqrt(rr.uniform(0.0, 1.0))
        x, y = 0.48 * d * math.cos(a), yc + 0.04 + 0.62 * d * math.sin(a)
        z = BZ1 - 0.02 + 0.125 * math.sqrt(max(0.0, 1 - d * d)) + 0.004
        tilt = (rr.uniform(-25, 25), rr.uniform(-25, 25), rr.uniform(0, 90))
        rnd.cyl(GLD, r=0.055, h=0.012, seg=12, loc=(x, y, z), rot=tilt)
    # hinge knuckles at the front midline where the lids pivot
    rnd.cyl(GLD, r=0.035, h=0.16, seg=12, loc=(0, BY0 + 0.005, BZ1 + 0.02), rot=(0, 90, 0))
    # tail stub: short round cast-iron cone at the back bottom, gold rings
    t0, t1 = V((0, BY1 - 0.05, 0.58)), V((0, BY1 + 0.2, 0.47))
    Mt = mtx(t0, (t1 - t0).normalized(), (1, 0, 0))
    Lt = (t1 - t0).length
    lathe_m(bb.piece(smooth=70), CST, [(0.0, 0.0), (0.12, 0.0), (0.118, Lt * 0.3), (0.095, Lt * 0.62),
                                        (0.055, Lt * 0.88), (0.0, Lt)], Mt, seg=14, cap=(False, False))
    for f, rr_ in ((0.32, 0.115), (0.6, 0.09)):
        torus_m(rnd, GLD, Mt @ Matrix.Translation((0, 0, Lt * f)), rr_, 0.013, seg=14, seg2=4)
    return bb.build(parent, (0, 0, 0))


# =============================================================================================
# LIDS (shell_L / shell_R)
# =============================================================================================
def build_lid(side, name, parent):
    sx = side
    bb = BoneBuilder(name, LID_P)
    slab = bb.piece(smooth=HARD, bevel=bevel(0.04, 3))
    trim = bb.piece(smooth=HARD, bevel=bevel(0.01, 2))
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    x0, x1 = 0.004, BX
    xc = sx * (x0 + x1) / 2
    w = x1 - x0
    yc, ylen = (BY0 + BY1) / 2, BY1 - BY0
    slab.box(STL, size=(w, ylen, LZ - BZ1 - 0.06), loc=(xc, yc, (BZ1 + LZ - 0.06) / 2))
    slab.box(STL, size=(w - 0.16, ylen - 0.2, 0.1), loc=(xc - sx * 0.04, yc, LZ - 0.05))     # raised step
    hard.box(GDK, size=(w - 0.1, ylen - 0.1, 0.006), loc=(xc, yc, BZ1 - 0.001))         # underside
    # gold border on top
    bt = 0.045
    for (sw, sl, cx, cy) in ((w - 0.05, bt, xc + sx * 0.005, BY0 + 0.045), (w - 0.05, bt, xc + sx * 0.005, BY1 - 0.045),
                             (bt, ylen - 0.09, sx * (x1 - 0.045), yc)):
        trim.box(GLD, size=(sw, sl, 0.024), loc=(cx, cy, LZ - 0.06 + 0.004))
    # tortoise scute: raised steel hexagon with a gold rim + engraved inner hexagon
    hc = V((xc, yc + 0.02, LZ))
    hard_bev = bb.piece(smooth=HARD, bevel=bevel(0.012, 2))
    hard_bev.cyl(STL, r=0.30, h=0.05, seg=6, loc=hc + V((0, 0, 0.012)), rot=(0, 0, 30))
    loop = [hc + V((math.cos(math.radians(60 * k + 30)) * 0.305, math.sin(math.radians(60 * k + 30)) * 0.305,
                    0.038)) for k in range(6)]
    sweep(rnd, GLD, loop, 0.016, seg=6, closed=True)
    loop2 = [hc + V((math.cos(math.radians(60 * k + 30)) * 0.17, math.sin(math.radians(60 * k + 30)) * 0.17,
                     0.04)) for k in range(6)]
    sweep(rnd, GDK, loop2, 0.009, seg=5, closed=True)
    # gold centre boss on the scute
    lathe_m(rnd, GLD, [(0.07, 0.0), (0.068, 0.02), (0.045, 0.04), (0.0, 0.046)],
            mtx(hc + V((0, 0, 0.035)), (0, 0, 1)), seg=16, cap=(False, False))
    # half scutes front & back (partial hex, as rimmed plates)
    for yy, sg in ((BY0 + 0.22, -1), (BY1 - 0.22, 1)):
        trim.box(GDK, size=(w - 0.42, 0.025, 0.012), loc=(xc - sx * 0.04, yy, LZ + 0.003))
    # rivets on the border
    for i in range(6):
        y = BY0 + 0.16 + (ylen - 0.32) * i / 5
        dome(rnd, GDK, V((sx * (x1 - 0.045), y, LZ - 0.06 + 0.016)), (0, 0, 1), 0.016)
    # gold filigree corner brackets on the outer corners of the raised step
    for yy, sy in ((BY0, -1), (BY1, 1)):
        c = V((sx * (x1 - 0.2), yy - sy * 0.2, LZ + 0.005))
        pts = [c + V((0, sy * 0.10, 0)), c, c + V((sx * 0.10, 0, 0))]
        sweep(rnd, GLD, pts, 0.014, seg=6)
        ball(rnd, GLD, c, 0.03, seg=10, rings=5, scale=(1, 1, 0.6))
    return bb.build(parent, BODY_P)


# =============================================================================================
# DIAL — combination lock (own bone; spins around its local forward axis)
# =============================================================================================
def build_dial(parent):
    bb = BoneBuilder("dial", DIAL_P)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    M = mtx(DOOR_C + V((0, -0.062, 0)), (0, -1, 0), (1, 0, 0))
    lathe_m(hard, BLK, [(0.116, 0.0), (0.116, 0.018), (0.108, 0.024), (0.0, 0.024)], M, seg=36,
            cap=(False, False))                                                          # dial face
    for k in range(30):                                                                   # ticks
        a = 2 * math.pi * k / 30
        L = 0.03 if k % 3 == 0 else 0.016
        r0 = 0.104 - L
        c = M @ V((math.cos(a) * (r0 + L / 2), math.sin(a) * (r0 + L / 2), 0.026))
        Mt = Matrix.Translation(c) @ (M.to_3x3() @ Matrix.Rotation(a, 3, "Z")).to_4x4()
        res_size = (L, 0.007 if k % 3 == 0 else 0.004, 0.004)
        box_m(hard, GLD if k % 3 == 0 else NUM, Mt, res_size)
    # knurled knob: steel, gold cap, grip ridges
    lathe_m(rnd, STE, [(0.062, 0.022), (0.064, 0.035), (0.058, 0.07), (0.05, 0.078), (0.0, 0.08)], M, seg=20,
            cap=(True, False))
    for k in range(12):
        a = 2 * math.pi * k / 12
        q0 = M @ V((math.cos(a) * 0.061, math.sin(a) * 0.061, 0.03))
        q1 = M @ V((math.cos(a) * 0.056, math.sin(a) * 0.056, 0.07))
        sweep(rnd, STE, [q0, q1], 0.006, seg=4)
    lathe_m(rnd, GLD, [(0.03, 0.078), (0.028, 0.088), (0.0, 0.092)], M, seg=14, cap=(False, False))
    # pointer fin on the knob
    box_m(hard, GLD, M @ Matrix.Translation((0, 0.074, 0.05)), (0.012, 0.03, 0.05))
    return bb.build(parent, BODY_P)


# =============================================================================================
# HEAD + JAW (horn)
# =============================================================================================
def head_surf(s, t, grow=0.0):
    """s: 0 = front pole .. 1 = back pole, t: angle around Y (0 = +X, 0.25 = top)."""
    th = s * math.pi
    ph = t * 2 * math.pi
    e1, e2 = 2 / 2.5, 2 / 2.7
    cy, sy = math.cos(th), math.sin(th)
    sn = math.sin(ph)
    hz = (HR.z + grow) if sn >= 0 else (HR.z * 0.62 + grow)
    x = (HR.x + grow) * sp(sy, e1) * sp(math.cos(ph), e2)
    z = hz * sp(sy, e1) * sp(sn, e2)
    y = -(HR.y + grow) * sp(cy, e1)
    return HC + V((x, y, z))


def build_head(parent):
    bb = BoneBuilder("head", HEAD_P)
    caps = bb.piece(smooth=60)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    plates = bb.piece(smooth=HARD, bevel=bevel(0.008, 2))
    # telescoping neck: cast-iron tube from deep inside the slot to the skull, with collar rings
    npts = [V((0, -0.45, 0.56)), V((0, -0.82, 0.565)), V((0, -1.04, 0.58)), V((0, -1.22, 0.61))]
    npts = catmull(npts, 3)
    nr = [0.125, 0.125, 0.125, 0.125, 0.125, 0.122, 0.12, 0.13, 0.145, 0.16][:len(npts)]
    sweep(caps, CST, npts, nr, seg=16, up=(0, 0, 1), fx=0.9, fy=1.0)
    for f, mat in ((0.42, GLD), (0.7, CST)):
        i = int(f * (len(npts) - 1))
        t = (npts[i + 1] - npts[i - 1]).normalized()
        torus_m(rnd, mat, mtx(npts[i], t, (1, 0, 0), scale=(1.0, 0.9, 1.0)), nr[i] + 0.012, 0.018, seg=18, seg2=5)
    # skull (top: cast iron, under the beak: dark mouth)
    rows = [[head_surf(i / 14, j / 20) for j in range(20)] for i in range(15)]
    R = grid_rows(caps.bm, rows)
    fs = grid_faces(caps.bm, R, close_v=True)
    set_mat(caps, fs, CST)
    # rivets along the crown
    for s_ in (0.40, 0.55, 0.70):
        for t in (0.165, 0.335):
            q = head_surf(s_, t, 0.0)
            dome(rnd, STE, q, (q - HC).normalized(), 0.013)
    # cheek plates with rivets
    for sx in (1, -1):
        t0 = 0.0 if sx > 0 else 0.5
        for s_ in (0.55, 0.72):
            q = head_surf(s_, t0 + (0.02 if sx > 0 else -0.02), 0.0)
            dome(rnd, STE, q, (q - HC).normalized(), 0.013)
    # indicator-lamp eyes: amber glow domes in steel bezels, worried brow plates (timid)
    for sx in (1, -1):
        t = 0.085 if sx > 0 else 0.415
        q = head_surf(0.33, t, 0.0)
        n = V((sx * 0.5, -0.78, 0.38)).normalized()
        Me = mtx(q + n * 0.004, n, (0, 0, 1))
        lathe_m(rnd, STE, [(0.062, -0.025), (0.066, 0.008), (0.058, 0.024), (0.047, 0.02), (0.047, 0.0)], Me,
                seg=18, cap=(False, False))
        lathe_m(rnd, GLW, [(0.048, 0.0), (0.046, 0.016), (0.028, 0.032), (0.0, 0.037)], Me, seg=16,
                cap=(False, False))
        b0 = q + n * 0.03 + V((-sx * 0.05, 0.0, 0.085))
        b1 = q + n * 0.02 + V((sx * 0.06, 0.03, 0.05))
        sweep(plates, CST, [b0, b0.lerp(b1, 0.5) + V((0, -0.01, 0.012)), b1], [0.0, 0.024, 0.0], seg=6,
              up=(0, 0, 1), fx=0.42, fy=1.0)
    # nostrils
    for sx in (1, -1):
        q = head_surf(0.06, 0.2 if sx > 0 else 0.3, 0.0)
        hard.cyl(DRK, r=0.009, h=0.02, seg=8, loc=q, rot=(55, 0, 0))
    return bb.build(parent, BODY_P)


def build_jaw(parent):
    """Lower beak, hanging slightly open at rest (timid 'oh no' mouth); attack snaps it shut."""
    bb = BoneBuilder("horn", JAW_P)
    caps = bb.piece(smooth=60)
    rnd = bb.piece(smooth=ROUND)
    JC = V((0, -1.44, 0.545))
    JR = V((0.215, 0.24, 0.08))
    rot = Matrix.Rotation(math.radians(12), 4, "X")          # open: tip down

    def js(s, t, grow=0.0):
        th = s * math.pi
        ph = math.pi + t * math.pi                             # lower half only
        e1, e2 = 2 / 2.4, 2 / 2.6
        x = (JR.x + grow) * sp(math.sin(th), e1) * sp(math.cos(ph), e2)
        z = (JR.z + grow) * sp(math.sin(th), e1) * sp(math.sin(ph), e2)
        y = -(JR.y + grow) * sp(math.cos(th), e1)
        p = JC + V((x, y, z))
        return JAW_P + (rot @ (p - JAW_P))
    rows = [[js(i / 12, j / 12) for j in range(13)] for i in range(13)]
    R = grid_rows(caps.bm, rows)
    set_mat(caps, grid_faces(caps.bm, R), CST)
    top = [js(i / 12, 0.0) for i in range(13)] + [js(i / 12, 1.0) for i in range(12, -1, -1)]
    seen = []
    for q in top:
        if not seen or (q - seen[-1]).length > 1e-6:
            seen.append(q)
    f = _face(caps.bm, [caps.bm.verts.new(q + V((0, 0, 0.001))) for q in seen[:-1]])
    if f:
        set_mat(caps, [f], DRK)
    # hinge stub back to the pivot (hidden in the cheek)
    sweep(rnd, CST, [JAW_P + V((0, -0.02, 0)), js(0.85, 0.5) + V((0, 0, 0.03))], 0.05, seg=8)
    return bb.build(parent, HEAD_P)


# =============================================================================================
# LEGS (FL, BL, FR, BR) — stumpy riveted cast-iron columns
# =============================================================================================
def build_leg(lg, side, sname, parent):
    H0, K0, F0 = LEGS[lg]
    H, K, F = mirror(H0, side), mirror(K0, side), mirror(F0, side)
    bb = BoneBuilder(f"leg_{lg}{sname}", H)
    rnd = bb.piece(smooth=ROUND)
    arm = bb.piece(smooth=50)
    ball(rnd, CST, H, 0.16, seg=10, rings=6)
    d = (K - H).normalized()
    pts = catmull([H, H.lerp(K, 0.5) + V((0, 0, 0.02)), K], 3)
    sweep(arm, CST, pts, [0.15, 0.155, 0.16, 0.16, 0.155, 0.15, 0.145], seg=14, up=(0, 0, 1), fx=1.0, fy=1.1)
    # shoulder armour plate (gold-rimmed) over the upper limb
    for f, rr in ((0.45, 0.172),):
        q = H.lerp(K, f)
        torus_m(rnd, GLD, mtx(q, d, (0, 0, 1)), rr, 0.016, seg=16, seg2=5)
        for a in (0.6, 1.57, 2.5):
            n = V((0, 0, 1)) * math.sin(a) + d.cross(V((0, 0, 1))).normalized() * math.cos(a)
            dome(rnd, STE, q + n * 0.165 + d * 0.06, n, 0.014)
    femur = bb.build(parent, BODY_P)

    bb = BoneBuilder(f"leg_{lg}{sname}_2", K)
    rnd = bb.piece(smooth=ROUND)
    col = bb.piece(smooth=55)
    pad = bb.piece(smooth=HARD, bevel=bevel(0.02, 1))
    ball(rnd, CST, K, 0.15, seg=12, rings=7)
    # elephant column: knee -> ankle, slightly flared, riveted bands
    A = V((F.x, F.y, 0.10))
    Mc = mtx(A, (K - A).normalized(), (1, 0, 0))
    L = (K - A).length
    lathe_m(col, CST, [(0.0, -0.005), (0.19, -0.005), (0.195, 0.04), (0.175, L * 0.45), (0.15, L * 0.8),
                       (0.14, L), (0.0, L)], Mc, seg=16, cap=(False, False))
    for f, r in ((0.12, 0.192), (0.62, 0.162)):
        torus_m(rnd, GLD if f < 0.3 else CST, Mc @ Matrix.Translation((0, 0, L * f)), r, 0.018, seg=18, seg2=5)
        for k in range(5):
            a = 2 * math.pi * (k + 0.5) / 5
            n = Mc.to_3x3() @ V((math.cos(a), math.sin(a), 0))
            dome(rnd, STE, Mc @ V((math.cos(a) * (r + 0.008), math.sin(a) * (r + 0.008), L * f + 0.035)), n, 0.011)
    # foot pad + three gold toenails toward the front / outside
    pad.cyl(CST, r=0.225, h=0.10, r2=0.205, seg=20, loc=(F.x, F.y - 0.02, 0.05))
    pad.cyl(DRK, r=0.23, h=0.02, seg=20, loc=(F.x, F.y - 0.02, 0.012))
    for k, a in enumerate((-40, 0, 40)):
        aa = math.radians(a - 90 + side * 12)
        dv = V((math.cos(aa), math.sin(aa), 0))
        q = V((F.x, F.y - 0.02, 0.05)) + dv * 0.2
        Mt = mtx(q, (dv * 0.9 + V((0, 0, -0.3))).normalized(), (0, 0, 1), scale=(1.0, 0.7, 1.0))
        lathe_m(rnd, GLD, [(0.055, -0.03), (0.05, 0.01), (0.032, 0.045), (0.0, 0.07)], Mt, seg=10, cap=(True, False))
    bb.build(femur, H)
    return femur


def build_knocker(side, sname, parent):
    """Middle 'legs' leg_ML / leg_MR: gold rosette boss + hanging knocker ring on the vault side."""
    P = V((side * (BX + 0.085), RING_Y, RING_Z))
    bb = BoneBuilder(f"leg_M{sname}", P)
    rnd = bb.piece(smooth=ROUND)
    hard = bb.piece(smooth=HARD)
    M = mtx(V((side * (BX + 0.05), RING_Y, RING_Z)), (side, 0, 0), (0, 1, 0))
    gear_ring(hard, GLD, M, 0.075, 0.062, 10, 0.03, hub=0.042, hub_h=0.05, mat_hub=GLD, bottom=False)
    ball(rnd, GLD, P + V((side * 0.01, 0, 0)), 0.035, seg=10, rings=6)
    boss = bb.build(parent, BODY_P)
    Q = P + V((0, 0, -0.035))
    bb = BoneBuilder(f"leg_M{sname}_2", Q)
    rnd = bb.piece(smooth=ROUND)
    Mr = mtx(Q + V((0, 0, -0.12)), (side, 0, 0), (0, 1, 0))
    torus_m(rnd, GLD, Mr, 0.115, 0.022, seg=28, seg2=8)
    ball(rnd, GLD, Q + V((0, 0, -0.235)), 0.03, seg=10, rings=6, scale=(1, 1, 0.8))   # striker knob
    sweep(rnd, GDK, [Q + V((0, 0, 0.01)), Q + V((0, 0, -0.012))], 0.024, seg=8)      # loop eye
    bb.build(boss, P)
    return boss


# =============================================================================================
# Assemble
# =============================================================================================
body = build_body(root)
build_lid(1, "shell_L", body)
build_lid(-1, "shell_R", body)
build_dial(body)
head = build_head(body)
build_jaw(head)
for lg in "FB":
    for side, sname in ((1, "L"), (-1, "R")):
        build_leg(lg, side, sname, body)
for side, sname in ((1, "L"), (-1, "R")):
    build_knocker(side, sname, body)
empty("steam_point", parent=body, loc=tuple(V((0, BY0 - 0.06, DOOR_C.z + DOOR_R + 0.04)) - BODY_P))

print(f"[tris] pre-rig total {hp.scene_tris()}")
for nm, t in sorted(((o.name, hp.obj_tris(o)) for o in bpy.context.scene.objects if o.type == "MESH"),
                    key=lambda r: -r[1]):
    print(f"[tris] {nm:14s} {t}")

arm = rig_from_parts(root, rigid=set(), smooth={}, skin_name="strongbox_tortoise_skin")
skin = bpy.data.objects["strongbox_tortoise_skin"]


def tint(p, n):
    k = 0.93 + 0.07 * max(0.0, n.z)
    if p.z < 0.3:
        k *= 0.8 + 0.2 * (p.z / 0.3)
    return (k, k, k)


bake_ao_open(skin, samples=24 if QUICK else 48, distance=0.35, strength=0.85, floor=0.3, ground=0.0,
             tint=tint, lo=0.5, hi=0.3)
hp.export_glb_hp("strongbox_tortoise")

# ---- previews ----------------------------------------------------------------------------
N = os.path.join(OUT, "strongbox_tortoise")
hp.render_hp(N, azimuth=35, elevation=18)
hp.render_hp(N + "_game", azimuth=30, elevation=22, dist_k=5.0, size=560)
hp.render_hp(N + "_head", target=((0, -1.25, 0.8), 0.65), azimuth=25, elevation=10)
if not QUICK:
    hp.render_views(N, views=(("_front", 0, 8), ("_side", 90, 8), ("_back", 200, 20)))

DEG = 180 / math.pi
STUN = {
    "shell_L": [("Y", -0.42 * DEG), ("X", 0.25 * DEG), ("Z", -0.3 * DEG)],
    "shell_R": [("Y", 0.42 * DEG), ("X", 0.25 * DEG), ("Z", 0.3 * DEG)],
}
WALK = {
    "leg_FL": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)], "leg_BL": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)],
    "leg_MR": [("X", 0.5 * DEG), ("Z", 0.3 * DEG)],
    "leg_FR": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)], "leg_BR": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)],
    "leg_ML": [("X", -0.5 * DEG), ("Z", -0.3 * DEG)],
    "leg_FL_2": [("X", 0.3 * DEG)], "leg_BL_2": [("X", 0.3 * DEG)], "leg_MR_2": [("X", 0.3 * DEG)],
    "leg_FR_2": [("X", -0.3 * DEG)], "leg_BR_2": [("X", -0.3 * DEG)], "leg_ML_2": [("X", -0.3 * DEG)],
    "head": [("Z", 0.15 * DEG)], "horn": [("X", -20)], "dial": [("Y", 70)],
}


def pose_render(name, pose, **kw):
    pose_world(arm, pose)
    hp.render_hp(name, **kw)
    reset_pose(arm)


pose_render(N + "_pose_open", STUN, azimuth=150, elevation=40)
if not QUICK:
    pose_render(N + "_pose_walk", WALK, azimuth=40, elevation=15)
print(f"[done] strongbox_tortoise {hp.scene_tris()} tris")
