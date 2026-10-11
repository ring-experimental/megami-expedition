"""Boiler Jelly — weak slime enemy (~0.6 m jelly + 0.25 m valve). Hi-poly.
Exports public/models/slime.glb.

    root
    └─ body    pivot at ground centre (0,0,0) — whole jelly incl. inner boiler heart (squash & stretch)
       ├─ valve    pivot at the top of the jelly; spins around its local Z (game: rot y)
       ├─ eye_L    (+X) pressure-gauge eye, pivot at the gauge centre (wobbles around the forward axis)
       └─ eye_R    (-X)

Build flow: every visual piece is a loose "component" object (so each gets its own bevel / smoothing and
the AO bake can ignore the jelly shell for the parts inside it), then components are joined into the four
named parts with their pivots. All rest rotations are identity (tilts live in the geometry).

COLOR_0 (three.js multiplies it into the material colour AND opacity, the attribute is RGBA):
    * opaque parts: baked vertex AO (inner parts ignore the jelly shell as occluder)
    * jelly_teal: deeper/bluer teal + alpha 1 at the pooled foot -> lighter, alpha 0.88 towards the top
      (game opacity 0.72 x 0.88..1) so the glowing boiler heart reads through it
    * glass covers: alpha 0.45 (game opacity 0.35 x 0.45) -> a glint without greying the dials
    * dial faces: soft radial "bezel shadow" instead of ray AO

Args (after `--`):  --no-preview  skip renders   --extra  close-ups, game-distance + squash tests
                    --count       per-component triangle counts
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

from common import Part, reset_scene, empty  # noqa: E402
from char_helpers import tube  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_slime_helpers as sh  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

reset_scene()

# ---------------------------------------------------------------------------------------------
# Jelly shell: lathe profile x angular modulation (pooled foot lobes, drips, soft noise bulges)
# ---------------------------------------------------------------------------------------------
N_AROUND = 44            # divisible by 4 -> a vertex column sits exactly on the front (-Y)
N_RINGS = 20
BASE_Z = 0.006           # flat underside (just above the ground plane, no z-fight)
VALVE_Z = 0.612          # valve pivot (top of the jelly)

PROF_CTRL = [            # (r, z) silhouette: sagging puddle lip -> belly -> gumdrop shoulders -> neck
    (0.300, BASE_Z), (0.420, 0.007), (0.461, 0.013), (0.469, 0.025), (0.457, 0.041), (0.446, 0.066),
    (0.448, 0.108), (0.444, 0.165), (0.430, 0.232), (0.402, 0.300), (0.362, 0.370), (0.308, 0.437),
    (0.256, 0.495), (0.194, 0.540), (0.143, 0.571), (0.112, 0.588), (0.099, 0.602), (0.094, 0.612),
]
TOP_POLE_Z = 0.616


def catmull_rom(pts, n=14):
    P = [Vector(pts[0])] + [Vector(q) for q in pts] + [Vector(pts[-1])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for s in range(n):
            t = s / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(Vector(pts[-1]))
    return out


DENSE = catmull_rom(PROF_CTRL)


def resample(dense, n, k_curv=0.09):
    """n points along the polyline, spaced by arc length + k_curv * turning (denser on tight bends)."""
    cost = [0.0]
    for i in range(1, len(dense)):
        seg = (dense[i] - dense[i - 1]).length
        turn = 0.0
        if 1 <= i < len(dense) - 1:
            a = (dense[i] - dense[i - 1]).normalized()
            b = (dense[i + 1] - dense[i]).normalized()
            turn = math.acos(max(-1.0, min(1.0, a.dot(b))))
        cost.append(cost[-1] + seg + k_curv * turn)
    out = []
    for k in range(n):
        c = cost[-1] * k / (n - 1)
        j = next((i for i in range(1, len(cost)) if cost[i] >= c - 1e-12), len(cost) - 1)
        t = (c - cost[j - 1]) / max(1e-9, cost[j] - cost[j - 1])
        out.append(dense[j - 1].lerp(dense[j], t))
    return out


def r0_at(z):
    """Base profile radius at height z (profile z is monotonic)."""
    for a, b in zip(DENSE, DENSE[1:]):
        if a.y <= z <= b.y:
            t = (z - a.y) / max(1e-9, b.y - a.y)
            return a.x + (b.x - a.x) * t
    return DENSE[0].x if z < DENSE[0].y else DENSE[-1].x


def _smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


FRONT = -math.pi / 2
# drips: (angle, radial amplitude m, top z of the streak, width m)
DRIPS = [(math.radians(212), 0.036, 0.44, 0.046),
         (math.radians(333), 0.028, 0.33, 0.040),
         (math.radians(100), 0.038, 0.50, 0.050),
         (math.radians(152), 0.022, 0.29, 0.036),
         (math.radians(35), 0.020, 0.24, 0.034)]
NOISE_OFF = Vector((3.7, -1.3, 8.1))
LUMP_OFF = Vector((-5.2, 2.9, 0.6))


def jelly_r(theta, z):
    r0 = r0_at(z)
    # pooled, lobed foot
    foot = 1.0 - _smooth01((z - 0.015) / 0.17)
    lobes = (0.034 * math.cos(5 * theta + 0.7) + 0.020 * math.cos(8 * theta + 2.1)
             + 0.010 * math.cos(13 * theta + 0.3))
    dr = r0 * lobes * foot
    # drips running down the sides (teardrop streaks ending in a pooled bulge)
    for (ta, amp, ztop, w) in DRIPS:
        if z > ztop:
            continue
        s = max(0.0, (z - 0.03) / (ztop - 0.03))
        width = w * (1.25 - 0.75 * s)
        d = _wrap(theta - ta) * r0
        g = math.exp(-(d / width) ** 2)
        bulb = math.exp(-((s - 0.12) / 0.16) ** 2) * 0.45      # rounder drop where it meets the puddle
        dr += amp * g * ((1.0 - s) ** 1.2 + bulb) * _smooth01(s * 5 + 0.3)
    # soft organic bulges (weaker on the face so the eyes sit on a clean surface)
    p = Vector((math.cos(theta) * r0, math.sin(theta) * r0, z)) * 3.1 + NOISE_OFF
    face = math.exp(-(_wrap(theta - FRONT) / 0.65) ** 2) * math.exp(-((z - 0.26) / 0.16) ** 2)
    dr += (0.011 * noise.noise(p) + 0.004 * noise.noise(p * 2.3)) * (1.0 - 0.75 * face)
    # big gentle lumps (not lathe-perfect), faded out at the collar and on the face
    q = Vector((math.cos(theta) * r0, math.sin(theta) * r0, z)) * 1.5 + LUMP_OFF
    collar = _smooth01((0.56 - z) / 0.12)
    dr += 0.020 * noise.noise(q) * collar * (1.0 - 0.8 * face)
    return r0 + dr


def surf(theta, z):
    r = jelly_r(theta, z)
    return Vector((r * math.cos(theta), r * math.sin(theta), z))


def surf_normal(theta, z):
    e = 1e-3
    dt = surf(theta + e, z) - surf(theta - e, z)
    dz = surf(theta, z + e) - surf(theta, z - e)
    n = dt.cross(dz).normalized()
    if n.dot(Vector((math.cos(theta), math.sin(theta), 0))) < 0:
        n = -n
    return n


def build_jelly():
    p = Part("c_jelly")
    bm = p.bm
    rings = []
    for q in resample(DENSE, N_RINGS):
        rings.append([bm.verts.new(surf(2 * math.pi * j / N_AROUND, q.y)) for j in range(N_AROUND)])
    bot = bm.verts.new((0, 0, BASE_Z))
    top = bm.verts.new((0, 0, TOP_POLE_Z))
    n = N_AROUND
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot, rings[0][j], rings[0][i]))
        bm.faces.new((rings[-1][i], rings[-1][j], top))
    p._assign(bm.verts[:], "jelly_teal")
    o = sh.build_comp(p)
    hp.smooth_obj(o, angle=180)
    if "--count" in ARGS:
        print(f"[comp] {o.name:22s} {sh.tris(o)}")
    return o


def jelly_vertex_colour(o):
    """COLOR_0 for the jelly: rgb deepens towards the pooled foot, alpha clears a bit towards the top."""
    me = o.data
    if hp.AO_ATTR in me.color_attributes:
        me.color_attributes.remove(me.color_attributes[hp.AO_ATTR])
    attr = me.color_attributes.new(hp.AO_ATTR, "BYTE_COLOR", "CORNER")
    vc = np.ones((len(me.vertices), 4), dtype=np.float32)
    lo = np.array((0.60, 0.76, 0.80))           # deeper, bluer teal where the jelly pools
    for v in me.vertices:
        z = v.co.z
        t = _smooth01((z - 0.01) / 0.42) ** 0.8
        c = lo + (1.0 - lo) * t
        vc[v.index] = (c[0], c[1], c[2], 1.0 - 0.12 * _smooth01((z - 0.10) / 0.30))
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    attr.data.foreach_set("color", vc[lv].ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find(hp.AO_ATTR)


# ---------------------------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------------------------
COMPS = {"body": [], "valve": [], "eye_L": [], "eye_R": []}
INNER, OUTER, GLASS, DECALS = [], [], [], []
DIAL_INFO = {}


def add(p, part, kind="outer", bevel=None, smooth=40.0, face=None):
    """face=(direction, mats or None): open sheets whose faces must point along `direction`."""
    o = sh.build_comp(p)
    if face:
        n = sh.orient_sheet(o, face[0], face[1])
        if n and "--count" in ARGS:
            print(f"[flip] {o.name}: {n} face(s)")
    if bevel:
        hp.bevel_obj(o, width=bevel[0], segments=bevel[1], angle=bevel[2] if len(bevel) > 2 else 30.0,
                     harden=False)
    hp.smooth_obj(o, angle=smooth)
    COMPS[part].append(o)
    {"inner": INNER, "outer": OUTER, "glass": GLASS, "decal": DECALS}[kind].append(o)
    if "--count" in ARGS:
        print(f"[comp] {o.name:22s} {sh.tris(o)}")
    return o


# ---------------------------------------------------------------------------------------------
# Inner boiler heart (seen through the jelly)
# ---------------------------------------------------------------------------------------------
CORE = Vector((0.0, 0.04, 0.375))
COIL_MAT = "glow_cyan"
DRUM = Vector((0.0, 0.04, 0.0))


def build_inner(eye_backs, mouth_back):
    # glowing aether core
    p = Part("c_core")
    p.ico("glow_cyan", r=0.070, subdiv=3, loc=CORE)
    add(p, "body", "inner", smooth=180)

    # armillary cage around the core
    p = Part("c_cage")
    p.torus("brass", R=0.097, r=0.0060, seg=20, seg2=5, loc=CORE, rot=(14, 0, 0))
    p.torus("brass", R=0.097, r=0.0060, seg=20, seg2=5, loc=CORE, rot=(90, 0, 28))
    add(p, "body", "inner", smooth=60)

    # little vertical boiler drum on the floor of the jelly
    p = Part("c_drum")
    sh.revolve(p, "brass", [(0.0, 0.012), (0.064, 0.012), (0.070, 0.019), (0.072, 0.034), (0.072, 0.046),
                            (0.070, 0.106), (0.062, 0.130), (0.044, 0.146), (0.020, 0.153), (0.0, 0.154)],
               seg=14, M=Matrix.Translation(DRUM))
    add(p, "body", "inner", smooth=40)

    # stem drum -> core + heating coil around it
    p = Part("c_stem")
    p.cyl("brass_dark", r=0.014, h=0.16, seg=8, loc=Vector((0, 0.04, 0.225)))
    pts, rr = [], 0.029
    turns, z0, z1 = 2.5, 0.170, 0.288
    nn = 22
    for i in range(nn + 1):
        t = i / nn
        a = 2 * math.pi * turns * t
        pts.append(Vector((math.cos(a) * rr, 0.04 + math.sin(a) * rr, z0 + (z1 - z0) * t)))
    tube(p, COIL_MAT, pts, 0.0062, seg=5)
    add(p, "body", "inner", smooth=60)

    # feed pipe core -> valve, gauge lines drum -> eyes, steam line drum -> mouth
    p = Part("c_pipes")
    tube(p, "brass_dark", [CORE + Vector((0, 0, 0.06)), Vector((0, 0.035, 0.50)), Vector((0, 0.012, 0.565)),
                           Vector((0, 0.0, VALVE_Z + 0.004))], 0.016, seg=8)
    for back in eye_backs:
        sgn = 1 if back.x > 0 else -1
        a = DRUM + Vector((sgn * 0.055, -0.035, 0.085))
        b = DRUM + Vector((sgn * 0.085, -0.075, 0.14))
        c = back + Vector((0, 0.045, -0.06))
        tube(p, "copper", [a, b, c, back], 0.0065, seg=6)
    tube(p, "brass_dark", [DRUM + Vector((0, -0.06, 0.05)), Vector((0, -0.17, 0.085)), mouth_back],
         0.011, seg=6)
    add(p, "body", "inner", smooth=60)

    # suspended bubbles
    p = Part("c_bubbles")
    for (x, y, z, r) in [(0.13, 0.10, 0.47, 0.020), (-0.16, 0.06, 0.40, 0.016), (0.20, -0.02, 0.15, 0.013),
                         (-0.10, 0.18, 0.21, 0.018)]:
        p.sphere("white", r=r, seg=6, rings=4, loc=(x, y, z))
    add(p, "body", "inner", smooth=180)


# ---------------------------------------------------------------------------------------------
# Pressure-gauge eyes
# ---------------------------------------------------------------------------------------------
# per eye: (dial-frame scale, height, lateral offset) — slightly mismatched gauges = goofy charm
EYES = {"eye_L": (1.08, 0.268, 0.160), "eye_R": (0.96, 0.280, 0.152)}
EYE_OUT = 0.010
GLASS_ALPHA = 0.45       # COLOR_0 alpha on the cover glass: game opacity 0.35 x 0.45 -> a clear glint


def eye_frame(side, s, z, x):
    th = FRONT + side * math.asin(x / r0_at(z))
    P = surf(th, z)
    N = surf_normal(th, z)
    ng = (N * 0.55 + Vector((0, -1, 0)) * 0.45 + Vector((0, 0, 0.05))).normalized()
    C = P + N * EYE_OUT * s
    return C, ng, sh.frame(ng, up=(0, 0, 1), origin=C) @ Matrix.Scale(s, 4)


def build_eye(name, side):
    C, ng, M = eye_frame(side, *EYES[name])

    def dial_dir(phi):          # dial angle phi (deg, clockwise from up) -> (x, y)
        a = math.radians(phi)
        return math.sin(a), math.cos(a)

    # housing can (embedded in the jelly) + back stub
    p = Part(f"c_{name}_housing")
    sh.revolve(p, "brass_dark", [(0.0, -0.064), (0.074, -0.064), (0.086, -0.056), (0.091, -0.040),
                                 (0.092, -0.004)], seg=14, M=M, cap1=True)
    sh.revolve(p, "brass_dark", [(0.0, -0.085), (0.014, -0.085), (0.016, -0.078), (0.016, -0.060)], seg=8, M=M,
               cap1=True)
    add(p, name, "outer", smooth=40)

    # bezel ring (rounded) + screws
    p = Part(f"c_{name}_bezel")
    sh.revolve(p, "brass", [(0.084, 0.000), (0.084, 0.021), (0.090, 0.030), (0.100, 0.029), (0.106, 0.016),
                            (0.103, -0.004)], seg=32, closed=True, M=M)
    for k in range(4):
        x, y = dial_dir(45 + 90 * k)
        sh.revolve(p, "brass_dark", [(0.0055, 0.027), (0.0050, 0.0310), (0.0030, 0.0330), (0.0, 0.0337)],
                   seg=8, M=M @ Matrix.Translation((x * 0.0955, y * 0.0955, 0.0)))
    add(p, name, "outer", smooth=50)

    # dial face + ticks + red zone
    p = Part(f"c_{name}_dial")
    sh.disc(p, "white", 0.0855, z=0.006, seg=32, M=M, fan=True)
    for k in range(11):
        phi = -135 + 27 * k
        x, y = dial_dir(phi)
        major = k % 2 == 0
        L = 0.0140 if major else 0.0090
        rc = 0.0745 - L / 2
        sh.flat_quad(p, "black", x * rc, y * rc, 0.0044 if major else 0.0032, L, ang=-math.radians(phi),
                     z=0.0072, M=M)
    a0, a1 = (math.radians(90 - 135), math.radians(90 - 92)) if side > 0 else \
        (math.radians(90 + 92), math.radians(90 + 135))
    sh.arc_strip(p, "cloth_red", 0.052, 0.0765, a0, a1, z=0.0066, seg=8, M=M)
    o = add(p, name, "decal", smooth=180, face=(ng, None))
    DIAL_INFO[o.name] = (C, ng, 0.0855 * EYES[name][0])

    # needle + pupil hub + catch-lights
    p = Part(f"c_{name}_needle")
    phi_n = side * 24.0
    R = Matrix.Rotation(-math.radians(phi_n), 4, "Z")
    sh.flat_poly(p, "black", [(0.0, -0.026), (0.0050, -0.011), (0.0032, 0.030), (0.0, 0.064),
                              (-0.0032, 0.030), (-0.0050, -0.011)], z=0.0130, thick=0.0025, M=M @ R)
    sh.revolve(p, "black", [(0.0340, 0.0085), (0.0340, 0.0140), (0.0285, 0.0198), (0.0160, 0.0228),
                            (0.0, 0.0236)], seg=20, M=M, cap0=True)
    sh.disc(p, "white", 0.0098, z=0.0234, seg=12, M=M, cx=-0.0118, cy=0.0118)     # same light dir both eyes
    sh.disc(p, "white", 0.0042, z=0.0230, seg=8, M=M, cx=0.0128, cy=-0.0108)
    add(p, name, "outer", smooth=50, face=(ng, {"white"}))

    # glass cover
    p = Part(f"c_{name}_glass")
    sh.revolve(p, "glass", [(0.0855, 0.0205), (0.063, 0.0296), (0.032, 0.0333), (0.0, 0.0340)], seg=24, M=M)
    add(p, name, "glass", smooth=180, face=(ng, None))
    return C, M @ Vector((0, 0, -0.085))


# ---------------------------------------------------------------------------------------------
# Mouth: little brass steam spout ("o")
# ---------------------------------------------------------------------------------------------
MOUTH_Z = 0.142
MOUTH_S = 1.12


def build_mouth():
    P = surf(FRONT, MOUTH_Z)
    N = surf_normal(FRONT, MOUTH_Z)
    n = (N * 0.7 + Vector((0, -1, 0)) * 0.3 + Vector((0, 0, 0.12))).normalized()
    M = sh.frame(n, up=(0, 0, 1), origin=P + N * 0.004) @ Matrix.Scale(MOUTH_S, 4)
    p = Part("c_mouth")
    sh.revolve(p, "brass", [(0.0165, -0.004), (0.0165, 0.010), (0.0215, 0.0170), (0.0300, 0.0172),
                            (0.0360, 0.0090), (0.0340, -0.006)], seg=20, closed=True, M=M)
    sh.revolve(p, "brass_dark", [(0.0170, -0.030), (0.0170, -0.004)], seg=12, M=M, cap0=True)
    sh.disc(p, "black", 0.0172, z=0.003, seg=12, M=M)
    add(p, "body", "outer", smooth=50, face=(n, {"black"}))
    return M @ Vector((0, 0, -0.030))


# ---------------------------------------------------------------------------------------------
# Valve / chimney (pivot at the top of the jelly, spins)
# ---------------------------------------------------------------------------------------------
WHEEL_MAT = "cloth_red"


def build_valve():
    T = Matrix.Translation((0, 0, VALVE_Z))
    # flange collar + hex bolts
    p = Part("c_valve_flange")
    sh.revolve(p, "brass_dark", [(0.0, -0.016), (0.090, -0.016), (0.098, -0.009), (0.099, 0.005),
                                 (0.093, 0.013), (0.062, 0.016), (0.0, 0.017)], seg=20, M=T)
    for k in range(6):
        a = 2 * math.pi * (k + 0.5) / 6
        p.cyl("brass", r=0.0092, h=0.009, seg=6,
              loc=(math.cos(a) * 0.078, math.sin(a) * 0.078, VALVE_Z + 0.0165), rot=(0, 0, math.degrees(a) + 30))
    add(p, "valve", "outer", smooth=40)

    # neck + globe valve body
    p = Part("c_valve_globe")
    sh.revolve(p, "brass", [(0.038, 0.010), (0.038, 0.028), (0.048, 0.038), (0.061, 0.052), (0.067, 0.067),
                            (0.063, 0.084), (0.051, 0.097), (0.037, 0.104), (0.0, 0.105)], seg=22, M=T, cap0=True)
    add(p, "valve", "outer", smooth=45)
    p = Part("c_valve_seam")                     # machined seam band around the globe
    sh.revolve(p, "brass_dark", [(0.0655, 0.0605), (0.0700, 0.0625), (0.0705, 0.0700), (0.0665, 0.0725)],
               seg=22, closed=True, M=T)
    add(p, "valve", "outer", smooth=50)

    # bonnet nut
    p = Part("c_valve_bonnet")
    p.cyl("brass_dark", r=0.034, h=0.020, seg=6, loc=(0, 0, VALVE_Z + 0.110))
    add(p, "valve", "outer", bevel=(0.003, 1, 40), smooth=40)

    # handwheel (horizontal -> reads as turning while the valve spins)
    WZ = VALVE_Z + 0.136
    p = Part("c_valve_wheel")
    p.torus(WHEEL_MAT, R=0.081, r=0.0098, seg=34, seg2=6, loc=(0, 0, WZ))
    p.cyl(WHEEL_MAT, r=0.021, h=0.022, seg=12, loc=(0, 0, WZ))
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        b = a + 0.32
        pts = [Vector((math.cos(a) * 0.017, math.sin(a) * 0.017, WZ)),
               Vector((math.cos(a + 0.18) * 0.045, math.sin(a + 0.18) * 0.045, WZ + 0.002)),
               Vector((math.cos(b) * 0.076, math.sin(b) * 0.076, WZ))]
        tube(p, WHEEL_MAT, pts, 0.0055, seg=6)
    ka = math.radians(-60)
    kx, ky = math.cos(ka) * 0.081, math.sin(ka) * 0.081
    p.cyl("brass_dark", r=0.0058, h=0.024, seg=8, loc=(kx, ky, WZ + 0.016))
    p.sphere("brass", r=0.0110, seg=8, rings=6, loc=(kx, ky, WZ + 0.031))
    add(p, "valve", "outer", smooth=55)

    # chimney (flared, open) + steam cap on posts + finial
    p = Part("c_valve_chimney")
    sh.revolve(p, "brass", [(0.025, 0.112), (0.025, 0.158), (0.029, 0.168), (0.039, 0.186), (0.046, 0.194),
                            (0.046, 0.201), (0.040, 0.204), (0.033, 0.198), (0.0, 0.190)], seg=18, M=T, cap0=True)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        p.cyl("brass_dark", r=0.0030, h=0.016, seg=4,
              loc=(math.cos(a) * 0.040, math.sin(a) * 0.040, VALVE_Z + 0.210))
    sh.revolve(p, "brass", [(0.0, 0.216), (0.046, 0.218), (0.056, 0.223), (0.054, 0.228), (0.036, 0.240),
                            (0.013, 0.247), (0.0, 0.248)], seg=18, M=T)
    p.sphere("brass_dark", r=0.0085, seg=8, rings=5, loc=(0, 0, VALVE_Z + 0.2535))
    add(p, "valve", "outer", smooth=45)


# ---------------------------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------------------------
jelly = build_jelly()
COMPS["body"].append(jelly)
eye_L_c, eye_L_back = build_eye("eye_L", +1)
eye_R_c, eye_R_back = build_eye("eye_R", -1)
mouth_back = build_mouth()
build_inner([eye_L_back, eye_R_back], mouth_back)
build_valve()

# vertex AO: inner parts only see each other (the jelly shell would black them out), outer parts also
# see the jelly (contact shadow where gauges / collar sink in); glass never occludes.
hp.bake_vertex_ao(objs=INNER, occluders=INNER, samples=48, distance=0.10, strength=0.75, floor=0.4, ground=0.0)
hp.bake_vertex_ao(objs=OUTER, occluders=OUTER + [jelly], samples=48, distance=0.07, strength=0.8, floor=0.35,
                  ground=0.0)
for d in DECALS:                     # dials: soft radial bezel shadow instead of ray AO (no interior verts)
    c, n, r = DIAL_INFO[d.name]
    sh.radial_colour(d, c, n, r, edge=0.80, start=0.6)
hp.fill_vertex_color(GLASS, color=(1.0, 1.0, 1.0))
for g in GLASS:                      # glass alpha via COLOR_0 (three.js multiplies material opacity by it)
    a = g.data.color_attributes[hp.AO_ATTR]
    cols = np.ones((len(g.data.loops), 4), dtype=np.float32)
    cols[:, 3] = GLASS_ALPHA
    a.data.foreach_set("color", cols.ravel())
jelly_vertex_colour(jelly)

root = empty("root")
body = sh.join(COMPS["body"], "body", (0, 0, 0))
body.parent = root
valve = sh.join(COMPS["valve"], "valve", (0, 0, VALVE_Z))
valve.parent = body
eye_L = sh.join(COMPS["eye_L"], "eye_L", eye_L_c)
eye_L.parent = body
eye_R = sh.join(COMPS["eye_R"], "eye_R", eye_R_c)
eye_R.parent = body

total = 0
for o in (body, valve, eye_L, eye_R):
    t = sh.tris(o)
    total += t
    print(f"[tris] {o.name:6s} {t}")
print(f"[tris] TOTAL {total}")
if total > 8000:
    print(f"[WARN] slime: {total} tris exceeds budget 8000")
print("[mats]", sorted({m.name for o in (body, valve, eye_L, eye_R) for m in o.data.materials}))

hp.export_glb_hp("slime")


# ---------------------------------------------------------------------------------------------
# Previews (after export; only touch preview-side material settings)
# ---------------------------------------------------------------------------------------------
def preview_materials():
    """Mimic the game: jelly opacity 0.72 x vertex alpha, glass opacity 0.35, both alpha-blended."""
    for name, alpha, use_vcol in (("jelly_teal", 0.72, True), ("glass", 0.35, True)):
        m = bpy.data.materials.get(name)
        if not m:
            continue
        nt = m.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        if use_vcol:
            at = nt.nodes.new("ShaderNodeVertexColor")
            at.layer_name = hp.AO_ATTR
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = alpha
            nt.links.new(at.outputs["Alpha"], mul.inputs[0])
            nt.links.new(mul.outputs[0], bsdf.inputs["Alpha"])
        else:
            bsdf.inputs["Alpha"].default_value = alpha
        bsdf.inputs["Roughness"].default_value = 0.15 if name.startswith("jelly") else 0.05
        try:
            m.surface_render_method = "DITHERED" if name.startswith("jelly") else "BLENDED"
        except Exception:
            pass


if "--no-preview" not in ARGS:
    preview_materials()
    hp.render_views("slime")
    if "--extra" in ARGS:
        hp.render_hp("slime_eyes", target=((0, -0.40, 0.25), 0.30), azimuth=10, elevation=10)
        hp.render_hp("slime_top", azimuth=30, elevation=55)
        hp.render_hp("slime_valve", target=((0, 0, VALVE_Z + 0.12), 0.16), azimuth=30, elevation=25)
        hp.render_hp("slime_game", azimuth=25, elevation=25, dist_k=7.0)
        for nm, sc in (("slime_squash", (1.12, 1.12, 0.84)), ("slime_stretch", (0.92, 0.92, 1.16))):
            body.scale = sc
            bpy.context.view_layer.update()
            hp.render_hp(nm, azimuth=30, elevation=15)
        body.scale = (1, 1, 1)
