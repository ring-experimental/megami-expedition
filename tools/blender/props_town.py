"""Chapter-1 props (hi-poly): town house, locomotive 'Kanna', nail board, organ spirit 'Pippe',
factory chimney, tower drive shaft. Assembled into props2.glb by model_props2.py.

Conventions (ASSET_SPEC.md): each builder returns a top-level empty named exactly like the prop, origin
at the base centre on the ground (z = 0), FRONT = -Y in Blender (= +Z in three.js). Group materials use
the prefix `twn_` (emissive: `glow_twn_*`). Geometry helpers come from hp_small_helpers (Kit etc.).

Named child nodes (all with identity rest rotation):
    prop_house       sign (mesh, pivot at the bracket crossbar; sways around X), door_point (empty, in
                     front of the door on the ground)
    prop_locomotive  steam_point (empty, smokestack top)
    prop_organ       jaw (mesh, keyboard cover, pivot at its lower front hinge; +rot X opens it forward/
                     down), pipe_01..pipe_12 (mesh, pivot at each pipe foot), steam_point (tallest pipe top)
    prop_nail_board  notice_1..notice_4 (mesh, the paper notices)
    prop_chimney     steam_point (empty, top centre)
    prop_drive_shaft rotor (mesh: shaft + gears + collars; rotates around local Z = three.js Y)

Test alone:  blender -b --factory-startup -P tools/blender/model_props2.py -- --previews --no-export [--only=prop_x]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import set_mat  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import numpy as np  # noqa: E402
import hp_helpers as hp  # noqa: E402
import hp_small_helpers as sh  # noqa: E402
from hp_small_helpers import I4, T, R, S, Kit, box, revolve, prism, ring_prism, plate, slab, ring_plate, \
    param_box, tube, rivet, circle2d, fillet_poly  # noqa: E402
from hp_steam_helpers import fbm, paint_faces, smoothstep  # noqa: E402


def setup_mats():
    """Group-specific materials (prefix twn_ / glow_twn_)."""
    # house
    get_mat("twn_brick", hex="#8e4f37", roughness=0.9)
    get_mat("twn_wood", hex="#5a3f2a", roughness=0.8)
    get_mat("twn_slate", hex="#3f4450", metallic=0.15, roughness=0.6)
    get_mat("twn_plaster", hex="#d8c7a4", roughness=0.95)
    get_mat("twn_stone", hex="#9a9184", roughness=0.92)
    get_mat("twn_pane", hex="#283544", metallic=0.4, roughness=0.12)
    get_mat("twn_sign", hex="#2f5a52", roughness=0.7)
    get_mat("glow_twn_window", hex="#ffc46b", emission="#ffb04a", strength=4.0)
    # locomotive
    get_mat("twn_loco", hex="#2a2622", metallic=0.55, roughness=0.42)
    get_mat("twn_loco_red", hex="#9a2a22", metallic=0.3, roughness=0.5)
    get_mat("twn_rust", hex="#7b4020", metallic=0.2, roughness=0.85)
    get_mat("twn_coal", hex="#151414", metallic=0.05, roughness=0.8)
    get_mat("twn_sleeper", hex="#4a3a2c", roughness=0.9)
    get_mat("glow_twn_lamp", hex="#fff0c8", emission="#ffe2a0", strength=5.0)
    # nail board
    get_mat("twn_board", hex="#6a4a30", roughness=0.85)
    get_mat("twn_nail", hex="#d4a83a", metallic=0.9, roughness=0.3)
    get_mat("twn_paper", hex="#efe6d2", roughness=0.9)
    get_mat("twn_ink", hex="#3a2e24", roughness=0.8)
    # organ
    get_mat("twn_walnut", hex="#5a3a24", roughness=0.55)
    get_mat("twn_pipe", hex="#b08d3c", metallic=0.85, roughness=0.42)
    get_mat("twn_ivory", hex="#e8dcc0", roughness=0.4)
    get_mat("twn_ebony", hex="#1d1714", roughness=0.4)
    get_mat("twn_felt", hex="#7c1d2b", roughness=0.95)
    # chimney / drive shaft
    get_mat("twn_soot_brick", hex="#5a3a2e", roughness=0.92)
    get_mat("twn_iron", hex="#3d3a36", metallic=0.7, roughness=0.6)
    get_mat("twn_black_iron", hex="#2b2a28", metallic=0.75, roughness=0.5)
    get_mat("glow_twn_violet", hex="#a98bff", emission="#a98bff", strength=6.0)


# ---------------------------------------------------------------------------
# shared bits
# ---------------------------------------------------------------------------

def F_front(y):
    """Face frame on a wall facing -Y: local (a, b, c) = (x, z, outward distance)."""
    return T(0, y, 0) @ R("X", 90)


def F_back(y):
    return T(0, y, 0) @ R("Z", 180) @ R("X", 90)


def F_right(x):
    return T(x, 0, 0) @ R("Z", 90) @ R("X", 90)


def F_left(x):
    return T(x, 0, 0) @ R("Z", -90) @ R("X", 90)


def rect(cx, cy, w, h):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def beam(part, mat, F, a0, b0, a1, b1, w, d, c0=0.0, divs=(1, 1, 1)):
    """Straight timber in a face frame from (a0, b0) to (a1, b1), width w, standing d proud of c0."""
    da, db = a1 - a0, b1 - b0
    L = math.hypot(da, db)
    ang = math.degrees(math.atan2(db, da))
    M = F @ T((a0 + a1) / 2, (b0 + b1) / 2, c0 + d / 2) @ R("Z", ang)
    return sh.grid_box(part, mat, (L, w, d), divs=divs, M=M)


def _h(*k):
    return random.Random(hash(k) & 0xFFFFFFFF).random()


def face_tint(obj, mats, fn):
    """Multiply the baked 'Col' per FACE (corner domain) by fn(centre, normal) -> (r, g, b) for faces with a
    material in `mats` (brick / tile patterns without extra geometry)."""
    me = obj.data
    if hp.AO_ATTR not in me.color_attributes:
        return
    names = [m.name if m else "" for m in me.materials]
    ok = {i for i, n in enumerate(names) if n in mats}
    attr = me.color_attributes[hp.AO_ATTR]
    nl = len(me.loops)
    cols = np.empty(nl * 4, dtype=np.float32)
    attr.data.foreach_get("color", cols)
    cols = cols.reshape(nl, 4)
    for p in me.polygons:
        if p.material_index not in ok:
            continue
        r, g, b = fn(p.center, p.normal)
        s = slice(p.loop_start, p.loop_start + p.loop_total)
        cols[s, 0] *= r
        cols[s, 1] *= g
        cols[s, 2] *= b
    np.clip(cols[:, :3], 0.0, 1.0, out=cols[:, :3])
    attr.data.foreach_set("color", cols.ravel())
    me.update()


def brick_fn(z0=0.0, ch=0.2, bw=0.5, lo=0.7, hi=1.04, seed=0):
    """Running-bond brick tint for flat walls built from bw/2 x ch face cells."""
    def fn(c, n):
        if abs(n.z) > 0.7:
            return (0.92, 0.92, 0.92)
        u = c.x if abs(n.y) >= abs(n.x) else c.y
        side = (0 if abs(n.y) >= abs(n.x) else 1) + (2 if (n.y > 0 or n.x > 0) else 0)
        course = math.floor((c.z - z0) / ch)
        b = math.floor((u + (course % 2) * bw / 2) / bw + 1e-4)
        t = _h(seed, side, course, b)
        k = lo + (hi - lo) * t
        if _h(seed + 7, side, course, b) < 0.07:
            k *= 0.72                                    # over-burnt brick
        warm = 1.0 + 0.06 * (_h(seed + 3, side, course, b) - 0.5)
        return (k * warm, k, k / warm)
    return fn


def finish_prop(root, kits_built, ao, tints=()):
    """AO over all parts of one prop, then join each kit; tints = [(kit_index, fn(obj))]."""
    sh.bake_parts(*[b for (_, b) in kits_built], **ao)
    objs = [k.join_parts(b) for (k, b) in kits_built]
    for i, fn in tints:
        fn(objs[i])
    return objs


# ===========================================================================
# prop_house
# ===========================================================================
HW, HD = 3.25, 2.5            # half width / depth of the brick ground floor
Z_PL, Z_G = 0.35, 3.15        # plinth top / ground-floor top (14 courses of 0.2 m)
Z_U0, Z_U1 = 3.4, 5.6         # upper floor
Y_J = -2.72                   # jettied upper front plane
Z_EAVE, Z_RIDGE, X_EAVE = 5.45, 7.6, 3.5
Y_R0, Y_R1 = -2.95, 2.75      # roof extent
SIGN_PIVOT = (2.75, -3.62, 3.93)
DOOR_X = -1.575


def _roof_frame(side):
    E = Vector((side * X_EAVE, 0, Z_EAVE))
    v = Vector((-side * X_EAVE, 0, Z_RIDGE - Z_EAVE))
    L = v.length
    d = v / L
    n = Vector((side * (Z_RIDGE - Z_EAVE), 0, X_EAVE)) / L
    return E, d, n, L


def _window(P, F, cx, cz, w, h, cols, rows, glow=(), fw=0.08, fd=0.07, sill=True, lintel=False, frame_mat="twn_wood"):
    outer = rect(cx, cz, w + 2 * fw, h + 2 * fw)
    inner = rect(cx, cz, w, h)
    ring_plate(P["wood"], frame_mat, outer, inner, 0.0, fd, bev=0.015, steps=1, M=F)
    pw, ph = w / cols, h / rows
    for i in range(cols):
        for j in range(rows):
            mat = "glow_twn_window" if (i, j) in glow else "twn_pane"
            box(P["pane"], mat, (pw, ph, 0.02), loc=(cx - w / 2 + pw * (i + 0.5), cz - h / 2 + ph * (j + 0.5), 0.005), M=F,
                skip=("-x", "+x", "-y", "+y", "-z"))
    for i in range(1, cols):
        box(P["wood"], frame_mat, (0.045, h, 0.04), loc=(cx - w / 2 + pw * i, cz, 0.035), M=F)
    for j in range(1, rows):
        box(P["wood"], frame_mat, (w, 0.045, 0.04), loc=(cx, cz - h / 2 + ph * j, 0.035), M=F)
    if sill:
        box(P["stone"], "twn_stone", (w + 2 * fw + 0.12, 0.08, 0.16), loc=(cx, cz - h / 2 - fw - 0.04, 0.08), M=F)
    if lintel:
        # soldier course of protruding bricks above the opening
        n = max(3, int(round((w + 2 * fw + 0.1) / 0.13)))
        bwid = (w + 2 * fw + 0.1) / n
        for k in range(n):
            box(P["brick"], "twn_brick", (bwid - 0.012, 0.26, 0.05),
                loc=(cx - (w + 2 * fw + 0.1) / 2 + bwid * (k + 0.5), cz + h / 2 + fw + 0.13, 0.025), M=F)


def _flower_box(P, F, cx, cz, w, rng):
    box(P["wood"], "twn_wood", (w, 0.2, 0.24), loc=(cx, cz, 0.13), M=F)
    for k in range(5):
        a = cx - w / 2 + w * (k + 0.5) / 5 + rng.uniform(-0.04, 0.04)
        loc = F @ Vector((a, cz + 0.13, 0.13 + rng.uniform(-0.03, 0.03)))
        sh.blob(P["leaf"], "leaf", 0.13, loc=tuple(loc), scale=(1.2, 1.0, 0.8), subdiv=1, amount=0.25, seed=rng.randrange(999))
    for k in range(6):
        a = cx - w / 2 + w * (k + 0.5) / 6 + rng.uniform(-0.05, 0.05)
        loc = F @ Vector((a, cz + 0.23 + rng.uniform(-0.03, 0.04), 0.2 + rng.uniform(-0.04, 0.05)))
        P["leaf"].ico("cloth_red", r=0.045, subdiv=1, loc=tuple(loc))


def build_house():
    root = empty("prop_house", size=1.0)
    rng = random.Random(21)
    kit = Kit("prop_house_body")
    P = {
        "brick": kit.part("brick", smooth=None),
        "stone": kit.part("stone", smooth=40),
        "stone_b": kit.part("stone_b", bevel=(0.025, 1, 40), smooth=40),
        "wood": kit.part("wood", smooth=40),
        "beam": kit.part("beam", bevel=(0.012, 1, 40), smooth=40),
        "plaster": kit.part("plaster", smooth=None),
        "slate": kit.part("slate", smooth=None),
        "metal": kit.part("metal", smooth=40),
        "pane": kit.part("pane", smooth=None, occluder=False, recalc=False),
        "pane_r": kit.part("pane_r", smooth=None, occluder=False),
        "leaf": kit.part("leaf", smooth=60, occluder=False),
    }
    # ---------- plinth ----------
    box(P["stone_b"], "twn_stone", (2 * HW + 0.16, 2 * HD + 0.16, Z_PL), loc=(0, 0, Z_PL / 2), divs=(4, 3, 1))
    # ---------- brick ground floor (0.25 x 0.2 face cells -> per-face brick pattern) ----------
    sh.grid_box(P["brick"], "twn_brick", (2 * HW, 2 * HD, Z_G - Z_PL), divs=(26, 20, 14),
                M=T(0, 0, (Z_PL + Z_G) / 2), skip=("-z", "+z", "+y"))
    # back wall: coarser cells (plain side of the house)
    sh.grid_box(kit.part("brick_back", smooth=None, recalc=False), "twn_brick", (2 * HW, 0.02, Z_G - Z_PL), divs=(13, 1, 7),
                M=T(0, HD - 0.01, (Z_PL + Z_G) / 2), skip=("-z", "+z", "-y", "-x", "+x"))
    # quoins on the four corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k in range(7):
                long_x = (k % 2 == 0)
                lx, ly = (0.55, 0.3) if long_x else (0.3, 0.55)
                z = Z_PL + 0.4 * k + 0.2
                box(P["stone"], "twn_stone", (lx + 0.04, ly + 0.04, 0.38),
                    loc=(sx * (HW - lx / 2 + 0.02), sy * (HD - ly / 2 + 0.02), z))
    # ---------- door (front, x = DOOR_X) ----------
    Ff = F_front(-HD)
    dw, dh = 1.15, 2.3
    dz0 = Z_PL
    ring_plate(P["wood"], "twn_wood", rect(DOOR_X, dz0 + dh / 2 + 0.06, dw + 0.24, dh + 0.12 + 0.24),
               rect(DOOR_X, dz0 + dh / 2 + 0.06, dw, dh + 0.12), 0.0, 0.1, bev=0.02, steps=1, M=Ff)
    for k in range(4):
        pwid = dw / 4
        a = DOOR_X - dw / 2 + pwid * (k + 0.5)
        box(P["wood"], "twn_wood", (pwid - 0.015, dh - 0.4, 0.05), loc=(a, dz0 + (dh - 0.4) / 2, 0.025), M=Ff)
    # transom above door (dark pane) + head rail + door cross rails
    _window(P, Ff, DOOR_X, dz0 + dh - 0.12, dw - 0.1, 0.26, 3, 1, fw=0.05, fd=0.05, sill=False)
    box(P["wood"], "twn_wood", (dw, 0.12, 0.06), loc=(DOOR_X, dz0 + dh - 0.4 + 0.05, 0.03), M=Ff)
    for zz in (0.45, 1.5):
        box(P["metal"], "brass", (dw * 0.62, 0.06, 0.02), loc=(DOOR_X - dw * 0.15, dz0 + zz, 0.06), M=Ff)
    knob = Ff @ Vector((DOOR_X + dw * 0.32, dz0 + 1.05, 0.06))
    P["metal"].sphere("brass", r=0.05, seg=10, rings=6, loc=tuple(knob))
    box(P["metal"], "brass", (0.08, 0.22, 0.015), loc=(DOOR_X + dw * 0.32, dz0 + 1.05, 0.055), M=Ff)
    # soldier-course lintel + door step
    _window_lintel = [(DOOR_X, dw + 0.24)]
    for (cx, w) in _window_lintel:
        n = 11
        bwid = (w + 0.12) / n
        for k in range(n):
            box(P["brick"], "twn_brick", (bwid - 0.012, 0.28, 0.06),
                loc=(cx - (w + 0.12) / 2 + bwid * (k + 0.5), dz0 + dh + 0.18 + 0.14, 0.03), M=Ff)
    box(P["stone_b"], "twn_stone", (dw + 0.6, 0.5, 0.18), loc=(DOOR_X, -HD - 0.3, 0.09))
    # ---------- shop window ----------
    # big lower panes + a row of 3 small warm-lit transom panes (the house's 3 glow_ panes)
    _window(P, Ff, 1.425, 1.62, 2.1, 1.15, 3, 1, fw=0.09, fd=0.09)
    _window(P, Ff, 1.425, 2.45, 2.1, 0.32, 3, 1, glow={(0, 0), (1, 0), (2, 0)}, fw=0.09, fd=0.09, sill=False,
            lintel=True)
    # side windows (ground floor)
    for F, a in ((F_right(HW), 0.6), (F_left(-HW), -0.6)):
        _window(P, F, a, 1.75, 0.9, 1.1, 2, 2, lintel=True)
    # ---------- jetty beam + joist ends ----------
    box(P["wood"], "twn_wood", (2 * HW + 0.1, 2 * HD + 0.08 + (-Y_J - HD), Z_U0 - Z_G),
        loc=(0, (Y_J - 0.05 + HD + 0.04) / 2, (Z_G + Z_U0) / 2), divs=(4, 1, 1))
    for k in range(12):
        x = -HW + 0.25 + k * (2 * HW - 0.5) / 11
        box(P["wood"], "twn_wood", (0.13, 0.32, 0.13), loc=(x, Y_J + 0.1, Z_G - 0.04))
    # ---------- upper floor: plaster + timber frame ----------
    box(P["plaster"], "twn_plaster", (2 * HW, HD - Y_J, Z_U1 - Z_U0), loc=(0, (Y_J + HD) / 2, (Z_U0 + Z_U1) / 2),
        divs=(6, 5, 3))
    Fu = F_front(Y_J)
    tw, td = 0.17, 0.07
    beam(P["beam"], "twn_wood", Fu, -HW - 0.02, Z_U0 + 0.09, HW + 0.02, Z_U0 + 0.09, 0.18, td + 0.02)
    beam(P["beam"], "twn_wood", Fu, -HW - 0.02, Z_U1 - 0.08, HW + 0.02, Z_U1 - 0.08, 0.16, td + 0.02)
    posts = [-HW + 0.085, -2.25, -0.85, 0.85, 2.25, HW - 0.085]
    for x in posts:
        beam(P["beam"], "twn_wood", Fu, x, Z_U0 + 0.18, x, Z_U1 - 0.16, tw, td)
    for s in (-1, 1):                              # K braces in the outer bays
        beam(P["beam"], "twn_wood", Fu, s * (HW - 0.17), Z_U0 + 0.2, s * 2.33, (Z_U0 + Z_U1) / 2, 0.14, td)
        beam(P["beam"], "twn_wood", Fu, s * 2.33, (Z_U0 + Z_U1) / 2, s * (HW - 0.17), Z_U1 - 0.17, 0.14, td)
    # St Andrew's cross in the middle bay
    beam(P["beam"], "twn_wood", Fu, -0.77, Z_U0 + 0.2, 0.77, Z_U1 - 0.17, 0.14, td)
    beam(P["beam"], "twn_wood", Fu, -0.77, Z_U1 - 0.17, 0.77, Z_U0 + 0.2, 0.14, td - 0.005)
    for cx in (-1.55, 1.55):
        _window(P, Fu, cx, 4.55, 0.9, 1.05, 2, 2, fw=0.07, fd=0.08)
        box(P["wood"], "twn_wood", (1.2, 0.08, 0.1), loc=(cx, 5.2, 0.06), M=Fu)
        _flower_box(P, Fu, cx, 3.82, 1.1, rng)
    # sides of the upper floor
    for F, s in ((F_right(HW), 1), (F_left(-HW), -1)):
        # side frame: a = +y on the right side, -y on the left
        a_front, a_back = (Y_J + 0.08) * s, (HD - 0.08) * s
        ps = sorted([a_front, -1.0, 1.0, a_back])
        beam(P["wood"], "twn_wood", F, ps[0] - 0.09, Z_U0 + 0.09, ps[-1] + 0.09, Z_U0 + 0.09, 0.18, td)
        beam(P["wood"], "twn_wood", F, ps[0] - 0.09, Z_U1 - 0.08, ps[-1] + 0.09, Z_U1 - 0.08, 0.16, td)
        for a in ps:
            beam(P["wood"], "twn_wood", F, a, Z_U0 + 0.18, a, Z_U1 - 0.16, tw, td)
        for (a0, a1) in ((ps[0], ps[1]), (ps[3], ps[2])):
            beam(P["wood"], "twn_wood", F, a0 + math.copysign(0.08, a1 - a0), Z_U0 + 0.2, a1 - math.copysign(0.08, a1 - a0),
                 Z_U1 - 0.17, 0.13, td)
        _window(P, F, 0.0, 4.5, 0.7, 0.9, 2, 2, fw=0.07, fd=0.08)
    # back of the upper floor
    Fb = F_back(HD)
    beam(P["wood"], "twn_wood", Fb, -HW, Z_U0 + 0.09, HW, Z_U0 + 0.09, 0.18, td)
    for x in (-HW + 0.085, -1.2, 1.2, HW - 0.085):
        beam(P["wood"], "twn_wood", Fb, x, Z_U0 + 0.18, x, Z_U1 - 0.1, tw, td)
    _window(P, Fb, 0.0, 4.5, 0.8, 1.0, 2, 2, fw=0.07, fd=0.08)
    _window(P, Fb, 1.6, 1.75, 0.9, 1.1, 2, 2, lintel=True)
    # ---------- gables (front detailed, back plain) ----------
    k = (Z_RIDGE - Z_EAVE) / X_EAVE
    top = Z_RIDGE - 0.12
    tri = [(-HW, Z_U1), (HW, Z_U1), (0.0, top)]
    prism(P["plaster"], "twn_plaster", tri, -0.12, 0.0, M=Fu)
    prism(P["plaster"], "twn_plaster", tri, -0.12, 0.0, M=Fb)
    zc = 6.45
    hw_c = (top - zc) / k
    beam(P["beam"], "twn_wood", Fu, -hw_c, zc, hw_c, zc, 0.16, td)
    beam(P["beam"], "twn_wood", Fu, 0, Z_U1, 0, zc - 0.08, tw, td)
    beam(P["beam"], "twn_wood", Fu, 0, 7.28, 0, top - 0.05, tw, td)
    for s in (-1, 1):
        beam(P["beam"], "twn_wood", Fu, s * 2.7, Z_U1 + 0.02, s * 1.1, zc - 0.07, 0.14, td)
        beam(P["beam"], "twn_wood", Fu, s * 1.2, Z_U1 + 0.02, s * 0.3, zc - 0.07, 0.12, td - 0.01)
        beam(P["beam"], "twn_wood", Fu, s * 1.05, zc + 0.07, s * 1.05, top - 1.05 * k - 0.05, 0.13, td)
    # round gable window
    cz = 6.92
    ring_plate(P["wood"], "twn_wood", circle2d(0.4, 20, cx=0, cy=cz), circle2d(0.3, 20, cx=0, cy=cz), 0.0, 0.09,
               bev=0.02, steps=1, M=Fu)
    prism(P["pane_r"], "twn_pane", circle2d(0.31, 20, cx=0, cy=cz), 0.0, 0.02, M=Fu)
    box(P["wood"], "twn_wood", (0.6, 0.04, 0.04), loc=(0, cz, 0.04), M=Fu)
    box(P["wood"], "twn_wood", (0.04, 0.6, 0.04), loc=(0, cz, 0.04), M=Fu)
    beam(P["wood"], "twn_wood", Fb, 0, Z_U1, 0, top - 0.05, tw, td)
    beam(P["wood"], "twn_wood", Fb, -hw_c, zc, hw_c, zc, 0.16, td)
    # ---------- roof ----------
    for side in (-1, 1):
        E, d, n, L = _roof_frame(side)

        def under(u, v, w, E=E, d=d, n=n, L=L):
            return E + d * (u * L) + n * (-0.1 + 0.1 * w) + Vector((0, Y_R0 + (Y_R1 - Y_R0) * v, 0))
        param_box(P["wood"], "twn_wood", under, divs=(3, 4, 1))
        step, rlen, lift, th = 0.34, 0.44, 0.055, 0.035
        nrow = int(math.ceil((L - 0.05) / step))
        for r in range(nrow):
            s0 = r * step
            s1 = min(s0 + rlen, L + 0.02)

            def tile(u, v, w, s0=s0, s1=s1, E=E, d=d, n=n):
                s = s0 + (s1 - s0) * u
                off = lift * (1 - u) * (1.0 if s0 > 0 else 0.6) + th * w
                return E + d * s + n * off + Vector((0, Y_R0 - 0.02 + (Y_R1 - Y_R0 + 0.04) * v, 0))
            param_box(P["slate"], "twn_slate", tile, divs=(1, 14, 1), skip=("-z", "+x"))
        # gutter
        gx = side * (X_EAVE + 0.02)
        tube(P["metal"], "copper", [(gx, Y_R0, Z_EAVE - 0.08), (gx, Y_R1, Z_EAVE - 0.08)], 0.075, seg=10)
    # ridge cap + barge boards + finial
    tube(P["slate"], "twn_slate", [(0, Y_R0 - 0.04, Z_RIDGE + 0.05), (0, Y_R1 + 0.04, Z_RIDGE + 0.05)], 0.11, seg=8)
    for yb in (Y_R0 - 0.01, Y_R1 + 0.01):
        for side in (-1, 1):
            E, d, n, L = _roof_frame(side)

            def barge(u, v, w, E=E, d=d, n=n, L=L, yb=yb):
                return E + d * (u * L * 1.0 - 0.05 * (1 - u)) + n * (-0.24 + 0.3 * w) + Vector((0, yb - 0.04 + 0.08 * v, 0))
            param_box(P["wood"], "twn_wood", barge, divs=(4, 1, 1))
    revolve(P["wood"], "twn_wood", [(0.0, -0.55), (0.06, -0.5), (0.09, -0.36), (0.05, -0.25), (0.07, -0.1),
                                    (0.07, 0.0), (0.0, 0.02)], seg=10, M=T(0, Y_R0 - 0.06, top - 0.05))
    P["metal"].cone("brass", r=0.04, h=0.3, seg=8, loc=(0, Y_R0 + 0.1, Z_RIDGE + 0.36))
    P["metal"].sphere("brass", r=0.07, seg=10, rings=6, loc=(0, Y_R0 + 0.1, Z_RIDGE + 0.18))
    # downpipe (front-left corner)
    tube(P["metal"], "copper", [(-X_EAVE - 0.04, Y_R0 + 0.12, Z_EAVE - 0.1), (-X_EAVE + 0.05, Y_R0 + 0.25, Z_EAVE - 0.45),
                                (-HW - 0.09, -HD + 0.12, Z_EAVE - 0.75), (-HW - 0.09, -HD + 0.12, 0.35),
                                (-HW - 0.25, -HD + 0.12, 0.08)], 0.055, seg=8)
    for z in (1.0, 2.3, 3.8):
        box(P["metal"], "copper", (0.1, 0.16, 0.05), loc=(-HW - 0.04, -HD + 0.12, z))
    # ---------- chimney (+X slope, behind the ridge) ----------
    cxh, cyh = 1.875, 1.375
    zb = Z_PL + 0.2 * 26            # 5.55, inside the roof
    sh.grid_box(P["brick"], "twn_brick", (0.75, 0.75, 7.75 - zb), divs=(3, 3, int(round((7.75 - zb) / 0.2))),
                M=T(cxh, cyh, (zb + 7.75) / 2), skip=("-z",))
    box(P["stone"], "twn_stone", (0.95, 0.95, 0.12), loc=(cxh, cyh, 7.8))
    for dx in (-0.15, 0.17):
        revolve(P["metal"], "copper", [(0.0, 0.0), (0.11, 0.0), (0.09, 0.2), (0.1, 0.28), (0.08, 0.3), (0.0, 0.3)],
                seg=10, M=T(cxh + dx, cyh, 7.85))
    # ---------- sign bracket (static brass) ----------
    sx_, sy_, sz_ = SIGN_PIVOT
    revolve(P["metal"], "brass", [(0.0, 0.0), (0.16, 0.0), (0.16, 0.03), (0.1, 0.06), (0.05, 0.07), (0.0, 0.07)],
            seg=12, M=T(sx_, Y_J, sz_ + 0.05) @ R("X", 90))
    tube(P["metal"], "brass", [(sx_, Y_J - 0.02, sz_ + 0.05), (sx_, sy_ - 0.1, sz_ + 0.05)], 0.035, seg=8)
    tube(P["metal"], "brass", [(sx_ - 0.55, sy_, sz_ + 0.05), (sx_ + 0.55, sy_, sz_ + 0.05)], 0.03, seg=8)
    for s in (-1, 1):
        P["metal"].sphere("brass", r=0.05, seg=8, rings=5, loc=(sx_ + s * 0.58, sy_, sz_ + 0.05))
    P["metal"].sphere("brass", r=0.06, seg=8, rings=5, loc=(sx_, sy_ - 0.12, sz_ + 0.05))
    # scroll brace under the arm
    pts = []
    for i in range(15):
        t = i / 14
        a = math.pi * 1.6 * t
        rr = 0.32 * (1 - 0.65 * t)
        pts.append((sx_, Y_J - 0.02 - 0.55 * t - math.sin(a) * rr * 0.4, sz_ - 0.55 + 0.55 * t + (1 - math.cos(a)) * rr * 0.25))
    tube(P["metal"], "brass", pts, 0.022, seg=6)
    # ---------- sign (child node, pivot at the crossbar; board faces -Y) ----------
    sk = Kit("sign")
    sw = sk.part("wood", bevel=(0.01, 1, 40), smooth=40)
    sm = sk.part("metal", smooth=40)
    bw_, bh_ = 1.0, 0.6
    btop = -0.2
    slab(sw, "twn_sign", fillet_poly(rect(0, btop - bh_ / 2, bw_, bh_), 0.06, 2), 0.06, bev=0.012, steps=1,
         M=R("X", 90), z0=-0.03)
    outer = fillet_poly(rect(0, btop - bh_ / 2, bw_ + 0.06, bh_ + 0.06), 0.08, 2)
    inner = fillet_poly(rect(0, btop - bh_ / 2, bw_ - 0.06, bh_ - 0.06), 0.04, 2)
    for side in (1, -1):
        ring_plate(sm, "brass", outer, inner, 0.0, 0.025, bev=0.008, steps=1,
                   M=R("Z", 0 if side == 1 else 180) @ R("X", 90) @ T(0, 0, 0.02))
        sh.gear(sm, "brass", 0.14, 8, 0.02, hole=0.05, M=R("Z", 0 if side == 1 else 180) @ R("X", 90) @ T(0, btop - bh_ / 2, 0.04))
    for s in (-1, 1):
        sm.torus("brass", R=0.045, r=0.012, seg=8, seg2=4, loc=(s * 0.4, 0, 0.0), rot=(0, 90, 0))
        sm.torus("brass", R=0.045, r=0.012, seg=8, seg2=4, loc=(s * 0.4, 0, btop + 0.05), rot=(0, 90, 0))
        tube(sm, "brass", [(s * 0.4, 0, -0.04), (s * 0.4, 0, btop + 0.08)], 0.012, seg=5)
    sign_built = sk.build_parts(root, loc=SIGN_PIVOT)
    body_built = kit.build_parts(root)
    sh.bake_parts(body_built, sign_built, distance=0.9, samples=40, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.8, dark=0.78))
    body = kit.join_parts(body_built)
    sign = sk.join_parts(sign_built)
    face_tint(body, {"twn_brick"}, brick_fn(z0=Z_PL, seed=3))
    E, d, n, L = _roof_frame(1)
    dx = 0.34 * abs(d.x)

    def tile_fn(c, nn):
        if abs(nn.z) < 0.2:
            return (1, 1, 1)
        row = int((X_EAVE - abs(c.x)) / dx)
        col = math.floor((c.y + (row % 2) * 0.2036) / 0.4071)
        t = _h(5, row, col, c.x > 0)
        k = 0.72 + 0.36 * t
        return (k, k * (0.98 + 0.04 * _h(6, row, col)), k * 1.02)
    face_tint(body, {"twn_slate"}, tile_fn)
    sh.tint_islands(body, {"twn_wood"}, lo=0.82, hi=1.05, seed=9, streak=0.1, streak_freq=6)
    sh.tint_islands(body, {"twn_stone"}, lo=0.8, hi=1.05, seed=4)
    empty("door_point", parent=root, loc=(DOOR_X, -HD - 0.9, 0.0), size=0.3)
    return root



# ===========================================================================
# prop_locomotive  (long axis X, front = +X; cab roof top at z 4.2)
# ===========================================================================
YZX = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # local (a, b, c) -> world (c, a, b)
RAIL_Z = 0.27
BOILER_Z = 2.45
STACK_X = 5.45
STACK_TOP = 4.5
RUST_T = 0.42


def _ax_x(x, y=0.0, z=0.0):
    """Frame whose local +Z runs along world +X (revolve along the boiler)."""
    return T(x, y, z) @ R("Y", 90)


def _wheel_frame(x, y, zc, side):
    """Local +Z = outward (side * Y). World angle th in the XZ plane -> local angle th * (-side)."""
    return T(x, y, zc) @ R("X", -90 if side > 0 else 90)


def _driver(P, x, y, zc, r, side, crank_deg, spokes=12):
    M = _wheel_frame(x, y, zc, side)
    w = 0.075
    # steel tyre with inner flange + red wheel rim
    revolve(P["steel"], "steel", [(r - 0.06, -w), (r + 0.035, -w), (r + 0.035, -w + 0.03), (r, -w + 0.045),
                                  (r, w), (r - 0.06, w)], seg=24, closed=True, M=M)
    revolve(P["wheel"], "twn_loco_red", [(r - 0.13, -w * 0.7), (r - 0.055, -w * 0.7), (r - 0.055, w * 0.8),
                                         (r - 0.13, w * 0.6)], seg=28, closed=True, M=M)
    hub = r * 0.24
    for k in range(spokes):
        a = 360.0 * k / spokes
        L = r - 0.12 - hub * 0.8
        box(P["wheel"], "twn_loco_red", (L, 0.055, 0.06), M=M @ R("Z", a) @ T(hub * 0.8 + L / 2, 0, 0.01))
    revolve(P["wheel"], "twn_loco_red", [(0.0, 0.07), (hub, 0.07), (hub * 1.1, 0.02), (hub * 1.1, -0.05), (0.0, -0.05)],
            seg=14, M=M)
    revolve(P["brass"], "brass", [(0.0, 0.11), (hub * 0.45, 0.11), (hub * 0.55, 0.06), (0.0, 0.06)], seg=10, M=M)
    # counterweight opposite the crank
    la = math.radians(crank_deg + 180) * (-side)
    arc = [((r - 0.13) * math.cos(la + t), (r - 0.13) * math.sin(la + t)) for t in np.linspace(-0.75, 0.75, 9)]
    arc += [((r * 0.5) * math.cos(la + t), (r * 0.5) * math.sin(la + t)) for t in np.linspace(0.6, -0.6, 7)]
    prism(P["wheel"], "twn_loco_red", arc, -0.03, 0.05, M=M)
    # crank boss + pin
    lc = math.radians(crank_deg) * (-side)
    rp = r * 0.45
    revolve(P["wheel"], "twn_loco_red", [(0.0, 0.08), (0.11, 0.08), (0.12, 0.0), (0.0, 0.0)], seg=10,
            M=M @ T(rp * math.cos(lc), rp * math.sin(lc), 0))
    th = math.radians(crank_deg)
    return Vector((x + rp * math.cos(th), y + side * 0.17, zc + rp * math.sin(th)))


def _disc_wheel(P, x, y, zc, r, side):
    M = _wheel_frame(x, y, zc, side)
    w = 0.07
    revolve(P["steel"], "steel", [(r - 0.05, -w), (r + 0.03, -w), (r + 0.03, -w + 0.025), (r, -w + 0.04),
                                  (r, w), (r - 0.05, w)], seg=20, closed=True, M=M)
    revolve(P["wheel"], "twn_loco_red", [(0.0, 0.03), (r * 0.3, 0.035), (r * 0.5, 0.01), (r - 0.05, 0.02),
                                         (r - 0.05, -0.04), (0.0, -0.04)], seg=16, M=M)
    revolve(P["brass"], "brass", [(0.0, 0.1), (0.07, 0.1), (0.08, 0.03), (0.0, 0.03)], seg=8, M=M)


def _streak(part, origin, down, side, nrm, L, w0, rng, mat="twn_rust"):
    """Tapered rust drip lying on a flat surface (origin on the surface, nrm outward)."""
    ph = rng.uniform(0, 6.28)

    def fn(u, v, w):
        wid = w0 * (1 - 0.85 * v)
        wob = math.sin(v * 5.0 + ph) * w0 * 0.25
        return origin + down * (v * L) + side * ((u - 0.5) * wid + wob) + nrm * (0.002 + 0.004 * w)
    param_box(part, mat, fn, divs=(1, 3, 1), skip=("-z",))


def _boiler_streak(part, x, side, r, rng, mat="twn_rust"):
    """Rust drip running down the boiler side below a band (follows the cylinder)."""
    th0 = math.radians(rng.uniform(-10, 25))
    L = rng.uniform(0.5, 1.0)
    w0 = rng.uniform(0.07, 0.12)
    ph = rng.uniform(0, 6.28)

    def fn(u, v, w):
        th = th0 - v * L / r
        wid = w0 * (1 - 0.85 * v)
        xx = x + (u - 0.5) * wid + math.sin(v * 5 + ph) * w0 * 0.25
        rr = r + 0.003 + 0.004 * w
        return Vector((xx, side * rr * math.cos(th), BOILER_Z + rr * math.sin(th)))
    param_box(part, mat, fn, divs=(1, 4, 1), skip=("-z",))


def _rect_path(x0, x1, y0, y1, z):
    return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z)]


def build_locomotive():
    root = empty("prop_locomotive", size=1.0)
    rng = random.Random(5)
    kit = Kit("prop_locomotive_body")
    P = {
        "black": kit.part("black", smooth=40),
        "black_b": kit.part("black_b", bevel=(0.02, 1, 40), smooth=40),
        "red": kit.part("red", bevel=(0.015, 1, 40), smooth=40),
        "wheel": kit.part("wheel", smooth=40),
        "brass": kit.part("brass", smooth=40),
        "steel": kit.part("steel", smooth=40),
        "track": kit.part("track", smooth=40),
        "coal": kit.part("coal", flat=True, occluder=False),
        "small": kit.part("small", smooth=50, occluder=False),
        "lamp": kit.part("lamp", smooth=None, occluder=False),
    }
    # ---------- track ----------
    for i in range(20):
        x = -6.65 + i * 0.7 + rng.uniform(-0.03, 0.03)
        box(P["track"], "twn_sleeper", (0.26, 2.5, 0.13), loc=(x, rng.uniform(-0.04, 0.04), 0.065),
            M=R("Z", rng.uniform(-1.5, 1.5)))
    rail = [(-0.07, 0), (0.07, 0), (0.07, 0.02), (0.022, 0.04), (0.022, 0.105), (0.04, 0.115), (0.04, 0.15),
            (-0.04, 0.15), (-0.04, 0.115), (-0.022, 0.105), (-0.022, 0.04), (-0.07, 0.02)]
    for sy in (-1, 1):
        prism(P["steel"], "steel", rail, -7.0, 7.0, M=T(0, sy * 0.72, 0.12) @ YZX)
    # ---------- frames + running boards ----------
    for sy in (-1, 1):
        box(P["black_b"], "twn_loco", (7.4, 0.09, 0.62), loc=(2.3, sy * 0.52, 1.07))
        box(P["black_b"], "twn_loco", (5.4, 0.36, 0.05), loc=(3.25, sy * 1.16, 1.86))
        box(P["red"], "twn_loco_red", (5.4, 0.03, 0.24), loc=(3.25, sy * 1.33, 1.73))
        tube(P["brass"], "brass", [(0.55, sy * 1.35, 1.86), (5.95, sy * 1.35, 1.86)], 0.018, seg=6)
    # ---------- wheels ----------
    crank = 30.0
    pins = {}
    for sy in (-1, 1):
        pins[sy] = [_driver(P, x, sy * 0.78, RAIL_Z + 0.75, 0.75, sy, crank) for x in (0.3, 1.9, 3.5)]
        _disc_wheel(P, 5.62, sy * 0.78, RAIL_Z + 0.42, 0.42, sy)
        for x in (-6.2, -5.1, -3.5, -2.4):
            _disc_wheel(P, x, sy * 0.78, RAIL_Z + 0.42, 0.42, sy)
    # axles
    for x in (0.3, 1.9, 3.5):
        P["steel"].cyl("steel", r=0.09, h=1.7, seg=8, loc=(x, 0, RAIL_Z + 0.75), rot=(90, 0, 0))
    for x in (5.62, -6.2, -5.1, -3.5, -2.4):
        P["steel"].cyl("steel", r=0.07, h=1.65, seg=8, loc=(x, 0, RAIL_Z + 0.42), rot=(90, 0, 0))
    # ---------- cylinders, rods ----------
    for sy in (-1, 1):
        yc = sy * 1.05
        revolve(P["black"], "twn_loco", [(0.0, 0.0), (0.3, 0.0), (0.34, 0.06), (0.34, 0.94), (0.3, 1.0), (0.0, 1.0)],
                seg=18, M=_ax_x(4.15, yc, 1.17))
        for xx in (4.17, 5.13):
            P["brass"].torus("brass", R=0.33, r=0.025, seg=18, seg2=5, loc=(xx, yc, 1.17), rot=(0, 90, 0))
        box(P["black_b"], "twn_loco", (0.8, 0.36, 0.3), loc=(4.65, yc * 0.98, 1.62))
        # guide bars, crosshead, piston rod
        box(P["steel"], "steel", (1.1, 0.05, 0.05), loc=(3.6, yc, 1.3))
        box(P["steel"], "steel", (1.1, 0.05, 0.05), loc=(3.6, yc, 1.04))
        box(P["steel"], "steel", (0.22, 0.12, 0.22), loc=(3.35, yc, 1.17))
        P["steel"].cyl("steel", r=0.035, h=0.85, seg=8, loc=(3.75, yc, 1.17), rot=(0, 90, 0))
        # side rods over the crank pins + main rod to the middle driver
        ps = pins[sy]
        yr = sy * 0.97
        tube(P["steel"], "steel", [(ps[0].x - 0.12, yr, ps[0].z), (ps[2].x + 0.12, yr, ps[2].z)], 0.05, seg=6)
        tube(P["steel"], "steel", [(3.35, sy * 1.05, 1.17), (ps[1].x, sy * 1.03, ps[1].z)], 0.055, seg=6)
        for pp in ps:
            P["steel"].cyl("steel", r=0.06, h=0.2, seg=8, loc=(pp.x, sy * 1.0, pp.z), rot=(90, 0, 0))
    box(P["black_b"], "twn_loco", (0.9, 1.6, 0.6), loc=(4.65, 0, 1.35))      # smokebox saddle
    # ---------- boiler + smokebox ----------
    prof = [(0.85, z) for z in np.linspace(0.0, 4.3, 11)]
    revolve(P["black"], "twn_loco", prof, seg=28, M=_ax_x(0.55, 0, BOILER_Z))
    revolve(P["black"], "twn_loco", [(0.0, 0.0), (0.95, 0.0)] + [(0.95, z) for z in np.linspace(0.12, 1.0, 4)] +
            [(0.93, 1.06), (0.88, 1.12)], seg=28, M=_ax_x(4.85, 0, BOILER_Z))
    revolve(P["black"], "twn_loco", [(0.88, 0.0), (0.7, 0.05), (0.45, 0.1), (0.0, 0.12)], seg=28,
            M=_ax_x(5.97, 0, BOILER_Z))
    for x in (1.35, 2.35, 3.55, 4.55):
        P["brass"].torus("brass", R=0.86, r=0.032, seg=28, seg2=4, loc=(x, 0, BOILER_Z), rot=(0, 90, 0))
    P["brass"].torus("brass", R=0.9, r=0.04, seg=28, seg2=6, loc=(5.98, 0, BOILER_Z), rot=(0, 90, 0))
    P["brass"].torus("brass", R=0.96, r=0.035, seg=28, seg2=6, loc=(4.86, 0, BOILER_Z), rot=(0, 90, 0))
    # smokebox door: hinge straps, handle, number plate
    for zz in (-0.35, 0.3):
        box(P["black_b"], "twn_loco", (0.04, 1.3, 0.08), loc=(6.03, -0.2, BOILER_Z + zz))
    P["brass"].torus("brass", R=0.13, r=0.025, seg=12, seg2=5, loc=(6.12, 0, BOILER_Z), rot=(0, 90, 0))
    box(P["brass"], "brass", (0.03, 0.3, 0.03), loc=(6.12, 0, BOILER_Z))
    box(P["brass"], "brass", (0.03, 0.03, 0.3), loc=(6.12, 0, BOILER_Z))
    plate(P["brass"], "brass", fillet_poly(rect(0, 0, 0.62, 0.2), 0.08, 2), 0.03, bev=0.01, steps=1,
          M=T(6.01, 0, BOILER_Z + 0.62) @ R("Y", 90) @ R("Z", 90))
    # rivet ring on the smokebox
    for k in range(16):
        a = 2 * math.pi * k / 16
        n = Vector((0, math.cos(a), math.sin(a)))
        rivet(P["small"], "twn_loco", Vector((4.98, 0, BOILER_Z)) + n * 0.95, n, r=0.025, h=0.02, seg=5)
    # smokestack + steam point
    revolve(P["black"], "twn_loco", [(0.34, 3.2), (0.31, 3.42), (0.27, 3.9), (0.29, 4.1), (0.38, 4.3), (0.43, 4.42),
                                     (0.41, STACK_TOP), (0.32, STACK_TOP), (0.24, 4.38), (0.0, 4.38)], seg=20,
            M=T(STACK_X, 0, 0))
    P["brass"].torus("brass", R=0.42, r=0.03, seg=20, seg2=5, loc=(STACK_X, 0, 4.44))
    P["brass"].torus("brass", R=0.3, r=0.025, seg=20, seg2=5, loc=(STACK_X, 0, 3.5))
    # domes, whistle, safety valve
    revolve(P["brass"], "brass", [(0.5, 3.12), (0.47, 3.36), (0.42, 3.44), (0.42, 3.55), (0.38, 3.7), (0.3, 3.82),
                                  (0.17, 3.9), (0.0, 3.93)], seg=20, M=T(3.05, 0, 0))
    revolve(P["black"], "twn_loco", [(0.36, 3.12), (0.33, 3.36), (0.3, 3.5), (0.0, 3.5)], seg=16, M=T(1.85, 0, 0))
    revolve(P["brass"], "brass", [(0.31, 3.49), (0.27, 3.56), (0.16, 3.63), (0.0, 3.65)], seg=16, M=T(1.85, 0, 0))
    revolve(P["brass"], "brass", [(0.05, 3.25), (0.05, 3.6), (0.08, 3.62), (0.08, 3.92), (0.06, 3.97), (0.0, 3.99)],
            seg=10, M=T(0.85, 0, 0))
    for dy in (-0.12, 0.12):
        revolve(P["brass"], "brass", [(0.06, 3.25), (0.06, 3.5), (0.09, 3.52), (0.09, 3.6), (0.0, 3.64)], seg=8,
                M=T(1.25, dy, 0))
    # handrails
    for sy in (-1, 1):
        tube(P["steel"], "steel", [(0.65, sy * 0.98, 2.8), (5.7, sy * 0.98, 2.8)], 0.022, seg=6)
        for x in (0.9, 2.0, 3.2, 4.3, 5.5):
            P["steel"].cyl("steel", r=0.016, h=0.16, seg=6, loc=(x, sy * 0.91, 2.78), rot=(90, 0, 0))
    # headlamp
    box(P["black_b"], "twn_loco", (0.36, 0.42, 0.42), loc=(5.8, 0, 3.55))
    box(P["black_b"], "twn_loco", (0.44, 0.5, 0.06), loc=(5.8, 0, 3.79))
    P["brass"].torus("brass", R=0.15, r=0.025, seg=14, seg2=5, loc=(5.99, 0, 3.55), rot=(0, 90, 0))
    revolve(P["lamp"], "glow_twn_lamp", [(0.0, 0.03), (0.14, 0.0)], seg=14, M=_ax_x(5.97, 0, 3.55), cap1=False)
    # ---------- buffer beam, buffers, pilot ----------
    box(P["red"], "twn_loco_red", (0.2, 2.7, 0.5), loc=(6.1, 0, 1.25), divs=(1, 3, 1))
    for sy in (-1, 1):
        P["steel"].cyl("steel", r=0.09, h=0.35, seg=10, loc=(6.35, sy * 0.95, 1.25), rot=(0, 90, 0))
        revolve(P["steel"], "steel", [(0.0, 0.0), (0.22, 0.0), (0.22, 0.05), (0.18, 0.08), (0.0, 0.09)], seg=16,
                M=_ax_x(6.5, sy * 0.95, 1.25))
    P["steel"].torus("steel", R=0.07, r=0.025, seg=10, seg2=5, loc=(6.33, 0, 1.25), rot=(90, 0, 0))
    bottom = lambda y: Vector((6.95 - 0.4 * abs(y) / 1.25, y, 0.36))
    top = lambda y: Vector((6.25, y, 1.02))
    for k in range(11):
        y = -1.2 + 2.4 * k / 10
        tube(P["red"], "twn_loco_red", [top(y), bottom(y)], 0.035, seg=6)
    tube(P["red"], "twn_loco_red", [bottom(-1.25), bottom(0), bottom(1.25)], 0.05, seg=6)
    tube(P["red"], "twn_loco_red", [top(-1.25), top(1.25)], 0.05, seg=6)
    # ---------- cab ----------
    cx0, cx1, cw = -1.35, 0.55, 1.3
    def cab_profile(n=12):
        pts = [(-cw, 1.86), (cw, 1.86), (cw, 3.95)]
        for i in range(1, n):
            y = cw - 2 * cw * i / n
            pts.append((y, 3.95 + 0.18 * math.cos(math.pi * y / (2 * cw))))
        pts.append((-cw, 3.95))
        return pts
    prism(P["black"], "twn_loco", cab_profile(), cx1 - 0.08, cx1, M=YZX)
    for sy in (-1, 1):
        ys = sy * cw
        box(P["black_b"], "twn_loco", (cx1 - cx0, 0.07, 1.12), loc=((cx0 + cx1) / 2, ys, 1.86 + 0.56), divs=(4, 1, 2))
        box(P["black_b"], "twn_loco", (0.3, 0.07, 1.1), loc=(cx1 - 0.15, ys, 3.5))
        box(P["black_b"], "twn_loco", (0.22, 0.07, 1.1), loc=(cx0 + 0.11, ys, 3.5))
        box(P["black_b"], "twn_loco", (cx1 - cx0, 0.07, 0.22), loc=((cx0 + cx1) / 2, ys, 3.86))
        # brass window beading + number plate + red lining
        tube(P["brass"], "brass", _rect_path(cx0 + 0.22, cx1 - 0.3, ys + sy * 0.04, ys + sy * 0.04, 0)[:1] and
             [(cx0 + 0.22, ys + sy * 0.04, 2.98), (cx1 - 0.3, ys + sy * 0.04, 2.98), (cx1 - 0.3, ys + sy * 0.04, 3.75),
              (cx0 + 0.22, ys + sy * 0.04, 3.75), (cx0 + 0.22, ys + sy * 0.04, 2.98)], 0.02, seg=5)
        plate(P["brass"], "brass", fillet_poly(rect(0, 0, 0.7, 0.32), 0.12, 3), 0.025, bev=0.008, steps=1,
              M=T(-0.4, ys + sy * 0.035, 2.45) @ R("X", -90 * sy))
        box(P["red"], "twn_loco_red", (cx1 - cx0 - 0.1, 0.02, 0.05), loc=((cx0 + cx1) / 2, ys + sy * 0.04, 2.0))
        # cab steps
        for zz in (1.1, 1.5):
            box(P["black_b"], "twn_loco", (0.4, 0.22, 0.04), loc=(cx0 + 0.35, sy * (cw + 0.06), zz))
        box(P["black_b"], "twn_loco", (0.04, 0.22, 0.85), loc=(cx0 + 0.15, sy * (cw + 0.06), 1.45))
        box(P["black_b"], "twn_loco", (0.04, 0.22, 0.85), loc=(cx0 + 0.55, sy * (cw + 0.06), 1.45))
        # spectacle windows on the cab front
        Mw = T(cx1 + 0.005, sy * 0.85, 3.45) @ R("Y", 90)
        ring_plate(P["brass"], "brass", circle2d(0.24, 16), circle2d(0.18, 16), 0.0, 0.04, bev=0.01, steps=1, M=Mw)
        prism(P["lamp"], "twn_pane", circle2d(0.185, 16), 0.0, 0.015, M=Mw)
    # roof (arched, overhanging; top at z 4.2)
    def roof(u, v, w):
        y = -1.48 + 2.96 * v
        z = 3.98 + 0.17 * math.cos(math.pi * y / 3.0) + 0.05 * w
        return Vector((-1.6 + 2.4 * u, y, z))
    param_box(P["black_b"], "twn_loco", roof, divs=(2, 10, 1))
    # floor + backhead details
    box(P["black_b"], "twn_loco", (cx1 - cx0, 2 * cw, 0.08), loc=((cx0 + cx1) / 2, 0, 1.84))
    revolve(P["black"], "twn_loco", [(0.0, 0.0), (0.8, 0.0), (0.8, 0.05), (0.0, 0.05)], seg=20, M=_ax_x(cx1 - 0.15, 0, BOILER_Z))
    box(P["brass"], "brass", (0.06, 0.5, 0.36), loc=(cx1 - 0.2, 0, 2.15))
    for dy in (-0.35, 0.35):
        revolve(P["brass"], "brass", [(0.0, 0.0), (0.1, 0.0), (0.1, 0.05), (0.0, 0.06)], seg=12,
                M=_ax_x(cx1 - 0.2, dy, 2.95) @ R("Y", 180))
    tube(P["brass"], "brass", [(cx1 - 0.15, 0.0, 3.2), (cx1 - 0.35, 0.25, 3.0)], 0.025, seg=6)
    # ---------- tender ----------
    tx0, tx1, tw2 = -6.85, -1.75, 1.22
    box(P["black_b"], "twn_loco", (tx1 - tx0, 1.2, 0.36), loc=((tx0 + tx1) / 2, 0, 0.98))
    for sy in (-1, 1):
        for xc in (-5.65, -2.95):
            box(P["black_b"], "twn_loco", (1.75, 0.08, 0.32), loc=(xc, sy * 0.92, RAIL_Z + 0.48))
            for dx in (-0.55, 0.55):
                box(P["black_b"], "twn_loco", (0.22, 0.14, 0.26), loc=(xc + dx, sy * 0.95, RAIL_Z + 0.44))
            # leaf spring
            sh.sweep_band(P["black"], "twn_loco", [(xc - 0.5, sy * 0.95, RAIL_Z + 0.78), (xc, sy * 0.95, RAIL_Z + 0.68),
                                                   (xc + 0.5, sy * 0.95, RAIL_Z + 0.78)],
                          [(0, 0, 1)] * 3, 0.12, 0.06)
    sh.grid_box(P["black"], "twn_loco", (tx1 - tx0, 2 * tw2, 1.9), divs=(16, 7, 6), M=T((tx0 + tx1) / 2, 0, 1.16 + 0.95),
                skip=("+z",))
    # flared coping around the top
    for (a, b, nrm) in (((tx0, -tw2), (tx1, -tw2), (0, -1)), ((tx1, tw2), (tx0, tw2), (0, 1)),
                        ((tx0, tw2), (tx0, -tw2), (-1, 0))):
        def cop(u, v, w, a=a, b=b, nrm=nrm):
            p = Vector((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 0))
            out = Vector((nrm[0], nrm[1], 0))
            p += out * (0.0 + 0.16 * v + 0.05 * w)
            p.z = 3.05 + 0.3 * v
            return p
        param_box(P["black_b"], "twn_loco", cop, divs=(4, 1, 1))
    tube(P["brass"], "brass", [(tx1, -tw2 - 0.21, 3.36), (tx0 - 0.21, -tw2 - 0.21, 3.36), (tx0 - 0.21, tw2 + 0.21, 3.36),
                               (tx1, tw2 + 0.21, 3.36)], 0.025, seg=6)
    tube(P["brass"], "brass", [(tx1, -tw2 - 0.01, 1.3), (tx0 - 0.01, -tw2 - 0.01, 1.3), (tx0 - 0.01, tw2 + 0.01, 1.3),
                               (tx1, tw2 + 0.01, 1.3)], 0.02, seg=6)
    # tank top + water hatch at the back, coal heap at the front
    box(P["black"], "twn_loco", (2.2, 2 * tw2 - 0.02, 0.06), loc=(tx0 + 1.1, 0, 3.08))
    revolve(P["brass"], "brass", [(0.0, 3.08), (0.36, 3.08), (0.36, 3.26), (0.4, 3.3), (0.36, 3.34), (0.0, 3.36)],
            seg=18, M=T(tx0 + 0.9, 0.3, 0))
    box(P["black"], "twn_loco", (tx1 - tx0 - 2.2, 2 * tw2 - 0.02, 0.06), loc=(tx1 - (tx1 - tx0 - 2.2) / 2, 0, 3.0))
    crng = random.Random(77)
    for i in range(34):
        x = crng.uniform(tx0 + 2.35, tx1 - 0.2)
        y = crng.uniform(-tw2 + 0.25, tw2 - 0.25)
        hgt = 3.15 + 0.45 * (1 - abs(y) / tw2) * min(1.0, (x - tx0 - 2.2) / 0.9) * min(1.0, (tx1 - x) / 0.6)
        sh.blob(P["coal"], "twn_coal", crng.uniform(0.22, 0.38), loc=(x, y, hgt - 0.12), scale=(1.2, 1.0, 0.7),
                subdiv=1, amount=0.35, seed=crng.randrange(9999))
    # rear: ladder + buffer beam + buffers
    for zz in np.linspace(1.5, 3.0, 5):
        box(P["steel"], "steel", (0.05, 0.42, 0.04), loc=(tx0 - 0.1, 0.5, zz))
    for dy in (0.3, 0.7):
        box(P["steel"], "steel", (0.05, 0.04, 1.75), loc=(tx0 - 0.08, dy, 2.28))
    box(P["red"], "twn_loco_red", (0.18, 2.6, 0.45), loc=(tx0 - 0.02, 0, 1.0), divs=(1, 3, 1))
    for sy in (-1, 1):
        P["steel"].cyl("steel", r=0.08, h=0.25, seg=10, loc=(tx0 - 0.2, sy * 0.95, 1.0), rot=(0, 90, 0))
        revolve(P["steel"], "steel", [(0.0, 0.0), (0.2, 0.0), (0.2, 0.05), (0.0, 0.07)], seg=14,
                M=_ax_x(tx0 - 0.3, sy * 0.95, 1.0) @ R("Y", 180))
    # rivet rows on the tender sides
    for sy in (-1, 1):
        for zz in (1.42, 2.92):
            for x in np.linspace(tx0 + 0.15, tx1 - 0.15, 14):
                rivet(P["small"], "twn_loco", (x, sy * tw2, zz), (0, sy, 0), r=0.022, h=0.016, seg=5)
    # drawbar
    box(P["black_b"], "twn_loco", (0.6, 0.3, 0.16), loc=(-1.55, 0, 1.1))
    # ---------- rust streaks (thin tapered decals running down from seams) ----------
    srng = random.Random(31)
    rs = kit.part("rust", smooth=40, occluder=False)
    for sy in (-1, 1):
        for x in np.linspace(tx0 + 0.4, tx1 - 0.4, 7):
            for z0 in (3.0, 2.86):
                if srng.random() < 0.45:
                    continue
                _streak(rs, Vector((x + srng.uniform(-0.25, 0.25), sy * (tw2 + 0.004), z0)), Vector((0, 0, -1)),
                        Vector((1, 0, 0)), Vector((0, sy, 0)), srng.uniform(0.35, 1.0), srng.uniform(0.07, 0.13), srng)
        for x in (cx0 + 0.5, cx1 - 0.5):
            _streak(rs, Vector((x + srng.uniform(-0.1, 0.1), sy * (cw + 0.04), 2.9)), Vector((0, 0, -1)), Vector((1, 0, 0)),
                    Vector((0, sy, 0)), srng.uniform(0.4, 0.7), 0.09, srng)
    for x in (1.35, 2.35, 3.55, 4.55, 4.86):
        for sy in (-1, 1):
            if srng.random() < 0.3:
                continue
            _boiler_streak(rs, x + srng.uniform(-0.06, 0.12), sy, 0.96 if x > 4.8 else 0.85, srng)
    # ---------- finishing: rust patches, AO, steam point ----------
    built = kit.build_parts(root)

    def rusty(p, n):
        if p.z > 1.75 or p.x > 6.3:
            return False
        blot = fbm(p * 0.55, seed=8, octaves=2)
        return blot + smoothstep(1.7, 1.15, p.z) * 0.35 > RUST_T
    nr = sum(paint_faces(o, "twn_loco", "twn_rust", rusty) for o, _ in built)
    print(f"[loco] rust faces {nr}")
    sh.bake_parts(built, distance=0.7, samples=40, strength=0.85, floor=0.28, tint=sh.ground_grime(0.0, 0.6, dark=0.8))
    obj = kit.join_parts(built)
    sh.tint_islands(obj, {"twn_sleeper"}, lo=0.75, hi=1.05, seed=3, streak=0.1, streak_freq=8)
    sh.tint_islands(obj, {"twn_rust"}, lo=0.75, hi=1.1, seed=5, hue=(1.08, 0.95, 0.85))
    empty("steam_point", parent=root, loc=(STACK_X, 0, STACK_TOP - 0.05), size=0.3)
    return root



# ===========================================================================
# prop_nail_board  (front = -Y; board 2.2 x 1.6 m, roof ridge along X)
# ===========================================================================
NB_W, NB_Z0, NB_Z1 = 2.2, 0.85, 2.45
NB_Y = -0.035                          # front face of the planks
NOTICES = [  # (centre x, top z, w, h, tilt deg, kind)
    (-0.62, 2.3, 0.46, 0.6, -4.0, "lines"),
    (0.1, 2.27, 0.5, 0.42, 3.0, "seal"),
    (0.68, 2.2, 0.4, 0.52, -2.5, "gear"),
    (-0.05, 1.68, 0.44, 0.56, 5.0, "lines"),
]


def _notice(root, idx, cx, ztop, w, h, tilt, kind, rng):
    k = Kit(f"notice_{idx}")
    pp = k.part("paper", smooth=40)
    ink = k.part("ink", smooth=None, recalc=False, occluder=False)
    pivot = (cx, NB_Y - 0.004, ztop)
    Mt = R("Y", tilt)                      # tilt in the board plane (XZ)
    curl0 = rng.uniform(0.01, 0.03)

    def fn(u, v, w_, curl0=curl0):
        x = (u - 0.5) * w
        z = -v * h
        bend = curl0 * (v ** 2.2) * (0.4 + abs(u - 0.5) * 1.6) + 0.004 * math.sin(u * 7 + v * 3)
        p_ = Mt @ Vector((x, -bend - 0.0025 * w_, z))
        return p_
    param_box(pp, "twn_paper", fn, divs=(4, 5, 1))
    # ink (front-facing strokes, frame normal = -Y)
    Mi = Mt @ R("X", 90)                   # local (a, b, c) -> (a, -c, b): b = z, c = towards -Y
    lines = []
    if kind in ("lines", "seal"):
        y = -0.1
        lines.append(((-w * 0.32, y + 0.02), (w * 0.32, y + 0.02)))
        y -= 0.07
        while y > -h + 0.08:
            L = rng.uniform(0.45, 0.8) * w * 0.8
            lines.append(((-w * 0.36, y), (-w * 0.36 + L, y)))
            y -= rng.uniform(0.045, 0.06)
    rings = []
    if kind == "gear":
        lines.append(((-w * 0.3, -0.08), (w * 0.3, -0.08)))
        rings.append((0.0, -h * 0.5, w * 0.22))
        for a in range(8):
            t = a * math.pi / 4
            r0, r1 = w * 0.22, w * 0.3
            lines.append(((r0 * math.cos(t), -h * 0.5 + r0 * math.sin(t)), (r1 * math.cos(t), -h * 0.5 + r1 * math.sin(t))))
        lines.append(((-w * 0.3, -h + 0.07), (w * 0.15, -h + 0.07)))
    sh.stroke_quads(ink, "twn_ink", Mi @ T(0, 0, 0.0045), lines, rings, sw=0.012, lift=0.0, ring_seg=16)
    if kind == "seal":
        c = Mt @ Vector((w * 0.28, -0.012, -h + 0.08))
        revolve(pp, "cloth_red", [(0.0, 0.0), (0.04, 0.0), (0.045, 0.006), (0.0, 0.01)], seg=10,
                M=T(*c) @ R("X", 90))
    return k.build_parts(root, loc=pivot)


def build_nail_board():
    root = empty("prop_nail_board", size=0.6)
    rng = random.Random(41)
    kit = Kit("prop_nail_board_body")
    wood = kit.part("wood", bevel=(0.012, 1, 40), smooth=40)
    plank = kit.part("plank", bevel=(0.008, 1, 40), smooth=40)
    roof = kit.part("roof", smooth=None)
    metal = kit.part("metal", smooth=45, occluder=False)
    stone = kit.part("stone", smooth=50)
    px = NB_W / 2 + 0.11
    # posts + stone footings
    for sx in (-1, 1):
        box(wood, "twn_wood", (0.15, 0.15, 2.78), loc=(sx * px, 0.02, 1.39), divs=(1, 1, 4))
        sh.blob(stone, "stone", 0.2, loc=(sx * px, 0.02, 0.05), scale=(1.3, 1.2, 0.6), subdiv=2, amount=0.25,
                seed=60 + sx, floor=0.0)
        revolve(wood, "twn_wood", [(0.1, 0.0), (0.1, 0.05), (0.06, 0.09), (0.0, 0.1)], seg=8, M=T(sx * px, 0.02, 2.78))
    # back battens + planks
    for z in (1.1, 2.2):
        box(wood, "twn_wood", (2 * px, 0.06, 0.12), loc=(0, 0.06, z))
    n = 6
    pw = NB_W / n
    for i in range(n):
        x = -NB_W / 2 + pw * (i + 0.5)
        box(plank, "twn_board", (pw - 0.012, 0.05, NB_Z1 - NB_Z0 - rng.uniform(0, 0.02)),
            loc=(x, NB_Y + 0.025 + rng.uniform(-0.003, 0.003), (NB_Z0 + NB_Z1) / 2), divs=(1, 1, 3),
            M=R("Y", rng.uniform(-0.4, 0.4)))
    # frame boards around the front
    fb = 0.09
    for (x0, z0, x1, z1) in ((-NB_W / 2 - fb, NB_Z1, NB_W / 2 + fb, NB_Z1), (-NB_W / 2 - fb, NB_Z0, NB_W / 2 + fb, NB_Z0)):
        box(wood, "twn_wood", (x1 - x0, 0.045, fb * 1.2), loc=((x0 + x1) / 2, NB_Y - 0.012, z0))
    for sx in (-1, 1):
        box(wood, "twn_wood", (fb, 0.045, NB_Z1 - NB_Z0), loc=(sx * (NB_W / 2 + 0.01), NB_Y - 0.012, (NB_Z0 + NB_Z1) / 2))
    # brass title plaque + corner plates
    plate(metal, "brass", fillet_poly(rect(0, 0, 0.62, 0.16), 0.05, 2), 0.015, bev=0.006, steps=1,
          M=T(0, NB_Y - 0.035, NB_Z1 + 0.11) @ R("X", 90))
    sh.stroke_quads(kit.part("plaque_ink", smooth=None, recalc=False, occluder=False), "twn_ink",
                    T(0, NB_Y - 0.051, NB_Z1 + 0.11) @ R("X", 90),
                    [((-0.22, 0.0), (0.22, 0.0)), ((-0.22, 0.035), (-0.22, -0.035)), ((0.22, 0.035), (0.22, -0.035))],
                    sw=0.012, lift=0.0)
    box(wood, "twn_wood", (0.7, 0.05, 0.2), loc=(0, NB_Y - 0.008, NB_Z1 + 0.11))
    for sx in (-1, 1):
        for z in (NB_Z0, NB_Z1):
            plate(metal, "brass", [(0, 0), (0.12 * -sx, 0), (0, 0.12 * (1 if z == NB_Z0 else -1))], 0.008, bev=0.003,
                  steps=1, M=T(sx * (NB_W / 2 + 0.05), NB_Y - 0.035, z) @ R("X", 90))
    # roof: tie beam, struts, two slopes of shingles, ridge
    box(wood, "twn_wood", (2 * px + 0.3, 0.12, 0.12), loc=(0, 0.02, 2.66))
    for sx in (-1, 1):
        beam(wood, "twn_wood", T(0, 0.02, 0) @ R("X", 90), sx * px, 2.25, sx * (px - 0.35), 2.62, 0.1, 0.09, c0=-0.045)
    apex, eave_y, eave_z = 3.0, 0.62, 2.62
    for sy in (-1, 1):
        E = Vector((0, sy * eave_y, eave_z))
        d = (Vector((0, 0, apex)) - E)
        L = d.length
        d.normalize()
        nrm = Vector((0, sy * (apex - eave_z), eave_y)).normalized()

        def under(u, v, w, E=E, d=d, nrm=nrm, L=L):
            return E + d * (v * L) + nrm * (-0.05 + 0.05 * w) + Vector((-1.55 + 3.1 * u, 0, 0))
        param_box(wood, "twn_wood", under, divs=(3, 1, 1))
        for r in range(4):
            s0, s1 = r * 0.2, min(r * 0.2 + 0.26, L + 0.02)

            def sh_(u, v, w, s0=s0, s1=s1, E=E, d=d, nrm=nrm):
                s_ = s0 + (s1 - s0) * v
                return E + d * s_ + nrm * (0.035 * (1 - v) + 0.025 * w) + Vector((-1.6 + 3.2 * u, 0, 0))
            param_box(roof, "twn_wood", sh_, divs=(16, 1, 1), skip=("-z", "+y"))
    tube(wood, "twn_wood", [(-1.62, 0, apex + 0.04), (1.62, 0, apex + 0.04)], 0.06, seg=8)
    for sx in (-1, 1):
        metal.sphere("brass", r=0.06, seg=10, rings=6, loc=(sx * 1.62, 0, apex + 0.04))
    # nails: 4 hold notices, the rest scattered (old holes / empty nails)
    nails = []
    for (cx, zt, w, h, tilt, kind) in NOTICES:
        nails.append((cx, zt - 0.025))
    tries = 0
    while len(nails) < 31 and tries < 4000:
        tries += 1
        x = rng.uniform(-NB_W / 2 + 0.1, NB_W / 2 - 0.1)
        z = rng.uniform(NB_Z0 + 0.1, NB_Z1 - 0.1)
        hidden = any(abs(x - cx) < w / 2 + 0.02 and zt - h - 0.02 < z < zt + 0.01 for (cx, zt, w, h, _, _) in NOTICES)
        if hidden or any(math.hypot(x - a, z - b) < 0.13 for (a, b) in nails):
            continue
        nails.append((x, z))
    for (x, z) in nails:
        revolve(metal, "twn_nail", [(0.0, -0.01), (0.024, -0.01), (0.024, 0.0), (0.02, 0.007), (0.0, 0.011)], seg=8,
                M=T(x, NB_Y - 0.012, z) @ R("X", 90))
    built = [kit.build_parts(root)]
    for i, (cx, zt, w, h, tilt, kind) in enumerate(NOTICES):
        built.append(_notice(root, i + 1, cx, zt, w, h, tilt, kind, rng))
    sh.bake_parts(*built, distance=0.35, samples=40, strength=0.85, floor=0.3, tint=sh.ground_grime(0.0, 0.4, dark=0.8))
    objs = [kit.join_parts(built[0])]
    for i in range(len(NOTICES)):
        objs.append(sh.join([o for o, _ in built[i + 1]], f"notice_{i + 1}"))
    sh.tint_islands(objs[0], {"twn_board", "twn_wood"}, lo=0.8, hi=1.05, seed=2, streak=0.12, streak_freq=9)
    for o in objs[1:]:
        sh.tint_islands(o, {"twn_paper"}, lo=0.88, hi=1.0, seed=len(o.name), hue=(1.0, 0.97, 0.9))
    return root


# ===========================================================================
# prop_organ "Pippe"  (front = -Y, 3.2 m; child jaw + pipe_01..12 + steam_point)
# ===========================================================================
OR_HINGE = (0.0, -0.74, 1.05)          # jaw pivot: lower front edge of the key recess
OR_FAN_C = Vector((0.0, 0.58, 0.85))   # pipes radiate from here
OR_TOP = 3.2


def _pipe_angles():
    return [(-1 if i < 6 else 1) * (5.0 + 10.0 * (5 - i if i < 6 else i - 6)) for i in range(12)]


def build_organ():
    root = empty("prop_organ", size=0.6)
    rng = random.Random(8)
    kit = Kit("prop_organ_body")
    wd = kit.part("wood", bevel=(0.012, 1, 40), smooth=40)
    wr = kit.part("wood_round", smooth=45)
    br = kit.part("brass", smooth=45)
    keys = kit.part("keys", bevel=(0.004, 1, 40), smooth=40, occluder=False)
    eye = kit.part("eye", smooth=None, occluder=False)
    felt = kit.part("felt", smooth=40)
    W2, D0, D1 = 0.86, -0.46, 0.44
    # feet (brass ball-and-claw-ish)
    for sx in (-1, 1):
        for y in (D0 + 0.12, D1 - 0.12):
            revolve(br, "twn_pipe", [(0.0, 0.0), (0.09, 0.02), (0.11, 0.08), (0.09, 0.15), (0.06, 0.2), (0.08, 0.25),
                                     (0.0, 0.26)], seg=12, M=T(sx * (W2 - 0.12), y, 0))
    # lower console
    box(wd, "twn_walnut", (2 * W2, D1 - D0, 0.12), loc=(0, (D0 + D1) / 2, 0.3))
    box(wd, "twn_walnut", (2 * W2 - 0.08, D1 - D0 - 0.06, 0.72), loc=(0, (D0 + D1) / 2 + 0.02, 0.69), divs=(3, 2, 2))
    Ff = F_front(D0 + 0.01)
    for cx in (-0.48, 0.0, 0.48):
        ring_plate(wd, "twn_walnut", fillet_poly(rect(cx, 0.68, 0.4, 0.5), 0.05, 2),
                   fillet_poly(rect(cx, 0.68, 0.3, 0.4), 0.03, 2), 0.0, 0.035, bev=0.01, steps=1, M=Ff)
    # pedal "toes"
    for k in range(5):
        x = -0.36 + 0.18 * k
        box(br, "twn_pipe", (0.1, 0.32, 0.05), loc=(x, D0 - 0.12, 0.08), M=R("X", -6))
    box(wd, "twn_walnut", (0.95, 0.38, 0.08), loc=(0, D0 - 0.12, 0.04))
    # keyboard shelf, cheeks, keys, name board (with felt strip)
    box(wd, "twn_walnut", (2 * W2 + 0.04, 0.42, 0.06), loc=(0, D0 - 0.08, 1.02))
    for sx in (-1, 1):
        prism(wd, "twn_walnut", [(D0 - 0.29, 1.05), (D0 + 0.3, 1.05), (D0 + 0.3, 1.42), (D0 - 0.05, 1.42),
                                 (D0 - 0.29, 1.16)], sx * 0.78, sx * 0.86, M=YZX)
    nw = 14
    kw = 1.52 / nw
    for i in range(nw):
        x = -0.76 + kw * (i + 0.5)
        box(keys, "twn_ivory", (kw - 0.008, 0.33, 0.035), loc=(x, D0 - 0.11, 1.07))
    for i in range(nw - 1):
        if i % 7 in (2, 6):
            continue
        x = -0.76 + kw * (i + 1)
        box(keys, "twn_ebony", (kw * 0.55, 0.2, 0.045), loc=(x, D0 - 0.04, 1.11))
    box(wd, "twn_walnut", (1.56, 0.08, 0.32), loc=(0, D0 + 0.1, 1.24))
    box(felt, "twn_felt", (1.54, 0.02, 0.03), loc=(0, D0 + 0.055, 1.105))
    # upper case (the face)
    zu0, zu1 = 1.38, 2.3
    box(wd, "twn_walnut", (2 * W2, D1 - D0 + 0.02, zu1 - zu0), loc=(0, (D0 + D1) / 2 - 0.01, (zu0 + zu1) / 2), divs=(4, 2, 3))
    Fu = F_front(D0 - 0.01)
    # cheek panels / brows / nose rosette
    ring_plate(wd, "twn_walnut", fillet_poly(rect(0, 1.84, 1.6, 0.84), 0.12, 3),
               fillet_poly(rect(0, 1.84, 1.48, 0.72), 0.08, 3), 0.0, 0.04, bev=0.012, steps=1, M=Fu)
    for sx in (-1, 1):
        pts = [Fu @ Vector((sx * (0.1 + 0.44 * t), 2.1 + 0.06 * math.sin(math.pi * t) + 0.02 * t, 0.05)) for t in np.linspace(0, 1, 8)]
        tube(wr, "twn_walnut", pts, 0.035, seg=8, radii=[0.022 + 0.022 * math.sin(math.pi * t) for t in np.linspace(0, 1, 8)])
    revolve(br, "twn_pipe", [(0.0, 0.0), (0.09, 0.0), (0.1, 0.02), (0.06, 0.045), (0.0, 0.055)], seg=14,
            M=Fu @ T(0, 1.63, 0.035))
    sh.gear(br, "twn_pipe", 0.075, 8, 0.02, M=Fu @ T(0, 1.63, 0.045))
    # the eyes: round sound holes, brass bezel, glowing amber with a fret rosette
    for sx in (-1, 1):
        ex, ez = sx * 0.34, 1.86
        ring_plate(br, "twn_pipe", circle2d(0.21, 24, cx=ex, cy=ez), circle2d(0.165, 24, cx=ex, cy=ez), 0.0, 0.07,
                   bev=0.015, steps=2, M=Fu)
        prism(eye, "glow_amber", circle2d(0.17, 24, cx=ex, cy=ez), -0.02, 0.012, M=Fu)
        for k in range(3):
            a = k * 60.0
            box(br, "twn_pipe", (0.32, 0.018, 0.018), loc=(ex, ez, 0.025), M=Fu @ T(ex, ez, 0) @ R("Z", a) @ T(-ex, -ez, 0))
        sh.gear(br, "twn_pipe", 0.05, 6, 0.02, M=Fu @ T(ex, ez, 0.03))
    # cornice
    revolve(wr, "twn_walnut", [(0.0, 0.0), (1.0, 0.0), (1.0, 0.04), (1.04, 0.07), (1.04, 0.12), (0.0, 0.12)], seg=4,
            M=T(0, (D0 + D1) / 2 - 0.01, zu1) @ R("Z", 45) @ S(W2 * 1.42 / 1.0 * 0.72, (D1 - D0) * 1.42 / 1.0 * 0.72, 1.0))
    # side volutes ("ears")
    for sx in (-1, 1):
        pts = []
        for i in range(18):
            t = i / 17
            a = math.pi * 2.2 * t
            rr = 0.2 * (1 - 0.7 * t)
            pts.append((sx * (W2 + 0.03), D0 + 0.2 + math.sin(a) * rr, 1.75 + math.cos(a) * rr))
        tube(wr, "twn_walnut", pts, 0.04, seg=8)
    # fan back board behind the pipes + wind chest
    angs = _pipe_angles()
    amax = math.radians(max(angs) + 6)
    C = OR_FAN_C

    def fan(u, v, w):
        a = -amax + 2 * amax * u
        r = 0.55 + (1.45 - 0.4 * (abs(a) / amax) ** 1.4) * v
        return Vector((C.x + r * math.sin(a), C.y + 0.18 + 0.05 * w, C.z + r * math.cos(a)))
    param_box(wd, "twn_walnut", fan, divs=(14, 2, 1))
    tube(br, "twn_pipe", [fan(u, 1.0, 0.0) + Vector((0, -0.01, 0)) for u in np.linspace(0, 1, 24)], 0.025, seg=6)

    def chest(u, v, w):
        a = -amax + 2 * amax * u
        r = 0.48 + 0.2 * w
        return Vector((C.x + r * math.sin(a), C.y - 0.15 + 0.3 * v, C.z + r * math.cos(a)))
    param_box(wd, "twn_walnut", chest, divs=(12, 1, 1))
    sh.gear(br, "twn_pipe", 0.22, 12, 0.05, hole=0.08, M=T(C.x, C.y + 0.14, C.z + 0.5) @ R("X", 90))
    # ---------- jaw (keyboard cover; pivot at the hinge, closes over the keys) ----------
    jk = Kit("jaw")
    jw = jk.part("wood", bevel=(0.01, 1, 40), smooth=40)
    jb = jk.part("brass", smooth=45)
    jf = jk.part("felt", smooth=40)
    # lower lip: a smiling board that drops forward (+rot X) to show the ivory "teeth" and a felt tongue
    xs = np.linspace(-0.78, 0.78, 13)
    top = [(x, 0.27 + 0.05 * (x / 0.78) ** 2) for x in xs]
    outline = [(-0.78, 0.0), (0.78, 0.0)] + top[::-1]
    prism(jw, "twn_walnut", outline, -0.02, 0.02, M=R("X", 90))
    inner = [(x * 0.95, z * 0.9) for x, z in ([(-0.78, 0.03), (0.78, 0.03)] + top[::-1])]
    prism(jf, "twn_felt", inner, -0.032, -0.02, M=R("X", 90))
    tube(jb, "twn_pipe", [(x, -0.025, z + 0.004) for x, z in top], 0.016, seg=6)
    tube(jb, "twn_pipe", [(-0.78, -0.025, 0.02), (0.78, -0.025, 0.02)], 0.018, seg=6)
    revolve(jb, "twn_pipe", [(0.0, 0.0), (0.05, 0.0), (0.04, 0.02), (0.0, 0.025)], seg=10, M=T(0, -0.02, 0.15) @ R("X", 90))
    for sx in (-1, 1):
        jb.cyl("twn_pipe", r=0.022, h=0.12, seg=8, loc=(sx * 0.6, 0, 0), rot=(0, 90, 0))
    jaw_built = jk.build_parts(root, loc=OR_HINGE)
    # ---------- pipes (one node each, pivot at the foot) ----------
    pipe_built = []
    tip_center = None
    for i, a in enumerate(angs):
        ar = math.radians(a)
        d = Vector((math.sin(ar), 0, math.cos(ar)))
        base = C + d * 0.62
        t = abs(a) / max(abs(x) for x in angs)
        top_r = (OR_TOP - C.z) - 0.45 * t ** 1.3
        L = top_r - 0.62
        rp = 0.072 - 0.022 * t
        pk = Kit(f"pipe_{i + 1:02d}")
        pb = pk.part("brass", smooth=40)
        pd = pk.part("dark", smooth=None, occluder=False)
        M = R("Y", a)                      # local +Z along the pipe
        foot = 0.2
        revolve(pb, "twn_pipe", [(0.0, -0.02), (0.022, -0.02), (rp * 0.95, foot), (rp, foot + 0.01), (rp, L - 0.02),
                                 (rp * 1.08, L - 0.01), (rp * 1.08, L), (rp * 0.85, L), (rp * 0.85, L - 0.06), (0.0, L - 0.06)],
                seg=14, M=M)
        # mouth: dark slit + brass upper lip (front = -Y)
        s_m = max(0.3, min(L - 0.35, (2.4 - base.z) / max(math.cos(ar), 0.3) + 0.06))
        if abs(base.x + math.sin(ar) * s_m) > 0.95:
            s_m = max(0.3, min(L - 0.35, L * 0.35))
        Mm = M @ T(0, -rp * 0.92, s_m) @ R("X", 90)
        box(pd, "twn_ebony", (rp * 1.0, 0.05, 0.015), M=Mm @ T(0, 0, 0.004))
        plate(pb, "twn_pipe", [(-rp * 0.55, 0.03), (rp * 0.55, 0.03), (rp * 0.4, 0.09), (0.0, 0.12), (-rp * 0.4, 0.09)],
              0.012, bev=0.004, steps=1, M=Mm)
        pipe_built.append(pk.build_parts(root, loc=tuple(base)))
        if i == 5:
            tip_center = (base + d * L, d)
    built_body = kit.build_parts(root)
    sh.bake_parts(built_body, jaw_built, *pipe_built, distance=0.35, samples=40, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.3, dark=0.82))
    body = kit.join_parts(built_body)
    jaw = jk.join_parts(jaw_built)
    for k_, b in enumerate(pipe_built):
        o = sh.join([o for o, _ in b], f"pipe_{k_ + 1:02d}")
    sh.tint_islands(body, {"twn_walnut"}, lo=0.85, hi=1.05, seed=4, streak=0.1, streak_freq=10)
    sh.tint_islands(jaw, {"twn_walnut"}, lo=0.9, hi=1.0, seed=6, streak=0.1, streak_freq=10)
    # tallest pipes are 6 and 7 (index 5/6): steam point above the centre between them
    empty("steam_point", parent=root, loc=(0.0, C.y, OR_TOP), size=0.15)
    return root


# ===========================================================================
# prop_chimney  (18 m, base r 1.6-1.75; iron door on the front -Y)
# ===========================================================================
CH_Z0, CH_COURSE, CH_SEG = 0.6, 0.3, 40


def _ch_r(z):
    return 1.6 - 0.25 * (z - CH_Z0) / (16.6 - CH_Z0)


def build_chimney():
    root = empty("prop_chimney", size=1.0)
    rng = random.Random(3)
    kit = Kit("prop_chimney_body")
    br = kit.part("brick", smooth=60)
    st = kit.part("stone", bevel=(0.03, 1, 40), smooth=40)
    ir = kit.part("iron", smooth=40)
    sm = kit.part("small", smooth=50, occluder=False)
    # base
    revolve(st, "stone_dark", [(0.0, 0.0), (1.78, 0.0), (1.78, 0.42), (1.7, 0.5), (1.66, CH_Z0 + 0.02), (0.0, CH_Z0 + 0.02)],
            seg=CH_SEG, M=I4)
    # shaft in brick courses (one ring of quads per course, cells ~0.25 m -> per-face brick pattern)
    zs = list(np.arange(CH_Z0, 16.6 + 1e-6, CH_COURSE))
    prof = [(_ch_r(z), z) for z in zs]
    # corbelled crown
    zc = zs[-1]
    for k, dr in enumerate((0.08, 0.16, 0.24)):
        prof += [(_ch_r(zc) + dr, zc + k * 0.3 + 0.001), (_ch_r(zc) + dr, zc + (k + 1) * 0.3)]
    ztop = 17.72
    prof += [(_ch_r(zc) + 0.2, ztop), (1.12, ztop), (1.12, ztop - 1.6), (0.0, ztop - 1.6)]
    revolve(br, "twn_soot_brick", prof, seg=CH_SEG, M=I4, phase=0.0)
    # iron cap ring at the top
    revolve(ir, "twn_iron", [(1.1, ztop - 0.04), (_ch_r(zc) + 0.27, ztop - 0.04), (_ch_r(zc) + 0.27, 17.92),
                             (_ch_r(zc) + 0.2, 18.0), (1.16, 18.0), (1.1, 17.95)], seg=CH_SEG, closed=True)
    # 4 iron bands with a bolted clamp each
    for z in (3.6, 7.6, 11.6, 15.0):
        r = _ch_r(z)
        revolve(ir, "twn_iron", [(r - 0.01, z - 0.11), (r + 0.045, z - 0.11), (r + 0.06, z - 0.09), (r + 0.06, z + 0.09),
                                 (r + 0.045, z + 0.11), (r - 0.01, z + 0.11)], seg=CH_SEG, closed=True)
        a = math.radians(rng.uniform(0, 360))
        n = Vector((math.cos(a), math.sin(a), 0))
        c = n * (r + 0.06) + Vector((0, 0, z))
        M = sh.frame(c, n, up=(0, 0, 1))
        box(ir, "twn_iron", (0.2, 0.26, 0.08), M=M @ T(0, 0, 0.03))
        for dz in (-0.07, 0.07):
            sh.bolt_hex(sm, "twn_iron", M @ Vector((0, dz, 0.07)), n, r=0.03, h=0.03)
    # door surround (brick arch) + iron door on the front (-Y)
    r0 = _ch_r(1.5)
    yf = -r0 + 0.02
    Fd = F_front(yf)
    arch = [(-0.55, CH_Z0)] + [(0.55 * math.cos(t), 1.75 + 0.55 * math.sin(t)) for t in np.linspace(0, math.pi, 9)] + [(-0.55, CH_Z0)]
    arch = [(0.55, CH_Z0)] + arch[1:-1] + [(-0.55, CH_Z0)]
    outer = [(x * 1.45, CH_Z0 + (z - CH_Z0) * 1.13) for x, z in arch]
    vous = kit.part("vous", bevel=(0.02, 1, 40), smooth=40)
    for k in range(9):
        t0 = math.pi * k / 9
        t1 = math.pi * (k + 1) / 9
        q = [(0.58 * math.cos(t0), 1.75 + 0.58 * math.sin(t0)), (0.86 * math.cos(t0), 1.75 + 0.86 * math.sin(t0)),
             (0.86 * math.cos(t1), 1.75 + 0.86 * math.sin(t1)), (0.58 * math.cos(t1), 1.75 + 0.58 * math.sin(t1))]
        q = [(x * 0.97 + (0.0 if True else 0), z) for x, z in q]
        prism(vous, "twn_soot_brick", q, -0.3, 0.12, M=Fd)
    for sx in (-1, 1):
        for k in range(4):
            prism(vous, "twn_soot_brick", rect(sx * 0.72, CH_Z0 + 0.15 + 0.3 * k, 0.28 if k % 2 else 0.36, 0.27), -0.3, 0.1, M=Fd)
    # iron door (arched plate), straps, rivets, handle
    door = [(0.5, CH_Z0 + 0.02)] + [(0.5 * math.cos(t), 1.75 + 0.5 * math.sin(t)) for t in np.linspace(0, math.pi, 12)] + \
           [(-0.5, CH_Z0 + 0.02)]
    prism(ir, "twn_iron", door, -0.3, 0.04, M=Fd)
    for zz in (0.95, 1.7):
        box(ir, "twn_iron", (1.0, 0.1, 0.03), loc=(0, zz, 0.055), M=Fd)
        for xx in np.linspace(-0.4, 0.4, 5):
            rivet(sm, "twn_iron", Fd @ Vector((xx, zz, 0.07)), Fd.to_3x3() @ Vector((0, 0, 1)), r=0.022, h=0.016, seg=5)
    sh.wheel if False else None
    ir.torus("twn_iron", R=0.09, r=0.018, seg=12, seg2=4, loc=tuple(Fd @ Vector((0.3, 1.3, 0.1))), rot=(90, 0, 0))
    box(st, "stone_dark", (1.4, 0.5, 0.2), loc=(0, yf - 0.25, 0.1))
    # iron ladder rungs up the back (+Y) + lightning conductor (copper strip, front-right)
    for z in np.arange(2.2, 17.4, 0.45):
        r = _ch_r(min(z, 16.6))
        tube(sm, "twn_iron", [(-0.26, r - 0.02, z), (-0.26, r + 0.2, z), (0.26, r + 0.2, z), (0.26, r - 0.02, z)],
             0.028, seg=5)
    a = math.radians(125)
    pts = []
    for z in np.linspace(CH_Z0, 16.6, 12):
        r = _ch_r(z) + 0.012
        pts.append((r * math.cos(a), r * math.sin(a), z))
    sh.sweep_band(sm, "copper", pts, [(math.cos(a), math.sin(a), 0)] * len(pts), 0.035, 0.01)
    rr = _ch_r(16.6) + 0.27
    tube(sm, "copper", [(rr * math.cos(a), rr * math.sin(a), 16.6), (rr * math.cos(a), rr * math.sin(a), 18.6)], 0.025, seg=6)
    built = kit.build_parts(root)

    def soot(p, n):
        t = smoothstep(7.0, 17.6, p.z) ** 0.8
        st_ = 0.55 + 0.45 * smoothstep(-0.3, 0.4, fbm(Vector((p.x * 2.2, p.y * 2.2, p.z * 0.08)), seed=4))
        k = (1.0 - 0.7 * t * st_) * (0.72 + 0.28 * smoothstep(0.0, 1.2, p.z))
        if p.z > 15.9 and (p.x * p.x + p.y * p.y) < 1.13 ** 2:
            k *= 0.25
        return (k, k * 0.97, k * 0.95)
    sh.bake_parts(built, distance=1.2, samples=40, strength=0.8, floor=0.3, tint=soot)
    obj = kit.join_parts(built)

    def bricks(c, nn):
        if abs(nn.z) > 0.6:
            return (0.9, 0.9, 0.9)
        a = math.atan2(c.y, c.x)
        j = math.floor((a % (2 * math.pi)) / (2 * math.pi / CH_SEG))
        course = math.floor((c.z - CH_Z0) / CH_COURSE)
        b = (j + course % 2) // 2
        t = _h(11, course, b, j if c.z < 2.6 and c.y < -1.0 else 0)
        k = 0.68 + 0.4 * t
        if course in (44, 45, 47):                     # decorative dark header courses below the crown
            k *= 0.62 if (b + course) % 2 else 0.8
        if _h(12, course, b) < 0.08:
            k *= 0.7
        w = 1.0 + 0.08 * (_h(13, course, b) - 0.5)
        return (k * w, k, k / w)
    face_tint(obj, {"twn_soot_brick"}, bricks)
    sh.tint_islands(obj, {"stone_dark"}, lo=0.85, hi=1.0, seed=2)
    empty("steam_point", parent=root, loc=(0, 0, 18.0), size=0.5)
    return root


# ===========================================================================
# prop_drive_shaft  (~10 m floor-to-ceiling; child rotor spins around local Z; sockets on the front -Y)
# ===========================================================================
DS_TOP = 10.0


def _gear_spokes(part, mat, r, teeth, depth, z, hub, rim, spokes, phase=0.0, tooth=None):
    sh.gear(part, mat, r, teeth, depth, tooth=tooth, hole=0.5, M=T(0, 0, z), hub=hub, spokes=spokes, rim=rim, phase=phase)


def build_drive_shaft():
    root = empty("prop_drive_shaft", size=1.0)
    rng = random.Random(14)
    kit = Kit("prop_drive_shaft_body")
    ir = kit.part("iron", bevel=(0.025, 1, 40), smooth=40)
    irr = kit.part("iron_round", smooth=40)
    br = kit.part("brass", smooth=40)
    sm = kit.part("small", smooth=50, occluder=False)
    gl = kit.part("glow", flat=True, occluder=False)
    # floor base: octagonal iron plinth, panels, brass collar
    revolve(ir, "twn_black_iron", [(0.0, 0.0), (1.95, 0.0), (1.95, 0.28), (1.75, 0.32), (1.72, 1.15), (1.5, 1.22),
                                   (0.0, 1.22)], seg=8, phase=math.pi / 8)
    for k in range(8):
        a = 2 * math.pi * k / 8
        n = Vector((math.cos(a), math.sin(a), 0))
        ri = 1.72 * math.cos(math.pi / 8)
        Mk = sh.frame(n * ri + Vector((0, 0, 0.74)), n, up=(0, 0, 1))
        ring_plate(irr, "twn_black_iron", rect(0, 0, 1.0, 0.6), rect(0, 0, 0.84, 0.44), 0.0, 0.04, bev=0.01, steps=1, M=Mk)
        for (x, y) in ((-0.46, -0.26), (0.46, -0.26), (-0.46, 0.26), (0.46, 0.26)):
            rivet(sm, "brass", Mk @ Vector((x, y, 0.04)), n, r=0.025, h=0.018, seg=5)
    revolve(br, "brass", [(0.0, 1.2), (1.4, 1.2), (1.4, 1.3), (1.32, 1.36), (1.32, 1.62), (1.22, 1.7), (0.0, 1.7)], seg=40)
    # ceiling bearing + ceiling plate
    revolve(br, "brass", [(0.0, 8.9), (1.22, 8.9), (1.32, 8.98), (1.32, 9.25), (1.4, 9.3), (0.0, 9.3)], seg=40)
    revolve(ir, "twn_black_iron", [(0.0, 9.3), (1.5, 9.3), (1.55, 9.4), (1.55, 9.62), (2.1, 9.68), (2.1, DS_TOP), (0.0, DS_TOP)],
            seg=8, phase=math.pi / 8)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        n = Vector((math.cos(a), math.sin(a), 0))
        sh.bolt_hex(sm, "brass", n * 1.62 + Vector((0, 0, 9.6)), Vector((0, 0, -1)), r=0.05, h=0.05)
    # ---------- sockets on the front ----------
    # crystal cradle (left, x -0.8): iron pedestal, brass claws, glowing violet crystal (child socket_crystal)
    cx, cy = -0.8, -2.15
    revolve(ir, "twn_black_iron", [(0.0, 0.0), (0.42, 0.0), (0.42, 0.12), (0.26, 0.2), (0.2, 0.75), (0.3, 0.85),
                                   (0.3, 0.95), (0.0, 0.95)], seg=8, M=T(cx, cy, 0), phase=math.pi / 8)
    revolve(br, "brass", [(0.0, 0.94), (0.3, 0.94), (0.33, 0.99), (0.26, 1.03), (0.0, 1.03)], seg=20, M=T(cx, cy, 0))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [Vector((cx, cy, 1.0)) + d * (0.22 + 0.06 * math.sin(t * 1.6)) + Vector((0, 0, 0.42 * t)) - d * (0.12 * t * t)
               for t in np.linspace(0, 1, 6)]
        tube(br, "brass", pts, 0.035, seg=6, radii=[0.04, 0.038, 0.034, 0.03, 0.025, 0.012])
    gl.torus("glow_twn_violet", R=0.2, r=0.018, seg=16, seg2=4, loc=(cx, cy, 1.05))
    # brass feed pipe from the cradle into the plinth
    tube(br, "brass", [(cx, cy + 0.2, 0.55), (cx, cy + 0.55, 0.55), (cx * 0.9, -1.6, 0.6)], 0.07, seg=8)
    # valve flange (right, x +0.8): pedestal, stub pipe, tilted bolted flange (empty socket_valve at its face)
    vx, vy = 0.8, -2.15
    revolve(ir, "twn_black_iron", [(0.0, 0.0), (0.42, 0.0), (0.42, 0.12), (0.26, 0.2), (0.2, 0.7), (0.0, 0.7)],
            seg=8, M=T(vx, vy, 0), phase=math.pi / 8)
    Mv = T(vx, vy, 0.95) @ R("X", 35)
    revolve(irr, "twn_black_iron", [(0.0, -0.4), (0.16, -0.4), (0.16, -0.05), (0.0, -0.05)], seg=16, M=Mv)
    revolve(irr, "twn_black_iron", [(0.12, -0.08), (0.36, -0.08), (0.38, -0.06), (0.38, 0.02), (0.36, 0.04), (0.12, 0.04),
                                    (0.12, -0.08)], seg=24, M=Mv, closed=True)
    revolve(br, "brass", [(0.0, -0.02), (0.12, -0.02), (0.12, 0.0), (0.0, 0.0)], seg=16, M=Mv)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        p_ = Mv @ Vector((0.29 * math.cos(a), 0.29 * math.sin(a), 0.04))
        sh.bolt_hex(sm, "brass", p_, Mv.to_3x3() @ Vector((0, 0, 1)), r=0.032, h=0.03)
    tube(br, "brass", [(vx, vy + 0.15, 0.62), (vx, vy + 0.55, 0.62), (vx * 0.9, -1.6, 0.65)], 0.07, seg=8)
    gl.torus("glow_twn_violet", R=0.24, r=0.012, seg=20, seg2=4, loc=tuple(Mv @ Vector((0, 0, 0.045))), rot=(35, 0, 0))
    # crystal (separate node so the game can hide it until it is installed)
    ck = Kit("socket_crystal")
    cg = ck.part("gem", flat=True, occluder=False)
    sh.facet_gem(cg, None) if False else None
    from env_helpers import shard, bipyramid
    bipyramid(cg, "glow_twn_violet", r=0.2, up=0.46, down=0.24, seg=6)
    crystal_built = ck.build_parts(root, loc=(cx, cy, 1.36))
    # ---------- rotor: shaft + 2 gears + collars + keys (spins around Z) ----------
    rk = Kit("rotor")
    rb = rk.part("brass", smooth=40)
    ri = rk.part("iron", smooth=40)
    rs = rk.part("small", smooth=50, occluder=False)
    revolve(rb, "brass", [(1.0, 1.65), (1.0, 8.95)], seg=36, cap0=False, cap1=False)
    for z in (2.2, 5.0, 8.3):
        revolve(ri, "twn_black_iron", [(0.98, z - 0.16), (1.1, z - 0.16), (1.13, z - 0.12), (1.13, z + 0.12), (1.1, z + 0.16),
                                       (0.98, z + 0.16)], seg=36, closed=True)
        for k in range(12):
            a = 2 * math.pi * k / 12
            n = Vector((math.cos(a), math.sin(a), 0))
            sh.bolt_hex(rs, "brass", n * 1.13 + Vector((0, 0, z)), n, r=0.035, h=0.03)
    # 4 iron key strips along the shaft so the rotation reads
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        n = Vector((math.cos(a), math.sin(a), 0))
        for (z0, z1) in ((1.7, 2.04), (2.36, 4.84), (5.16, 8.14)):
            pts = [n * 1.0 + Vector((0, 0, z)) for z in (z0, z1)]
            sh.sweep_band(ri, "twn_black_iron", pts, [n, n], 0.16, 0.035)
    # gear 1 (brass, big) and gear 2 (iron with brass hub)
    sh.gear(rb, "brass", 2.35, 36, 0.36, tooth=0.22, hole=0.5, spokes=8, hub=1.25, rim=0.32, spoke_w=0.3, M=T(0, 0, 3.5))
    revolve(rb, "brass", [(1.0, 3.45), (1.96, 3.45), (1.96, 3.55), (1.0, 3.55)], seg=36, closed=True)
    revolve(ri, "twn_black_iron", [(1.0, 3.2), (1.32, 3.2), (1.36, 3.26), (1.36, 3.74), (1.32, 3.8), (1.0, 3.8)], seg=36, closed=True)
    sh.gear(ri, "twn_black_iron", 1.95, 30, 0.32, tooth=0.2, hole=0.5, spokes=6, hub=1.2, rim=0.28, spoke_w=0.28,
            M=T(0, 0, 6.6) @ R("Z", 10))
    revolve(ri, "twn_black_iron", [(1.0, 6.56), (1.6, 6.56), (1.6, 6.64), (1.0, 6.64)], seg=36, closed=True)
    revolve(rb, "brass", [(1.0, 6.36), (1.28, 6.36), (1.32, 6.42), (1.32, 6.78), (1.28, 6.84), (1.0, 6.84)], seg=36, closed=True)
    for z, rr_, nb in ((3.5, 1.85, 24), (6.6, 1.5, 20)):
        for k in range(nb):
            a = 2 * math.pi * k / nb
            for sz in (-1, 1):
                rivet(rs, "brass" if z > 5 else "twn_black_iron", (rr_ * math.cos(a), rr_ * math.sin(a), z + sz * 0.16 + sz * 0.0),
                      (0, 0, sz), r=0.03, h=0.02, seg=5)
    rotor_built = rk.build_parts(root, loc=(0, 0, 0))
    body_built = kit.build_parts(root)
    sh.bake_parts(body_built, rotor_built, crystal_built, distance=0.8, samples=40, strength=0.85, floor=0.3,
                  tint=sh.ground_grime(0.0, 0.5, dark=0.85))
    kit.join_parts(body_built)
    rk.join_parts(rotor_built)
    ck.join_parts(crystal_built)
    empty("socket_valve", parent=root, loc=tuple(Mv @ Vector((0, 0, 0.04))), size=0.2)
    return root


# name, builder, preview kwargs (render_hp kwargs + optional views)
PROPS = [
    ("prop_house", build_house, {}),
    ("prop_locomotive", build_locomotive, dict(views=(("", 55, 16), ("_back", 235, 22)))),
    ("prop_nail_board", build_nail_board, dict(views=(("", 25, 12), ("_back", 210, 15)))),
    ("prop_organ", build_organ, dict(views=(("", 25, 10), ("_back", 200, 20)))),
    ("prop_chimney", build_chimney, dict(dist_k=3.0, views=(("", 30, 10), ("_back", 200, 30)))),
    ("prop_drive_shaft", build_drive_shaft, dict(views=(("", 30, 10), ("_back", 200, 15), ("_high", 20, 40)))),
]

BUDGET = {
    "prop_house": 12000,
    "prop_locomotive": 25000,
    "prop_nail_board": 25000,
    "prop_organ": 25000,
    "prop_chimney": 25000,
    "prop_drive_shaft": 25000,
}
