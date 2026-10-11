"""Cog Rat — weak clockwork rat enemy (~0.45 m tall, ~0.8 m long). Exports public/models/cograt.glb.

Skeleton (RIG_SPEC.md), armature object 'root':
  body (root bone) > head > {ear_L, ear_R}
                   > tail_1 > tail_2 > tail_3 > tail_4
                   > leg_FL, leg_FR, leg_BL, leg_BR
  rigid attachment: key (bone-parented to body, spins around its local Z)
Faces -Y (head toward -Y), L = +X. Tail extends +Y curving up; tail joints sit on the iron rod
between the beads, so the beads stay rigid and only the rod/bead tips blend at each joint.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from char_helpers import *
from rig_helpers import rig_from_parts
from creature_rig_helpers import vsub, pose_views

reset_scene()
root = empty("root")

BODY_Z = 0.25

# ---- body ---------------------------------------------------------------------
p = Part("body")
# copper barrel body, lofted along Y (rot X=-90 maps local Z -> +Y; section depth -> -Z... use (w, d) symmetric)
loft(p, "copper", [(-0.27, 0.12, 0.12), (-0.20, 0.26, 0.24), (-0.02, 0.34, 0.29), (0.14, 0.36, 0.30),
                   (0.25, 0.26, 0.22), (0.29, 0.10, 0.10)], shape=8, rot=(-90, 0, 0))
for y in (-0.10, 0.06):
    loft(p, "brass", [(y, 0.355, 0.30), (y + 0.035, 0.36, 0.305)], shape=8, rot=(-90, 0, 0))
p.box("iron", size=(0.20, 0.36, 0.05), loc=(0, 0.0, -0.13))                       # belly plate
for x in (-0.08, 0.08):
    p.box("brass_dark", size=(0.025, 0.025, 0.025), loc=(x, 0.18, 0.11))
p.cyl("brass_dark", r=0.05, h=0.03, seg=6, loc=(0, 0.05, 0.145))                   # key socket
for s in (1, -1):
    p.sphere("copper", r=0.10, seg=6, rings=4, loc=(s * 0.14, 0.13, -0.03), scale=(0.6, 1.0, 1.0))  # haunches
body = p.build(root, loc=(0, 0, BODY_Z))

# ---- head (extends toward -Y from the neck pivot) ----------------------------------
p = Part("head")
loft(p, "copper", [(0.0, 0.20, 0.18), (0.08, 0.22, 0.19, 0, 0.01), (0.20, 0.11, 0.10, 0, -0.01),
                   (0.27, 0.04, 0.04, 0, -0.015)], shape=8, rot=(90, 0, 0))
p.ico("black", r=0.03, loc=(0, -0.275, -0.012))                                     # nose
for s in (1, -1):
    gem(p, "glow_red", r=0.036, up=0.024, seg=6, loc=(s * 0.088, -0.10, 0.045), rot=(0, s * 70, 0))  # eyes
    p.cyl("brass", r=0.048, h=0.02, seg=6, loc=(s * 0.082, -0.10, 0.045), rot=(0, s * 70, 0))
    # whiskers
    p.box("brass_dark", size=(0.12, 0.006, 0.006), loc=(s * 0.09, -0.22, -0.0), rot=(0, s * 10, s * 15))
    p.box("brass_dark", size=(0.12, 0.006, 0.006), loc=(s * 0.09, -0.22, -0.02), rot=(0, -s * 10, s * 15))
p.box("white", size=(0.04, 0.015, 0.03), loc=(0, -0.235, -0.045))                   # buck teeth
p.box("iron", size=(0.10, 0.10, 0.03), loc=(0, -0.13, -0.075))                      # jaw plate
head = p.build(body, loc=(0, -0.22, 0.04))

# ---- ears (big round brass discs, pivot at the ear base on top of the head) --------
for s, side in ((1, "L"), (-1, "R")):
    piv = (s * 0.07, -0.025, 0.075)                       # ear base in head space
    p = Part("ear_" + side)
    p.cyl("brass", r=0.075, h=0.022, seg=8, loc=vsub((s * 0.09, -0.01, 0.14), piv), rot=(80, 0, s * 25))
    p.cyl("copper", r=0.05, h=0.024, seg=8, loc=vsub((s * 0.088, -0.014, 0.14), piv), rot=(80, 0, s * 25))
    p.build(head, loc=piv)

# ---- tail: 4-bone chain (segmented, extends +Y curving up) --------------------------
# Same curve, beads and tip gear as before; joints at rod points between beads.
TAIL_PIVOT = (0, 0.27, 0.0)                                 # tail base in body space
pts = [(0, 0.0, 0.0), (0, 0.10, -0.01), (0, 0.20, 0.01), (0, 0.29, 0.07), (0, 0.35, 0.16), (0, 0.37, 0.26),
       (0, 0.35, 0.34)]
JOINTS = [0, 2, 3, 4]                                       # pts index where tail_1..tail_4 start
parent, parent_piv = body, None
for k, a in enumerate(JOINTS):
    b = JOINTS[k + 1] if k + 1 < len(JOINTS) else len(pts) - 1
    piv = pts[a]
    p = Part(f"tail_{k + 1}")
    tube(p, "iron", [vsub(q, piv) for q in pts[a:b + 1]], r=0.012, seg=4)
    for i in range(a, b):
        A, B = Vector(pts[i]), Vector(pts[i + 1])
        m = (A + B) / 2
        d = (B - A).normalized()
        ang = math.degrees(math.atan2(d.z, d.y))
        r = 0.042 - i * 0.004
        gem(p, "copper" if i % 2 == 0 else "brass", r=r, up=0.022, down=0.022, seg=6, mid=0.05,
            loc=vsub(tuple(m), piv), rot=(-90 + ang, 0, 0))
    if k == len(JOINTS) - 1:
        sgear(p, "brass", r=0.045, teeth=6, thick=0.015, loc=vsub((0, 0.345, 0.37), piv), rot=(0, 90, 0))
    loc = TAIL_PIVOT if parent_piv is None else vsub(piv, parent_piv)
    parent = p.build(parent, loc=loc)
    parent_piv = piv

# ---- legs ---------------------------------------------------------------------
def make_leg(name, x, y, back):
    p = Part(name)
    top = -0.07
    h = BODY_Z + top               # pivot height above ground
    if back:
        p.sphere("copper", r=0.065, seg=6, rings=4, loc=(0, 0.0, -0.02), scale=(0.7, 1.0, 1.0))
    else:
        p.sphere("copper", r=0.05, seg=6, rings=4, loc=(0, 0.0, -0.01), scale=(0.8, 1.0, 1.0))
    p.cyl("iron", r=0.018, h=h - 0.03, seg=4, loc=(0, 0.0, -(h - 0.03) / 2 - 0.01))
    p.cyl("brass_dark", r=0.026, h=0.03, seg=6, loc=(0, 0.0, -h * 0.55))
    # paw (points -Y)
    loft(p, "brass", [(-h, 0.07, 0.10, 0, -0.02), (-h + 0.035, 0.06, 0.08, 0, -0.01)], shape="oct")
    for dx in (-0.022, 0.0, 0.022):
        p.box("brass_dark", size=(0.014, 0.03, 0.02), loc=(dx, -0.075, -h + 0.01))
    return p.build(body, loc=(x, y, top))

make_leg("leg_FL", 0.12, -0.13, False)
make_leg("leg_FR", -0.12, -0.13, False)
make_leg("leg_BL", 0.15, 0.13, True)
make_leg("leg_BR", -0.15, 0.13, True)

# ---- wind-up key (rigid attachment, spins around local Z) ------------------------------
p = Part("key")
p.cyl("brass", r=0.016, h=0.10, seg=6, loc=(0, 0, 0.05))
p.cyl("brass_dark", r=0.03, h=0.02, seg=6, loc=(0, 0, 0.03))
p.box("brass", size=(0.04, 0.03, 0.05), loc=(0, 0, 0.10))
for s in (1, -1):
    p.torus("brass", R=0.042, r=0.014, seg=8, seg2=3, loc=(s * 0.055, 0, 0.12), rot=(90, 0, 0))
key = p.build(body, loc=(0, 0.05, 0.15))

# ---- rig + export + previews ------------------------------------------------------------
TAIL_SMOOTH = 0.035
arm = rig_from_parts(root, rigid={"key"},
                     smooth={"tail_2": TAIL_SMOOTH, "tail_3": TAIL_SMOOTH, "tail_4": TAIL_SMOOTH},
                     skin_name="cograt_skin")
finish("cograt")          # tri report + export_glb("cograt") + rest-pose previews

# deformation test: head turned, ears flicked, legs mid-stride, tail curled sideways & up
COGRAT_TEST_POSE = {
    "head": [("Z", 25), ("X", -10)],
    "ear_L": [("X", -30), ("Y", 20)],
    "ear_R": [("X", 20), ("Y", -15)],
    "leg_FL": [("X", -30)],
    "leg_BR": [("X", -20)],
    "leg_FR": [("X", 20)],
    "leg_BL": [("X", 30)],
    "tail_1": [("Z", -25), ("X", 5)],
    "tail_2": [("Z", -25), ("X", 10)],
    "tail_3": [("Y", 25)],
    "tail_4": [("Y", 35), ("X", 15)],
}
pose_views(arm, "cograt", COGRAT_TEST_POSE, views=(("", 35, 18), ("_back", 160, 40)))
