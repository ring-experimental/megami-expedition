"""Steam-works props: gas lamp, steam pipes, vent, fence, giant gear monument.

Builders for props.glb (assembled by model_props.py). Each builder returns the prop's top-level
object named exactly as in ASSET_SPEC.md, origin at its base centre on the ground (z = 0).

Hi-poly pass (2026-10-11): everything is rebuilt from lathed profiles, chamfered extrusions and sweeps
(hp_steam_helpers.py) — chamfers are modelled, not bevel-modifier generated, so triangle counts stay
predictable. Each builder ends with _finish(): smooth shading + sharp edges (35 deg) and vertex AO
(hp.bake_tree_ao, optional tint for grime / verdigris). Child meshes are prefixed with the prop name.
Group materials: stm_soot (pipe bores, gaskets), stm_moss_dark (moss shading, moss-filled cracks).

Test this group alone (no props.glb export):
    blender -b --factory-startup -P tools/blender/model_props.py -- --group=steam --previews [--back] [--only=prop_x]
Test export to a scratch dir:  ... -- --group=steam --out=<dir>
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403   (Part, empty, get_mat, ...)
from mathutils import Matrix, Vector  # noqa: E402
import hp_helpers as hp  # noqa: E402
from hp_steam_helpers import (  # noqa: E402
    TAU, place, T, Rot, S, axis_x, axis_y, axis_my, fbm, smoothstep, revolve, torus_m, ball, rrect,
    offset_outline, prism, ring_prism, gear_outline, at_angles, gear, sweep, tube, bezier, spiral, arc,
    hex_bolt, rivet, moss_pad, lumpy_blob, rubble, cull_faces, paint_faces)


def setup_mats():
    """Group-specific materials. Name them with the group prefix (e.g. 'stm_bark'), or 'glow_stm_*' /
    'jelly_stm_*' for emissive / translucent ones, so groups never clash inside props.glb."""
    get_mat("stm_soot", hex="#1e1a17", metallic=0.3, roughness=0.85)       # pipe bores, gaskets, pits
    get_mat("stm_moss_dark", hex="#4c6b2a", roughness=0.95)                # shaded moss variation


def _finish(root, angle=35.0, ao=None, skip=(), floor=None):
    """Smooth-shade every mesh of the prop (sharp edges by angle) and bake its vertex AO.
    floor: {material: min value} raises the baked colour of faces that should stay bright even when
    recessed (e.g. gauge dials sitting inside their bezel)."""
    for o in hp.tree_meshes(root):
        if o.name not in skip:
            hp.smooth_obj(o, angle)
    hp.bake_tree_ao(root, **(ao or {}))
    for o in hp.tree_meshes(root) if floor else ():
        me = o.data
        attr = me.color_attributes.get(hp.AO_ATTR)
        names = [m.name if m else "" for m in me.materials]
        for poly in me.polygons:
            lo = floor.get(names[poly.material_index]) if poly.material_index < len(names) else None
            if lo is None or attr is None:
                continue
            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                c = attr.data[li].color
                attr.data[li].color = (max(c[0], lo), max(c[1], lo), max(c[2], lo), c[3])
    return root


def collar(p, z0, z1, r_out, r_in, ch, seg=20, mat="brass"):
    """Open brass collar ring around a shaft (inner wall omitted: it is buried in the shaft)."""
    revolve(p, [(z0, r_in), (z0, r_out - ch), (z0 + ch, r_out), (z1 - ch, r_out), (z1, r_out - ch), (z1, r_in)],
            seg=seg, mats=mat, cap_bottom=False, cap_top=False)


def small_gear(p, r_root, r_tip, teeth, thick, r_in, M, phase, spokes, hub_r, hub_len, mat="brass",
               hub_mat="brass_dark"):
    """Cheap decorative gear (trapezoid teeth, no chamfers: they would be sub-pixel at game distance)."""
    out, angs = gear_outline(r_root, r_tip, teeth, base=0.56, top=0.32, phase=phase, gap_mid=False)
    out2, angs2 = [], []
    for i in range(0, len(out), 6):   # drop the flank mid points -> 4 points per tooth
        for j in (0, 2, 3, 5):
            out2.append(out[i + j])
            angs2.append(angs[i + j])
    ring_prism(p, mat, out2, at_angles(angs2, r_in), thick, ch=0.0, ch_in=0.0, M=M)
    for i in range(spokes):
        a = phase + TAU * i / spokes + math.pi / teeth
        L = r_in - hub_r * 0.5
        mid = hub_r * 0.5 + L / 2
        prism(p, mat, rrect(L, r_in * 0.26), thick * 0.7,
              M=M @ T(mid * math.cos(a), mid * math.sin(a), 0) @ Matrix.Rotation(a, 4, "Z"))
    revolve(p, [(-hub_len / 2, hub_r), (hub_len / 2 - hub_r * 0.15, hub_r), (hub_len / 2, hub_r * 0.8)],
            seg=8, M=M, mats=hub_mat, cap_bottom=False)


# ---------------------------------------------------------------------------
# prop_lamp — ornate cast-iron gas street lamp with a magic aether bulb
# ---------------------------------------------------------------------------

def build_lamp():
    nm = "prop_lamp"
    root = empty(nm, size=0.5)
    p = Part(nm + "_body")

    # -- stone plinth slab (chamfered top edge, slightly irregular)
    prism(p, "stone_dark", rrect(0.62, 0.62, 0.07, 2), 0.1, ch=0.0, back_ch=0.02, M=T(0, 0, 0.05),
          jitter=0.006, seed=3)

    # -- moulded cast-iron base: foot band, torus moulding, cove, fluted pedestal, brass band, bead
    def ped_flutes(a, z):
        return 1.0 - 0.12 * (0.5 + 0.5 * math.cos(6 * a)) if 0.28 < z < 0.535 else 1.0

    base = [
        (0.098, 0.256, "iron"), (0.132, 0.256, "iron"), (0.144, 0.244, "iron"), (0.158, 0.252, "iron"),
        (0.174, 0.259, "iron"), (0.19, 0.252, "iron"), (0.2, 0.237, "iron"), (0.218, 0.215, "iron"),
        (0.24, 0.206, "iron"), (0.262, 0.197, "iron"), (0.3, 0.2, "iron"), (0.36, 0.198, "iron"),
        (0.45, 0.174, "iron"), (0.525, 0.154, "iron"),
        (0.55, 0.148, "brass"), (0.562, 0.162, "brass"), (0.6, 0.166, "brass"), (0.614, 0.158, "brass"),
        (0.624, 0.146, "iron"), (0.66, 0.122, "iron"), (0.725, 0.106, "brass"), (0.742, 0.121, "brass"),
        (0.76, 0.118, "brass"), (0.775, 0.1, "iron"),
    ]
    revolve(p, [(z, r) for z, r, _ in base], seg=24, mats=[m for _, _, m in base[:-1]], rfunc=ped_flutes,
            cap_bottom=False, cap_top=False)

    # maintenance door on the pedestal front (-Y): arched panel, raised field, brass keyhole knob
    tilt = math.atan(0.024 / 0.09)
    n_door = (0.0, -math.cos(tilt), math.sin(tilt))
    arch_pts = [(-0.045, -0.075), (0.045, -0.075)] + [(0.045 * math.cos(math.radians(a)),
                                                         0.03 + 0.045 * math.sin(math.radians(a)))
                                                        for a in range(0, 181, 30)]
    Md = place((0, -0.172, 0.405), n=n_door)
    prism(p, "iron", arch_pts, 0.04, ch=0.0, back_ch=0.006, M=Md)
    prism(p, "iron", offset_outline(arch_pts, -0.014), 0.044, ch=0.0, back_ch=0.004, M=Md @ T(0, 0, 0.004))
    revolve(p, [(0.0, 0.011), (0.008, 0.011), (0.012, 0.006), (0.013, 0.0)], seg=10,
            M=Md @ T(0.022, -0.005, 0.024), mats="brass")
    for hz in (-0.05, 0.02):   # hinge knuckles
        revolve(p, [(-0.012, 0.006), (0.012, 0.006)], seg=6, M=Md @ T(-0.047, hz, 0.019) @ Rot("X", 90),
                mats="brass_dark")

    # -- fluted shaft (10 flutes), tapering
    def shaft_r(z):
        return 0.085 - (z - 0.835) * (0.018 / 1.55)

    def shaft_flutes(a, z):
        return 1.0 - 0.14 * (0.5 + 0.5 * math.cos(8 * a)) if 0.87 < z < 2.4 else 1.0

    zs = [0.77, 0.835, 0.885, 1.40, 1.58, 2.36, 2.44]      # rings just outside the collars (clean AO)
    revolve(p, [(z, shaft_r(z)) for z in zs], seg=32, mats="iron", rfunc=shaft_flutes,
            cap_bottom=False, cap_top=False)

    # brass collars
    collar(p, 0.80, 0.874, 0.101, 0.078, 0.009)
    revolve(p, [(1.42, 0.074), (1.425, 0.098), (1.448, 0.1), (1.462, 0.112), (1.49, 0.117), (1.518, 0.112),
                (1.532, 0.1), (1.555, 0.098), (1.56, 0.074)], seg=24, mats="brass", cap_bottom=False, cap_top=False)
    collar(p, 2.37, 2.445, 0.089, 0.064, 0.008)

    # -- decorative meshing gears on the shaft front (big below, small above)
    small_gear(p, 0.112, 0.138, 10, 0.022, 0.086, axis_my((0, -0.104, 1.08)), math.radians(72), 4, 0.03, 0.054)
    small_gear(p, 0.075, 0.1, 7, 0.02, 0.058, axis_my((0, -0.101, 1.2925)), math.radians(270), 3, 0.024, 0.05)

    # -- ladder bar with brass ball ends, sleeve and flat-bar scroll brackets
    zb = 2.30
    revolve(p, [(-0.335, 0.017), (0.335, 0.017)], seg=12, M=axis_x((0, 0, zb)), mats="iron",
            cap_bottom=False, cap_top=False)
    for sx in (-1, 1):
        Mb = T(sx * 0.33, 0, zb) @ Rot("Y", 90 * sx)
        revolve(p, [(0.0, 0.024), (0.014, 0.024), (0.022, 0.027), (0.034, 0.036), (0.05, 0.039),
                    (0.066, 0.034), (0.078, 0.02), (0.084, 0.0)], seg=6, M=Mb, mats="brass", cap_bottom=False)
    collar(p, zb - 0.03, zb + 0.03, 0.092, 0.066, 0.008)
    sec = rrect(0.022, 0.011)
    for sx in (-1, 1):
        pts = bezier((0.078, 0, 2.03), (0.098, 0, 2.2), (0.17, 0, 2.2765), (0.285, 0, 2.2765), 7)
        pts += spiral((0.285, 0, 2.2265), 0.05, 0.013, 90, -250, 15)[1:]
        pts = [(sx * x, y, z) for x, y, z in pts]
        sweep(p, "iron", pts, sec, up=(0, 1, 0))

    # -- capital (trumpet flare) with brass rim
    cap = [(2.44, 0.066, "iron"), (2.5, 0.075, "iron"), (2.535, 0.087, "iron"), (2.565, 0.107, "iron"),
           (2.592, 0.133, "iron"), (2.612, 0.154, "brass"), (2.63, 0.172, "brass"), (2.658, 0.176, "brass"),
           (2.666, 0.166, "iron")]
    revolve(p, [(z, r) for z, r, _ in cap], seg=24, mats=[m for _, _, m in cap[:-1]], cap_bottom=False,
            cap_top=False)

    # -- hexagonal lantern: tray, tapered posts, rails, glass panes, roof, crown, finial
    def rc(z):  # corner radius of the cage
        return 0.158 + (z - 2.715) * (0.054 / 0.5)

    revolve(p, [(2.664, 0.12), (2.672, 0.15), (2.686, 0.174), (2.7, 0.186), (2.712, 0.186), (2.72, 0.176),
                (2.72, 0.0)], seg=6, mats="brass")
    for k in range(6):
        a = math.radians(60 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        sweep(p, "brass", [d * rc(2.712) + Vector((0, 0, 2.712)), d * rc(3.218) + Vector((0, 0, 3.218))],
              rrect(0.02, 0.02), up=d)
    for z0, z1 in ((2.715, 2.745), (3.186, 3.216)):
        revolve(p, [(z0, rc(z0) - 0.006), (z0, rc(z0) + 0.012), (z1, rc(z1) + 0.012), (z1, rc(z1) - 0.006)],
                seg=6, mats="brass", closed=True)
    for k in range(6):
        a0, a1 = math.radians(60 * k), math.radians(60 * (k + 1))
        vs = []
        for z, a in ((2.745, a0), (2.745, a1), (3.186, a1), (3.186, a0)):
            r = rc(z) - 0.004
            vs.append((r * math.cos(a), r * math.sin(a), z))
        p.poly("glass", vs, [(0, 1, 2, 3)])
    roof = [(3.212, 0.17, "brass"), (3.212, 0.236, "brass"), (3.222, 0.246, "brass"), (3.236, 0.246, "brass"),
            (3.242, 0.238, "iron"), (3.25, 0.252, "iron"), (3.258, 0.255, "iron"), (3.266, 0.247, "iron"),
            (3.29, 0.212, "iron"), (3.32, 0.173, "iron"), (3.355, 0.136, "iron"), (3.39, 0.105, "iron"),
            (3.425, 0.082, "iron"), (3.425, 0.0, "iron")]
    revolve(p, [(z, r) for z, r, _ in roof], seg=6, mats=[m for _, _, m in roof[:-1]])
    for k in range(6):
        a = math.radians(60 * k)
        ball(p, "brass", 0.017, seg=6, rings=3, M=T(0.258 * math.cos(a), 0.258 * math.sin(a), 3.266))
    revolve(p, [(3.41, 0.066), (3.42, 0.074), (3.468, 0.068), (3.476, 0.08), (3.492, 0.08), (3.5, 0.05),
                (3.512, 0.026), (3.53, 0.026), (3.545, 0.031), (3.565, 0.03), (3.582, 0.018), (3.594, 0.009),
                (3.628, 0.0)], seg=12, mats="brass", cap_bottom=False)

    # -- bulb socket + brass claws holding the bulb
    revolve(p, [(2.72, 0.022), (2.79, 0.02), (2.8, 0.03), (2.82, 0.042), (2.84, 0.048), (2.85, 0.044),
                (2.85, 0.0)], seg=10, mats="brass", cap_bottom=False)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [d * r + Vector((0, 0, z)) for z, r in ((2.842, 0.047), (2.875, 0.068), (2.915, 0.08),
                                                       (2.955, 0.08), (2.985, 0.071), (3.0, 0.062))]
        tube(p, "brass", pts, 0.0045, seg=4)

    # -- copper gas line up the back of the shaft, with gland nut and clamps
    gl = [(0, 0.132, 0.6), (0, 0.132, 0.9), (0, 0.132, 1.5), (0, 0.132, 2.36), (0, 0.13, 2.42), (0, 0.123, 2.46),
          (0, 0.111, 2.495), (0, 0.092, 2.535)]
    tube(p, "copper", gl, 0.013, seg=6)
    revolve(p, [(0.62, 0.02), (0.65, 0.02), (0.655, 0.016)], seg=6, M=T(0, 0.132, 0), mats="brass", phase=0.5,
            cap_bottom=False)
    for zc in (1.0, 1.95):
        prism(p, "brass", rrect(0.05, 0.075, 0.012, 1, cy=0.012), 0.024, M=T(0, 0.112, zc))

    body = p.build(root)

    b = Part(nm + "_bulb")
    revolve(b, [(2.835, 0.0), (2.842, 0.026), (2.862, 0.052), (2.895, 0.07), (2.935, 0.076), (2.975, 0.07),
                (3.015, 0.054), (3.05, 0.032), (3.075, 0.012), (3.088, 0.0)], seg=14, mats="glow_cyan")
    b.build(root)

    def tint(pw, nw):
        k = 0.8 + 0.2 * smoothstep(0.08, 0.7, pw.z)
        return (k, k, k)

    return _finish(root, ao=dict(distance=0.35, samples=48, strength=0.85, tint=tint))


# ---------------------------------------------------------------------------
# prop_pipe — thick copper steam pipe (two bolted sections), open flanged ends, saddle supports,
#             valve with hand wheel, pressure gauge on a siphon loop
# ---------------------------------------------------------------------------

PIPE_CZ = 0.72


def _mirror_profile(left, centre, end_and_bore):
    """left: [(x, r, span_mat)] from x = -E up to the centre; centre: points crossing x = 0;
    returns the closed loop left + centre + mirrored(left) + end_and_bore."""
    pts = list(left) + list(centre)
    n = len(left)
    for i in range(n - 1, -1, -1):
        x, r, _ = left[i]
        pts.append((-x, r, left[i - 1][2] if i > 0 else "brass"))
    return pts + list(end_and_bore)


def _pipe_profile(E=3.0, R=0.4, RI=0.34, weld_x=1.25):
    """Closed (x, r, mat) loop for a thick-walled pipe from -E..E: flanged ends, weld beads, a bolted
    flange pair in the middle, soot-dark bore. Revolved around X it is one closed manifold."""
    left = [
        (-E, 0.505, "brass"), (-E + 0.014, 0.53, "brass"), (-E + 0.126, 0.53, "brass"),
        (-E + 0.14, 0.507, "brass"), (-E + 0.14, 0.45, "brass"), (-E + 0.25, R, "copper"),
        (-weld_x - 0.018, R, "brass_dark"), (-weld_x, R + 0.012, "brass_dark"), (-weld_x + 0.018, R, "copper"),
        (-0.25, R, "brass"), (-0.135, 0.45, "brass"),
        (-0.135, 0.507, "brass"), (-0.122, 0.522, "brass"), (-0.024, 0.522, "brass"), (-0.012, 0.508, "stm_soot"),
    ]
    centre = [(-0.012, 0.494, "stm_soot"), (0.012, 0.494, "stm_soot")]
    # end face with a raised gasket face, chamfered bore lip, soot-dark bore
    bore = [(E, 0.432, "brass"), (E + 0.012, 0.42, "brass"), (E + 0.012, 0.36, "brass"),
            (E - 0.006, RI, "stm_soot"), (E - 0.5, RI, "stm_soot"), (-(E - 0.5), RI, "stm_soot"),
            (-(E - 0.006), RI, "brass"), (-E - 0.012, 0.36, "brass"), (-E - 0.012, 0.42, "brass"),
            (-E, 0.432, "brass")]
    return _mirror_profile(left, centre, bore)


def _handwheel(p, center, n, R=0.16, r=0.016, spokes=5, mat="paint_red", hub_mat="brass_dark", seg=20):
    """Valve hand wheel: rim torus, gently curved spokes, hex hub nut. Axis along n."""
    M = place(center, n=n)
    torus_m(p, mat, R, r, seg=seg, seg2=6, M=M)
    for i in range(spokes):
        a = TAU * i / spokes
        pts = [(math.cos(a) * 0.02, math.sin(a) * 0.02, 0.0),
               (math.cos(a + 0.12) * R * 0.5, math.sin(a + 0.12) * R * 0.5, -0.005),
               (math.cos(a + 0.3) * (R - r * 0.4), math.sin(a + 0.3) * (R - r * 0.4), 0.0)]
        tube(p, mat, [tuple(M @ Vector(q)) for q in pts], r * 0.62, seg=5, cap_start=False, cap_end=False)
    revolve(p, [(-0.022, R * 0.17), (0.012, R * 0.17), (0.02, R * 0.12), (0.022, 0.0)], seg=6, M=M, mats=hub_mat,
            phase=math.pi / 6, cap_bottom=False)


def _gauge(p, center, n, r=0.12, mat="brass", needle=40.0, seg=16, ink="black", cap_mat="brass_dark"):
    """Pressure gauge: brass case + bezel, white dial with ticks, red zone, black needle. Faces n."""
    Mg = place(center, n=n)
    revolve(p, [(-0.042, 0.045), (-0.036, r * 0.82), (-0.026, r * 0.96), (0.0, r), (0.012, r), (0.02, r * 0.9),
                (0.016, r * 0.84), (0.006, r * 0.84)], seg=seg, M=Mg, mats=mat, cap_top=False)
    revolve(p, [(0.004, r * 0.85), (0.0062, 0.0)], seg=seg, M=Mg, mats="white", cap_bottom=False)
    rd = r * 0.72
    for k in range(7):
        a = math.radians(225 - 45 * k)
        L = r * (0.18 if k % 3 == 0 else 0.11)
        rr = rd - L / 2
        prism(p, ink, rrect(L, r * 0.04), 0.003, M=Mg @ T(rr * math.cos(a), rr * math.sin(a), 0.0075)
              @ Matrix.Rotation(a, 4, "Z"))
    red = [(rd * 1.02 * math.cos(math.radians(a)), rd * 1.02 * math.sin(math.radians(a))) for a in range(-45, 1, 15)]
    red += [(rd * 0.84 * math.cos(math.radians(a)), rd * 0.84 * math.sin(math.radians(a))) for a in range(0, -46, -15)]
    prism(p, "paint_red", red, 0.003, M=Mg @ T(0, 0, 0.0075))
    prism(p, ink, [(-r * 0.05, -r * 0.13), (0.0, -r * 0.17), (r * 0.05, -r * 0.13), (r * 0.02, r * 0.66),
                       (-r * 0.02, r * 0.66)], 0.004,
          M=Mg @ T(0, 0, 0.011) @ Matrix.Rotation(-math.radians(needle), 4, "Z"))
    revolve(p, [(0.008, r * 0.09), (0.016, r * 0.07), (0.019, 0.0)], seg=8, M=Mg, mats=cap_mat, cap_bottom=False)
    return Mg


def build_pipe():
    nm = "prop_pipe"
    root = empty(nm, size=0.5)
    cz = PIPE_CZ
    E, R = 3.0, 0.4
    p = Part(nm + "_body")
    prof = _pipe_profile(E, R)
    Mx = T(0, 0, cz) @ Rot("Y", 90)          # local z -> +X, local x -> -Z
    revolve(p, [(x, r) for x, r, _ in prof], seg=32, M=Mx, mats=[m for _, _, m in prof], closed=True,
            phase=math.pi / 32)

    # -- flange bolts: hex heads on the inner face of the end flanges, thread stubs on the end face
    for sx in (-1, 1):
        for i in range(8):
            a = TAU * (i + 0.5) / 8
            y, z = 0.478 * math.cos(a), cz + 0.478 * math.sin(a)
            hex_bolt(p, "brass_dark", place((sx * (E - 0.14), y, z), n=(-sx, 0, 0), spin=a), r=0.027, h=0.026,
                     chamfer=False)
            hex_bolt(p, "brass_dark", place((sx * E, y, z), n=(sx, 0, 0), spin=a), r=0.027, h=0.022,
                     chamfer=False)
    # middle flange pair: heads on the -X flange, nuts + thread stubs on the +X flange
    for i in range(8):
        a = TAU * i / 8
        y, z = 0.478 * math.cos(a), cz + 0.478 * math.sin(a)
        hex_bolt(p, "brass_dark", place((-0.135, y, z), n=(-1, 0, 0), spin=a), r=0.027, h=0.026, chamfer=False)
        hex_bolt(p, "brass_dark", place((0.135, y, z), n=(1, 0, 0), spin=a), r=0.027, h=0.026, chamfer=False)

    # -- saddle supports: base plate, cradle web + rib, brass clamp strap with bolted lugs
    for sx in (-1, 1):
        x = sx * 1.7
        prism(p, "iron", rrect(0.44, 0.86, 0.06, 2), 0.05, ch=0.0, back_ch=0.012, M=T(x, 0, 0.025))
        rr = R + 0.004
        top = [(rr * math.cos(math.radians(-35 - 110 * t / 8)), cz + rr * math.sin(math.radians(-35 - 110 * t / 8)))
               for t in range(9)]
        zt = top[0][1]
        web = [(-0.27, 0.05), (0.27, 0.05), (0.27, 0.1), (0.338, zt - 0.035), (0.338, zt)]
        web += top[1:-1]
        web += [(-0.338, zt), (-0.338, zt - 0.035), (-0.27, 0.1)]
        prism(p, "iron", web, 0.15, ch=0.012, M=T(x, 0, 0) @ Rot("Z", 90) @ Rot("X", 90))
        prism(p, "iron", [(-0.17, 0.05), (0.17, 0.05), (0.06, cz - R + 0.02), (-0.06, cz - R + 0.02)],
              0.05, ch=0.008, M=T(x, 0, 0) @ Rot("X", 90))
        pts = [(x, (R + 0.011) * math.cos(math.radians(a)), cz + (R + 0.011) * math.sin(math.radians(a)))
               for a in [-35 + 250 * t / 16 for t in range(17)]]
        sweep(p, "brass", pts, rrect(0.075, 0.016), up=(1, 0, 0))
        for sy in (-1, 1):
            ly = sy * 0.378
            prism(p, "brass", rrect(0.09, 0.08, 0.014, 1), 0.026, ch=0.0, back_ch=0.005, M=T(x, ly, zt + 0.013))
            hex_bolt(p, "brass_dark", place((x, ly + sy * 0.006, zt + 0.026), n=(0, 0, 1)), r=0.018, h=0.016,
                     chamfer=False, stub=True)
            for bx in (-1, 1):
                hex_bolt(p, "brass_dark", place((x + bx * 0.15, sy * 0.34, 0.05), n=(0, 0, 1)), r=0.022, h=0.02,
                         chamfer=False)

    # -- valve on top: branch stub, bolted flange, globe body, hex bonnet, stem, red hand wheel
    vx = 0.95
    Mv = T(vx, 0, cz)
    revolve(p, [(0.3, 0.072), (0.47, 0.072), (0.475, 0.122), (0.5, 0.126), (0.506, 0.118)], seg=16, M=Mv,
            mats=["copper", "brass", "brass", "brass"], cap_bottom=False, cap_top=False)
    for i in range(4):
        a = TAU * (i + 0.5) / 4
        hex_bolt(p, "brass_dark", place((vx + 0.104 * math.cos(a), 0.104 * math.sin(a), cz + 0.506), n=(0, 0, 1)),
                 r=0.013, h=0.013, chamfer=False)
    revolve(p, [(0.5, 0.075), (0.53, 0.098), (0.565, 0.112), (0.6, 0.11), (0.63, 0.092), (0.645, 0.07)],
            seg=16, M=Mv, mats="brass", cap_bottom=False, cap_top=False)
    revolve(p, [(0.64, 0.066), (0.69, 0.066), (0.695, 0.05), (0.73, 0.04), (0.735, 0.03)], seg=6, M=Mv,
            mats="brass_dark", cap_bottom=False)
    revolve(p, [(0.73, 0.014), (0.84, 0.014)], seg=8, M=Mv, mats="brass_dark", cap_bottom=False, cap_top=False)
    _handwheel(p, (vx, 0, cz + 0.82), (0, 0, 1), R=0.165, r=0.017, spokes=5)

    # -- pressure gauge on a pigtail siphon, dial facing front (-Y), tilted up 15 deg
    gx = -0.95
    revolve(p, [(0.3, 0.03), (0.47, 0.03), (0.475, 0.042), (0.5, 0.042), (0.505, 0.022)], seg=6,
            M=T(gx, 0, cz), mats="brass_dark", cap_bottom=False, cap_top=False, phase=math.pi / 6)
    loop = [(gx, 0, cz + 0.5), (gx, 0, cz + 0.56)]
    for k in range(1, 13):
        a = math.radians(180 - 360 * k / 12)
        loop.append((gx + 0.05 + 0.05 * math.cos(a), -0.03 * k / 12, cz + 0.56 + 0.05 * math.sin(a)))
    loop += [(gx, -0.03, cz + 0.6), (gx, -0.03, cz + 0.65)]
    tube(p, "copper", loop, 0.011, seg=5, cap_start=False)
    revolve(p, [(cz + 0.6, 0.02), (cz + 0.635, 0.02)], seg=6, M=T(gx, -0.03, 0), mats="brass_dark",
            phase=math.pi / 6, cap_bottom=True)
    tilt = math.radians(15)
    _gauge(p, (gx, -0.04, cz + 0.755), (0, -math.cos(tilt), math.sin(tilt)), r=0.12, needle=35)

    p.build(root)

    def tint(pw, nw):
        g = smoothstep(0.15, 0.85, pw.z)
        return (0.74 + 0.26 * g, 0.8 + 0.2 * g, 0.78 + 0.22 * g)

    return _finish(root, ao=dict(distance=0.45, samples=48, strength=0.85, tint=tint), floor={"white": 0.85})


# ---------------------------------------------------------------------------
# prop_pipe_arch — copper steam main arching over the path (walk-under), aether sight-glasses in the
#                  legs, bolted joints, riveted junction drum with valve wheel and steam whistle
# ---------------------------------------------------------------------------

ARCH_LX, ARCH_R, ARCH_RB, ARCH_ZE = 2.7, 0.3, 0.92, 2.98


def build_pipe_arch():
    nm = "prop_pipe_arch"
    root = empty(nm, size=0.5)
    LX, R, RB, ZE = ARCH_LX, ARCH_R, ARCH_RB, ARCH_ZE
    ZT = ZE + RB                       # top centre line: span underside 3.60 m, junction drum 3.51 m
    p = Part(nm + "_body")

    # -- main pipe: legs above the sight-glasses, smooth 90 deg elbows (12 segments), top span
    # (rings sit just outside collars/flanges so hidden vertices don't smear dark AO along the pipe)
    pts = [(-LX, 0, 1.79), (-LX, 0, 2.4), (-LX, 0, ZE)]
    pts += arc((-LX + RB, 0, ZE), RB, 180, 90, 12)[1:]
    pts += [(-1.25, 0, ZT), (-0.55, 0, ZT), (0.55, 0, ZT), (1.25, 0, ZT)]
    pts += arc((LX - RB, 0, ZE), RB, 90, 0, 12)
    pts += [(LX, 0, 2.4), (LX, 0, 1.79)]
    tube(p, "copper", pts, R, seg=24, cap_start=False, cap_end=False)
    # brass joint bands where the elbows meet the top span
    for sx in (-1, 1):
        revolve(p, [(-0.05, R - 0.004), (-0.05, R + 0.016), (-0.036, R + 0.028), (0.036, R + 0.028),
                    (0.05, R + 0.016), (0.05, R - 0.004)], seg=20, M=T(sx * (LX - RB - 0.08), 0, ZT) @ Rot("Y", 90),
                mats="brass", cap_bottom=False, cap_top=False)

    for sx in (-1, 1):
        x = sx * LX
        # stone footing
        prism(p, "stone_dark", rrect(0.92, 0.92, 0.08, 2), 0.32, ch=0.0, back_ch=0.035, M=T(x, 0, 0.16),
              jitter=0.012, seed=7 + sx)
        # base flange with neck, gusset ribs and anchor bolts
        revolve(p, [(0.318, 0.44), (0.388, 0.45), (0.4, 0.438), (0.4, 0.35), (0.47, R + 0.012), (0.53, R + 0.002)],
                seg=24, M=T(x, 0, 0), mats="brass", cap_bottom=False, cap_top=False)
        for k in range(4):
            a = 45 + 90 * k
            prism(p, "brass", [(R - 0.02, 0.4), (0.435, 0.4), (0.435, 0.43), (R + 0.03, 0.6), (R - 0.02, 0.6)],
                  0.04, ch=0.007, M=T(x, 0, 0) @ Rot("Z", a) @ Rot("X", 90))
        for k in range(4):
            for da in (-20, 20):
                a = math.radians(90 * k + da)
                hex_bolt(p, "brass_dark", place((x + 0.395 * math.cos(a), 0.395 * math.sin(a), 0.4), spin=a),
                         r=0.024, h=0.022, chamfer=False)
        # lower leg
        tube(p, "copper", [(x, 0, 0.5), (x, 0, 0.56), (x, 0, 1.17), (x, 0, 1.22)], R, seg=24, cap_start=False,
             cap_end=False)
        # aether sight-glass: brass collars, glowing core, glass tube, cage bars
        for z0, z1 in ((1.2, 1.29), (1.71, 1.8)):
            revolve(p, [(z0, R - 0.01), (z0, 0.352), (z0 + 0.012, 0.365), (z1 - 0.012, 0.365), (z1, 0.352),
                        (z1, R - 0.01)], seg=24, M=T(x, 0, 0), mats="brass", cap_bottom=False, cap_top=False)
        revolve(p, [(1.29, 0.235), (1.71, 0.235)], seg=16, M=T(x, 0, 0), mats="glow_cyan", cap_bottom=False,
                cap_top=False)
        revolve(p, [(1.29, 0.29), (1.71, 0.29)], seg=20, M=T(x, 0, 0), mats="glass", cap_bottom=False,
                cap_top=False)
        for k in range(6):
            a = math.radians(30 + 60 * k)
            d = Vector((math.cos(a), math.sin(a), 0))
            c = Vector((x, 0, 0)) + d * 0.315
            sweep(p, "brass", [c + Vector((0, 0, 1.28)), c + Vector((0, 0, 1.72))], rrect(0.03, 0.026), up=d)
        # bolted flange pair below the elbow
        revolve(p, [(2.43, R + 0.004), (2.475, 0.35), (2.475, 0.408), (2.545, 0.408), (2.545, 0.394),
                    (2.555, 0.394), (2.555, 0.408), (2.625, 0.408), (2.625, 0.35), (2.67, R + 0.004)], seg=24,
                M=T(x, 0, 0), mats=["brass"] * 3 + ["stm_soot"] * 3 + ["brass"] * 3, cap_bottom=False,
                cap_top=False)
        for k in range(6):
            a = math.radians(30 + 60 * k)
            bx, by = x + 0.375 * math.cos(a), 0.375 * math.sin(a)
            hex_bolt(p, "brass_dark", place((bx, by, 2.475), n=(0, 0, -1), spin=a), r=0.022, h=0.02, chamfer=False)
            hex_bolt(p, "brass_dark", place((bx, by, 2.625), spin=a), r=0.022, h=0.02, chamfer=False, stub=True)

    # -- riveted junction drum (axis Y) at the top centre
    My = axis_y((0, 0, ZT))
    drum = [(-0.525, 0.0, "copper"), (-0.512, 0.13, "copper"), (-0.475, 0.245, "copper"), (-0.415, 0.327, "copper"),
            (-0.37, 0.356, "brass"), (-0.37, 0.39, "brass"), (-0.29, 0.39, "brass"), (-0.29, 0.372, "copper"),
            (0.29, 0.372, "brass"), (0.29, 0.39, "brass"), (0.37, 0.39, "brass"), (0.37, 0.356, "copper"),
            (0.415, 0.327, "copper"), (0.475, 0.245, "copper"), (0.512, 0.13, "copper"), (0.525, 0.0, "copper")]
    revolve(p, [(y, r) for y, r, _ in drum], seg=24, M=My, mats=[m for _, _, m in drum[:-1]], phase=math.pi / 24)
    for yb in (-0.33, 0.33):
        for k in range(10):
            a = TAU * (k + 0.5) / 10
            d = Vector((math.cos(a), 0, math.sin(a)))
            rivet(p, "brass_dark", place(Vector((0, yb, ZT)) + d * 0.39, n=d), r=0.018)
    # valve on the front dome (-Y): gland, stem, red hand wheel
    revolve(p, [(0.5, 0.05), (0.56, 0.05), (0.565, 0.035), (0.6, 0.03)], seg=6, M=axis_my((0, 0, ZT)),
            mats="brass_dark", cap_bottom=False)
    revolve(p, [(0.6, 0.014), (0.66, 0.014)], seg=8, M=axis_my((0, 0, ZT)), mats="brass_dark", cap_bottom=False,
            cap_top=False)
    _handwheel(p, (0, -0.65, ZT), (0, -1, 0), R=0.21, r=0.02, spokes=5)
    # steam whistle on top with pull lever
    zb = ZT + 0.36
    revolve(p, [(zb - 0.02, 0.07), (zb + 0.03, 0.07), (zb + 0.036, 0.05), (zb + 0.08, 0.038), (zb + 0.086, 0.052),
                (zb + 0.1, 0.064), (zb + 0.11, 0.078), (zb + 0.13, 0.078), (zb + 0.132, 0.06), (zb + 0.152, 0.06),
                (zb + 0.156, 0.078), (zb + 0.3, 0.078), (zb + 0.32, 0.07), (zb + 0.34, 0.05), (zb + 0.352, 0.0)],
            seg=12, mats=["brass_dark"] * 6 + ["brass", "stm_soot", "stm_soot", "stm_soot"] + ["brass"] * 4,
            M=T(0, 0, 0), cap_bottom=False)
    tube(p, "brass_dark", [(0.04, 0, zb + 0.06), (0.14, 0, zb + 0.07), (0.27, 0, zb + 0.04)], 0.012, seg=6)
    ball(p, "brass", 0.026, seg=8, rings=5, M=T(0.28, 0, zb + 0.038))

    p.build(root)

    def tint(pw, nw):
        g = smoothstep(0.0, 1.2, pw.z)
        k = 0.78 + 0.22 * g
        return (k, k * 1.02, k)

    return _finish(root, ao=dict(distance=0.6, samples=48, strength=0.85, tint=tint))


# ---------------------------------------------------------------------------
# prop_vent — round cast-iron steam vent: moulded frame with brass inlay ring and bolts, chamfered
#             grate slats on cross bars, gear medallion, glowing aether pit, limescale stains,
#             copper riser with valve + hand wheel feeding the frame
# ---------------------------------------------------------------------------

VENT_FRAME = [  # (z, r, span material)
    (0.0, 0.7, "iron"), (0.02, 0.7, "iron"), (0.03, 0.684, "iron"), (0.036, 0.668, "iron"),
    (0.108, 0.628, "iron"), (0.124, 0.618, "iron"), (0.132, 0.6, "iron"), (0.132, 0.545, "brass"),
    (0.14, 0.537, "brass"), (0.143, 0.525, "brass"), (0.143, 0.5, "brass"), (0.14, 0.49, "brass"),
    (0.132, 0.482, "iron"), (0.132, 0.472, "iron"), (0.12, 0.46, "gunmetal"), (0.095, 0.46, "gunmetal"),
    (0.095, 0.44, "gunmetal"), (0.02, 0.44, "gunmetal"), (0.02, 0.0, "gunmetal"),
]


def build_vent():
    nm = "prop_vent"
    root = empty(nm, size=0.5)
    p = Part(nm + "_body")
    revolve(p, [(z, r) for z, r, _ in VENT_FRAME], seg=48, mats=[m for _, _, m in VENT_FRAME[:-1]],
            cap_bottom=False)
    for k in range(8):
        a = TAU * (k + 0.5) / 8
        hex_bolt(p, "brass", place((0.572 * math.cos(a), 0.572 * math.sin(a), 0.132), spin=a), r=0.021, h=0.02,
                 chamfer=False)

    # grate: chamfered slats resting on two cross bars, gear medallion in the middle
    for i in range(-4, 5):
        x = i * 0.09
        L = 2 * math.sqrt(0.452 ** 2 - x ** 2)
        prism(p, "gunmetal", rrect(0.032, 0.05, 0.008, 1), L, M=T(x, 0, 0.103) @ Rot("X", 90))
    for y in (-0.2, 0.2):
        L = 2 * math.sqrt(0.445 ** 2 - y ** 2)
        prism(p, "gunmetal", rrect(0.03, 0.04, 0.006, 1), L, M=T(0, y, 0.06) @ Rot("Y", 90))
    out, angs = gear_outline(0.1, 0.125, 8, base=0.56, top=0.34, phase=math.pi / 8, gap_mid=False)
    out = [q for i, q in enumerate(out) if i % 6 in (0, 2, 3, 5)]
    prism(p, "brass", out, 0.016, ch=0.0, back_ch=0.004, M=T(0, 0, 0.136))
    revolve(p, [(0.144, 0.05), (0.152, 0.048), (0.156, 0.036), (0.158, 0.0)], seg=12, mats="brass",
            cap_bottom=False)

    # cast buttress ribs on the outer wall (between the bolts)
    slope = math.atan2(0.108 - 0.036, 0.668 - 0.628)          # wall angle from horizontal
    for k in range(8):
        if k == 0:
            continue                                          # the riser branch enters here
        M = (Rot("Z", 45 * k) @ T(0.648 + 0.006 * math.sin(slope), 0, 0.072 + 0.006 * math.cos(slope))
             @ Matrix.Rotation(slope, 4, "Y"))
        prism(p, "iron", rrect(0.1, 0.036, 0.01, 1), 0.026, ch=0.0, back_ch=0.007, M=M)

    # copper riser from the ground with valve + hand wheel, branch feeding the frame
    rx, ry = 0.84, 0.36
    ra = math.atan2(ry, rx)
    revolve(p, [(0.0, 0.068), (0.022, 0.068), (0.026, 0.06)], seg=12, M=T(rx, ry, 0), mats="brass",
            cap_bottom=False, cap_top=False)
    tube(p, "copper", [(rx, ry, 0.0), (rx, ry, 0.08), (rx, ry, 0.165)], 0.042, seg=12, cap_start=False,
         cap_end=False)
    d = Vector((-math.cos(ra), -math.sin(ra), 0))
    b0 = Vector((rx, ry, 0.075))
    tube(p, "copper", [b0, b0 + d * 0.12, b0 + d * 0.33], 0.034, seg=12, cap_start=False, cap_end=False)
    fl = b0 + d * 0.27
    revolve(p, [(-0.012, 0.03), (-0.012, 0.052), (0.012, 0.052), (0.012, 0.03)], seg=12, M=place(fl, n=d),
            mats="brass", closed=True)
    revolve(p, [(-0.018, 0.04), (-0.018, 0.054), (0.018, 0.054), (0.018, 0.04)], seg=12, M=place(b0, n=(0, 0, 1)),
            mats="brass", closed=True)
    revolve(p, [(0.16, 0.046), (0.175, 0.06), (0.2, 0.064), (0.222, 0.056), (0.232, 0.04)], seg=12,
            M=T(rx, ry, 0), mats="brass", cap_bottom=False, cap_top=False)
    revolve(p, [(0.228, 0.036), (0.25, 0.036), (0.256, 0.026), (0.262, 0.02)], seg=6, M=T(rx, ry, 0),
            mats="brass", cap_bottom=False)
    revolve(p, [(0.26, 0.01), (0.285, 0.01)], seg=6, M=T(rx, ry, 0), mats="brass", cap_bottom=False,
            cap_top=False)
    _handwheel(p, (rx, ry, 0.278), (0, 0, 1), R=0.1, r=0.012, spokes=4, seg=16, hub_mat="brass")
    # small pressure gauge on the branch, facing the viewer side
    gp = b0 + d * 0.19
    revolve(p, [(0.0, 0.014), (0.07, 0.014)], seg=6, M=T(gp.x, gp.y, 0.075), mats="brass",
            cap_bottom=False, cap_top=False)
    _gauge(p, (gp.x, gp.y, 0.075 + 0.11), (0.55, -0.55, 0.62), r=0.055, needle=-20, seg=14, ink="gunmetal",
           cap_mat="brass")

    body = p.build(root)
    # steam-stained inlay ring: irregular verdigris patches
    def stained(c, n):
        r = math.hypot(c.x, c.y)
        if c.z < 0.12 or r > 0.56:
            return False
        v = fbm(Vector((c.x * 6.0, c.y * 6.0, 0.3)), 12)
        return v > -0.12 if r < 0.5 else v > 0.2         # creeping in from the opening's edge
    paint_faces(body, "brass", "patina", stained)

    g = Part(nm + "_glow")
    revolve(g, [(0.021, 0.36), (0.034, 0.25), (0.046, 0.0)], seg=24, mats="glow_cyan", cap_bottom=False)
    g.build(root)

    def tint(pw, nw):
        r = math.hypot(pw.x, pw.y)
        c = [1.0, 1.0, 1.0]
        if pw.z > 0.09 and r < 0.6:           # steam tarnish on the inlay ring / soot round the opening
            t = 1.0 - smoothstep(0.5, 0.58, r) * 0.6
            n = 0.5 + 0.5 * fbm(pw * 9.0, 4)
            c = [1.0 - 0.32 * t * n, 1.0 - 0.12 * t * n, 1.0 - 0.18 * t * n]
        dirt = 1.0 - 0.2 * (1.0 - smoothstep(0.0, 0.06, pw.z))
        return (c[0] * dirt, c[1] * dirt * 0.97, c[2] * dirt * 0.92)

    return _finish(root, ao=dict(distance=0.22, samples=48, strength=0.85, tint=tint), floor={"white": 0.85})


# ---------------------------------------------------------------------------
# prop_fence — wrought-iron fence segment: stone curb + footings, capped posts with brass ball finials,
#              flat-bar rails, bars with brass spear finials, ring frieze, gear medallion with
#              C-scrolls. Symmetric in Y, so it reads the same from both sides.
# ---------------------------------------------------------------------------

def _spear(p, x, z0, h=0.1, w=0.036):
    """Flattened brass spearhead (leaf shape seen from the front/back)."""
    k = h / 0.1
    revolve(p, [(0.0, 0.018), (0.016 * k, 0.018), (0.022 * k, 0.012), (0.048 * k, w), (0.066 * k, w * 0.82),
                (0.1 * k, 0.0)], seg=8, M=T(x, 0, z0) @ S(1, 0.42, 1), mats="brass", cap_bottom=False)


def build_fence():
    nm = "prop_fence"
    root = empty(nm, size=0.5)
    p = Part(nm + "_body")
    PX = 0.92                       # post centres

    # -- stone curb + post footings
    prism(p, "stone_dark", rrect(0.13, 0.15, 0.02, 1), 2 * PX - 0.2, ch=0.0, M=T(0, 0, 0.065) @ Rot("Y", 90),
          jitter=0.006, seed=21)
    for sx in (-1, 1):
        x = sx * PX
        prism(p, "stone_dark", rrect(0.25, 0.25, 0.035, 2), 0.14, ch=0.0, back_ch=0.025, M=T(x, 0, 0.07),
              jitter=0.008, seed=23 + sx)
        # post: square bar, brass collars, cap plate, pyramid, ball finial
        prism(p, "iron", rrect(0.09, 0.09, 0.012, 1), 0.98, ch=0.0, back_ch=0.0, M=T(x, 0, 0.14 + 0.49))
        for k in range(4):     # raised cast panels on the four faces
            n = Vector((math.cos(math.radians(90 * k)), math.sin(math.radians(90 * k)), 0))
            prism(p, "iron", rrect(0.05, 0.56, 0.012, 1), 0.014, M=place((x + n.x * 0.045, n.y * 0.045, 0.585), n=n))
        for zc in (0.22, 0.95):
            prism(p, "brass", rrect(0.112, 0.112, 0.016, 1), 0.035, ch=0.006, M=T(x, 0, zc))
        prism(p, "iron", rrect(0.135, 0.135, 0.018, 1), 0.03, ch=0.007, M=T(x, 0, 1.135))
        revolve(p, [(1.15, 0.088), (1.158, 0.088), (1.2, 0.03)], seg=4, M=T(x, 0, 0), mats="iron",
                phase=math.pi / 4, cap_bottom=False, cap_top=False)
        revolve(p, [(1.195, 0.03), (1.205, 0.022), (1.215, 0.03), (1.232, 0.043), (1.252, 0.046), (1.272, 0.038),
                    (1.288, 0.02), (1.296, 0.008), (1.33, 0.0)], seg=12, M=T(x, 0, 0), mats="brass")

    # -- flat-bar rails between the posts
    for z in (0.2, 0.86, 0.98):
        prism(p, "iron", rrect(0.034, 0.026, 0.004, 1), 2 * PX - 0.04, M=T(0, 0, z) @ Rot("Y", 90))

    # -- bars with spear finials (alternating heights)
    for k in range(-4, 5):
        x = k * 0.175
        top = 1.07 if k % 2 == 0 else 1.02
        revolve(p, [(0.12, 0.0125), (top + 0.005, 0.0125)], seg=8, M=T(x, 0, 0), mats="iron", cap_bottom=False,
                cap_top=False)
        _spear(p, x, top, h=0.1 if k % 2 == 0 else 0.085)

    # -- ring frieze between the two upper rails
    for k in range(8):
        x = -0.6125 + k * 0.175
        revolve(p, [(-0.006, 0.033), (-0.006, 0.046), (0.006, 0.046), (0.006, 0.033)], seg=12,
                M=axis_y((x, 0, 0.92)), mats="iron", closed=True)

    # -- centre gear medallion with C-scrolls in the neighbouring bays
    small_gear(p, 0.122, 0.15, 10, 0.026, 0.092, axis_my((0, 0, 0.56)), math.radians(90), 5, 0.034, 0.05)
    sec = rrect(0.02, 0.009)
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx = sx * 0.2625
            # C-scroll: leaves the outer bar, sweeps round and curls into the bay centre
            pts = spiral((cx, 0, 0.56 + sz * 0.07), 0.075, 0.015, 0 if sx > 0 else 180,
                         (0 if sx > 0 else 180) + sz * sx * 330, 18)
            sweep(p, "iron", pts, sec, up=(0, 1, 0))

    p.build(root)

    def tint(pw, nw):
        k = 0.8 + 0.2 * smoothstep(0.05, 0.5, pw.z)
        return (k, k, k * 0.97)

    return _finish(root, ao=dict(distance=0.3, samples=48, strength=0.85, tint=tint))


# ---------------------------------------------------------------------------
# prop_gear_monument — giant brass gear (chamfered teeth, I-beam spokes, bolted hub with an aether
#                      inlay ring, riveted rim, verdigris), half-buried in a mossy earth mound on a
#                      cracked two-tier stone plinth, a smaller fallen gear, rubble and a brass plaque
# ---------------------------------------------------------------------------

GEAR_Z = 2.12


def _stone_block(p, mat, cx, cy, z0, w, d, h, seed, tilt=(0.0, 0.0), rot=0.0, ch=0.06, jitter=0.022):
    M = T(cx, cy, z0 + h / 2) @ Rot("Z", rot) @ Rot("X", tilt[0]) @ Rot("Y", tilt[1])
    prism(p, mat, rrect(w, d, ch * 1.2, 2), h, ch=0.012, back_ch=ch, M=M, jitter=jitter, seed=seed,
          jitter_freq=1.6)


def _crack(p, pts, y, w=0.03, mat="stm_moss_dark"):
    """Jagged crack decal on a face at world y (facing -Y): pts = [(x, z)], widest in the middle."""
    n = len(pts)
    vs, fs = [], []
    for i, (x, z) in enumerate(pts):
        a = Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])
        nrm = Vector((-a.y, a.x)).normalized()
        hw = w * 0.5 * math.sin(math.pi * (i + 0.5) / n) + 0.002
        vs += [(x + nrm.x * hw, y, z + nrm.y * hw), (x - nrm.x * hw, y, z - nrm.y * hw)]
    for i in range(n - 1):
        fs.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    p.poly(mat, vs, fs)


def build_gear_monument():
    nm = "prop_gear_monument"
    root = empty(nm, size=0.5)
    GZ = GEAR_Z
    TH = 0.5                                  # gear thickness (Y)
    Mg = axis_my((0, 0, GZ))                  # gear plane: local x -> X, local y -> Z, local z -> -Y
    g = Part(nm + "_gear")

    # -- toothed rim: chamfered teeth, extra face loop (verdigris tint resolution)
    out, angs = gear_outline(2.52, 2.88, 20, base=0.56, top=0.34, phase=math.radians(90), bulge=0.38)
    ring_prism(g, "brass", out, at_angles(angs, 2.02), TH, ch=0.045, ch_in=0.035, M=Mg,
               mid=at_angles(angs, 2.4))
    # raised verdigris bead + rivet ring on both faces
    for side in (-1, 1):
        y0 = side * TH / 2
        prof = [(0.0, 2.06), (0.032, 2.08), (0.032, 2.15), (0.0, 2.17)]
        revolve(g, [(y0 + side * z, r) for z, r in prof], seg=64, M=axis_y((0, 0, GZ)), mats="patina",
                cap_bottom=False, cap_top=False)
        for k in range(20):
            a = TAU * (k + 0.5) / 20 + math.radians(90)
            rivet(g, "brass_dark", place((2.3 * math.cos(a), y0, GZ + 2.3 * math.sin(a)), n=(0, side, 0)),
                  r=0.045, seg=6)

    # -- six I-beam spokes with flared ends
    web = [(0.55, -0.3), (0.72, -0.21), (0.95, -0.165), (1.5, -0.15), (1.85, -0.17), (2.0, -0.23), (2.08, -0.32),
           (2.08, 0.32), (2.0, 0.23), (1.85, 0.17), (1.5, 0.15), (0.95, 0.165), (0.72, 0.21), (0.55, 0.3)]
    for k in range(6):
        Ms = Mg @ Matrix.Rotation(math.radians(90 + 60 * k), 4, "Z")
        prism(g, "brass", web, 0.26, ch=0.03, M=Ms)
        prism(g, "brass", rrect(1.45, 0.1, 0.02, 1, cx=1.36), 0.4, ch=0.025, M=Ms)

    # -- hub: chamfered boss, raised ring with glowing aether inlay, bolts, hex axle nuts, domed ends
    half = [(0.0, 0.8, "brass"), (0.29, 0.8, "brass"), (0.32, 0.77, "brass"), (0.32, 0.56, "brass"),
            (0.35, 0.545, "brass"), (0.36, 0.53, "brass"), (0.36, 0.5, "glow_cyan"), (0.36, 0.44, "brass"),
            (0.36, 0.4, "brass"), (0.34, 0.38, "brass"), (0.34, 0.3, "brass")]
    pts = [(-y, r) for y, r, _ in half[::-1]] + [(y, r) for y, r, _ in half[1:]]
    mats = [half[len(half) - 2 - i][2] for i in range(len(half) - 1)] + [m for _, _, m in half[:-1]]
    revolve(g, pts, seg=40, M=axis_y((0, 0, GZ)), mats=mats)
    for side in (-1, 1):
        My = axis_y((0, 0, GZ)) if side > 0 else axis_my((0, 0, GZ))
        revolve(g, [(0.335, 0.27), (0.43, 0.27), (0.46, 0.215), (0.46, 0.0)], seg=6, M=My, mats="brass_dark",
                phase=math.pi / 6, cap_bottom=False)
        revolve(g, [(0.455, 0.135), (0.475, 0.13), (0.5, 0.108), (0.518, 0.07), (0.526, 0.0)], seg=12, M=My,
                mats="brass", cap_bottom=False)
        for k in range(8):
            a = TAU * (k + 0.5) / 8
            hex_bolt(g, "brass_dark" if k % 3 else "patina",
                     place((0.665 * math.cos(a), side * 0.32, GZ + 0.665 * math.sin(a)), n=(0, side, 0), spin=a),
                     r=0.045, h=0.04, washer=1.3)
    gear_obj = g.build(root)
    # faces entirely below the upper plinth tier are buried in stone/ground -> drop them
    cull_faces(gear_obj, lambda c, vs: max(v.z for v in vs) > 0.36)
    # verdigris on the lower rim rivets (damp side near the mound)
    paint_faces(gear_obj, "brass_dark", "patina",
                lambda c, n: (c - Vector((0, c.y, GZ))).length > 2.2 and c.z < 2.8
                and fbm(c * 1.7, 21) > -0.05)

    # -- a smaller, older gear that fell over and sank into the mound behind the big one
    f = Part(nm + "_fallen")
    Mf = place((-1.55, 0.72, 0.98), n=(-0.38, 0.52, 0.77), spin=0.4)
    gear(f, "brass_dark", 0.9, 1.08, 12, 0.2, 0.68, ch=0.03, ch_in=0.025, M=Mf, phase=0.2, spokes=4,
         spoke_w=0.16, hub_r=0.22, hub_len=0.3, hub_mat="brass_dark", spoke_mat="brass_dark")
    f.build(root)

    # ------------------------------------------------------------------ plinth
    s = Part(nm + "_base")
    # tier 1: 3 x 2 big blocks (one settled + chipped), tier 2: 3 blocks, the right one cracked in two
    t1 = [(-2.05, -0.75, 2.0, 1.46, 0.4, 61), (0.0, -0.75, 2.0, 1.46, 0.42, 62), (2.05, -0.75, 2.0, 1.46, 0.38, 63),
          (-2.05, 0.75, 2.0, 1.46, 0.41, 64), (0.0, 0.75, 2.0, 1.46, 0.39, 65), (2.05, 0.75, 2.0, 1.46, 0.4, 66)]
    for i, (cx, cy, w, d, h, sd) in enumerate(t1):
        if i == 0:   # settled, slightly tilted corner block + a broken-off chunk lying in front of it
            _stone_block(s, "stone", cx, cy, -0.03, w, d, h, sd, tilt=(-2.0, 1.5), rot=1.5)
            rubble(s, "stone", (cx - 0.5, cy - 0.98, 0.12), (0.46, 0.36, 0.26), seed=sd + 1, tilt=(8, -14),
                   rot=0.4, ch=0.04)
        else:
            _stone_block(s, "stone", cx, cy, 0.0, w, d, h, sd)
    _stone_block(s, "stone_dark", -1.82, 0.0, 0.4, 1.78, 1.96, 0.44, 73)
    _stone_block(s, "stone_dark", 0.0, 0.0, 0.4, 1.8, 1.96, 0.44, 74)
    # cracked block: two pieces with a gap, the outer one sagging and twisted
    _stone_block(s, "stone_dark", 1.33, 0.0, 0.4, 0.8, 1.96, 0.44, 71)
    _stone_block(s, "stone_dark", 2.26, -0.03, 0.36, 0.92, 1.94, 0.44, 72, tilt=(0, 4.0), rot=3.0)
    # crack decals on the front faces
    _crack(s, [(-0.45, 0.4), (-0.38, 0.33), (-0.41, 0.25), (-0.3, 0.17), (-0.33, 0.08), (-0.24, 0.0)], -1.487)
    _crack(s, [(-1.3, 0.84), (-1.22, 0.76), (-1.25, 0.69), (-1.13, 0.6), (-1.16, 0.53)], -0.985, w=0.026)
    _crack(s, [(2.6, 0.38), (2.66, 0.3), (2.62, 0.22), (2.72, 0.14)], -1.487, w=0.024)
    # rubble around the base
    for i, (x, y, w, z, t) in enumerate(((2.95, -1.75, 0.36, 0.1, 10), (3.35, 0.45, 0.3, 0.08, -6),
                                         (-3.3, -0.3, 0.32, 0.09, 12), (1.2, -1.8, 0.26, 0.07, 5),
                                         (-1.0, 1.8, 0.3, 0.08, -9), (2.6, 1.7, 0.22, 0.06, 14),
                                         (-2.7, 1.62, 0.25, 0.07, 7), (0.75, -1.3, 0.18, 0.47, -12),
                                         (3.0, -0.2, 0.2, 0.45, 9))):
        rubble(s, "stone_dark" if i % 2 else "stone", (x, y, z), (w, w * 0.8, w * 0.62), seed=90 + i,
               tilt=(t, -t * 0.6), rot=i * 0.9, ch=0.03)
    # brass plaque on the front of tier 2
    Mp = place((0.0, -0.985, 0.62), n=(0, -1, 0))
    prism(s, "brass_dark", rrect(1.1, 0.32, 0.05, 2), 0.03, ch=0.0, back_ch=0.008, M=Mp)
    prism(s, "brass", rrect(0.98, 0.22, 0.035, 2), 0.036, ch=0.0, back_ch=0.006, M=Mp @ T(0, 0, 0.004))
    for k, (w, yy) in enumerate(((0.62, 0.05), (0.74, 0.0), (0.46, -0.05))):
        prism(s, "brass_dark", rrect(w, 0.018), 0.006, M=Mp @ T(0, yy, 0.024))
    for sx in (-1, 1):
        for sy in (-1, 1):
            rivet(s, "brass_dark", Mp @ T(sx * 0.505, sy * 0.115, 0.015), r=0.022, seg=6)
    s.build(root)

    # ------------------------------------------------------------------ moss & earth
    m = Part(nm + "_moss")
    # earth heaped up against the gear: a long ridge + two side heaps, moss on top, darker flanks
    lumpy_blob(m, "stm_moss_dark", (0.0, 0.0, 0.78), (2.6, 0.95, 0.72), seg=36, rings=14, amp=0.22, freq=1.5,
               seed=5, floor=0.78, top_mat="moss", top_thresh=0.45)
    lumpy_blob(m, "stm_moss_dark", (-1.25, -0.38, 0.8), (1.05, 0.62, 0.46), seg=16, rings=8, amp=0.3, freq=2.0,
               seed=6, floor=0.78, top_mat="moss", top_thresh=0.45)
    lumpy_blob(m, "stm_moss_dark", (1.45, 0.4, 0.8), (0.95, 0.58, 0.42), seg=16, rings=8, amp=0.3, freq=2.0,
               seed=7, floor=0.78, top_mat="moss", top_thresh=0.45)
    for i, (x, y, rx, ry, z) in enumerate(((-2.6, -1.05, 0.38, 0.28, 0.39), (2.5, 1.08, 0.42, 0.3, 0.4),
                                            (0.9, -1.2, 0.32, 0.2, 0.42), (-1.2, 1.18, 0.35, 0.22, 0.41),
                                            (-2.75, 0.45, 0.25, 0.3, 0.41))):
        moss_pad(m, "moss" if i % 2 else "stm_moss_dark", (x, y, z), rx, ry, h=0.05, seg=12, rings=3, seed=30 + i,
                 droop=0.02, rot=i * 0.7)
    # moss clumps climbing the rim, the spokes and the fallen gear
    for i, (x, z, rx, rz) in enumerate(((-2.3, 1.17, 0.42, 0.26), (2.33, 1.15, 0.44, 0.28),
                                        (-2.62, 1.36, 0.2, 0.17), (2.66, 1.33, 0.2, 0.16))):
        lumpy_blob(m, "moss", (x, 0.0, z), (rx, 0.33, rz), seg=14, rings=7, amp=0.2, freq=2.4, seed=50 + i)
    m.build(root)

    def tint(pw, nw):
        # verdigris blotches on the metal, darker/greener towards the mound, damp mossy stone tops
        st = fbm(Vector((pw.x * 1.4, pw.y * 1.4, pw.z * 0.45)), 8)
        streak = smoothstep(-0.12, 0.28, st) * (0.4 + 0.6 * smoothstep(3.8, 1.2, pw.z))
        low = 1.0 - 0.22 * smoothstep(1.5, 0.5, pw.z)
        r, gg, b = 1.0 - 0.42 * streak, 1.0 - 0.08 * streak, 1.0 - 0.06 * streak
        if pw.z < 0.9 and nw.z > 0.6:
            r, gg, b = r * 0.84, gg * 0.93, b * 0.8
        return (r * low, gg * low, b * low)

    return _finish(root, ao=dict(distance=1.0, samples=48, strength=0.9, tint=tint))


# name, builder, preview kwargs (passed to hp.render_hp)
PROPS = [
    ("prop_lamp", build_lamp, {}),
    ("prop_pipe", build_pipe, {}),
    ("prop_pipe_arch", build_pipe_arch, {}),
    ("prop_vent", build_vent, dict(elevation=40)),
    ("prop_fence", build_fence, {}),
    ("prop_gear_monument", build_gear_monument, {}),
]

# triangle budget per prop (user-chosen "medium" tier, 2026-10-11)
BUDGET = {
    "prop_lamp": 6000,
    "prop_pipe": 6000,
    "prop_pipe_arch": 8000,
    "prop_vent": 4000,
    "prop_fence": 4000,
    "prop_gear_monument": 15000,
}
