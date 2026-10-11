"""Verify exported character GLBs contain the node names the game animates.

Standard library only. Usage (from anywhere):
    python tools/blender/check_glb.py [name ...]      # default: all 8 characters/enemies
Exit code 1 if a file is missing, unparsable, or lacks a required node.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.normpath(os.path.join(HERE, "..", "..", "public", "models"))

# --- Rigged models (RIG_SPEC.md): joints of the skin + rigid attachments -----------------
HUMANOID_BONES = ["hips", "torso", "head", "arm_L", "forearm_L", "arm_R", "forearm_R",
                  "leg_L", "shin_L", "leg_R", "shin_R"]
RIGGED = {
    "kai": {"bones": HUMANOID_BONES + ["coat_L_1", "coat_L_2", "coat_R_1", "coat_R_2", "scarf_1", "scarf_2"],
            "rigid": {"weapon": "forearm_R", "steam_point": "torso"}},
    "lyra": {"bones": HUMANOID_BONES + ["skirt_F_1", "skirt_F_2", "skirt_B_1", "skirt_B_2", "skirt_L_1",
                                        "skirt_R_1", "hat_1"],
             "rigid": {"weapon": "forearm_R", "staff_tip": "weapon"},
             "any_of": [["hair_L_1", "hair_R_1", "hair_B_1"]]},
    "knight": {"bones": HUMANOID_BONES + ["tabard_F_1", "tabard_F_2"],
               "rigid": {"weapon": "forearm_R", "shield": "forearm_L", "key": "torso"}},
    # chapter 1 NPCs (model_npc.py) share the hero skeleton
    "npc_marta": {"bones": HUMANOID_BONES + ["coat_FL_1", "coat_FR_1", "coat_L_1", "coat_R_1"], "rigid": {"weapon": "forearm_R"}},
    "npc_bail": {"bones": HUMANOID_BONES + ["coat_FL_1", "coat_FR_1", "coat_L_1", "coat_R_1"], "rigid": {"weapon": "forearm_R"}},
    "npc_poppy": {"bones": HUMANOID_BONES + ["scarf_1", "scarf_2"], "rigid": {"weapon": "forearm_R"}},
    "npc_shopkeeper": {"bones": HUMANOID_BONES + ["tabard_F_1", "tabard_F_2"], "rigid": {"weapon": "forearm_R"}},
    "grand_carillon": {"bones": HUMANOID_BONES + ["needle", "brow_L", "brow_R", "tail_1", "tail_2", "tail_3"], "rigid": {"steam_point": None}},
    "strongbox_tortoise": {"bones": ["body", "head", "horn", "shell_L", "shell_R", "dial"] +
                                    [f"leg_{p}{s}{seg}" for p in "FMB" for s in "LR" for seg in ("", "_2")],
                           "rigid": {"steam_point": "body"}},
    "golem": {"bones": HUMANOID_BONES,
              "rigid": {"steam_point": None}},
    "cograt": {"bones": ["body", "head", "ear_L", "ear_R", "tail_1", "tail_2", "tail_3", "tail_4",
                         "leg_FL", "leg_FR", "leg_BL", "leg_BR"],
               "rigid": {"key": "body"}},
    "beetle": {"bones": ["body", "head", "horn", "shell_L", "shell_R"] +
                        [f"leg_{p}{s}{seg}" for p in "FMB" for s in "LR" for seg in ("", "_2")],
               "rigid": {}},
}
# expected bone parents (child -> parent) for the skeleton
BONE_PARENTS = {
    "_humanoid": {"torso": "hips", "head": "torso", "arm_L": "torso", "arm_R": "torso",
                  "forearm_L": "arm_L", "forearm_R": "arm_R", "leg_L": "hips", "leg_R": "hips",
                  "shin_L": "leg_L", "shin_R": "leg_R", "hips": "root"},
    "cograt": {"head": "body", "tail_1": "body", "tail_2": "tail_1", "tail_3": "tail_2", "tail_4": "tail_3",
               "ear_L": "head", "ear_R": "head", "body": "root"},
    "beetle": {"head": "body", "horn": "head", "shell_L": "body", "shell_R": "body", "body": "root",
               "leg_FL_2": "leg_FL", "leg_BR_2": "leg_BR"},
}

# --- Unrigged (rigid part) models ----------------------------------------------------------
REQUIRED = {
    "slime": ["root", "body", "valve", "eye_L", "eye_R"],
    "bellows_toad": ["root", "body", "valve", "eye_L", "eye_R"],
    "prism_moth": ["root", "lantern", "flame", "ring_A", "wing_L", "wing_R"],
    "wisp": ["root", "lantern", "flame", "ring_A", "ring_B", "wing_L", "wing_R"],
}
PARENTS = {
    "slime": {"valve": "body", "eye_L": "body", "eye_R": "body", "body": "root"},
    "wisp": {"lantern": "root", "flame": "lantern", "ring_A": "lantern", "wing_L": "lantern",
             "wing_R": "lantern"},
}
# heroes (low-poly) get a little extra for the round elbow/knee joint caps;
# enemies use the hi-poly "medium" tier budgets (see ASSET_SPEC.md "Build quality")
BUDGET = {"prism_moth": 10000, "bellows_toad": 8000, "strongbox_tortoise": 25000, "grand_carillon": 30000, "kai": 3100, "lyra": 3100, "npc_marta": 3100, "npc_bail": 3100, "npc_poppy": 3100, "npc_shopkeeper": 3100, "cograt": 10000, "slime": 8000, "wisp": 10000, "beetle": 20000,
          "knight": 25000, "golem": 30000}
ALL = ["kai", "lyra", "knight", "cograt", "slime", "beetle", "wisp", "golem",
       "prism_moth", "bellows_toad", "strongbox_tortoise", "grand_carillon", "npc_marta", "npc_bail", "npc_poppy", "npc_shopkeeper"]
# animated nodes whose rest rotation must be identity (unrigged models only)
NO_ROT_EXEMPT = {"ring_B_tilt"}


def read_glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError("not a GLB file")
    clen, ctype = struct.unpack_from("<I4s", data, 12)
    if ctype != b"JSON":
        raise ValueError("first chunk is not JSON")
    return json.loads(data[20:20 + clen].decode("utf-8"))


def tri_count(gltf):
    tris = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            if "indices" in prim:
                tris += gltf["accessors"][prim["indices"]]["count"] // 3
            else:
                tris += gltf["accessors"][prim["attributes"]["POSITION"]]["count"] // 3
    return tris


def check(name):
    path = os.path.join(MODELS, name + ".glb")
    if not os.path.exists(path):
        return False, f"{name}: MISSING {path}"
    g = read_glb_json(path)
    nodes = g.get("nodes", [])
    names = [n.get("name", "") for n in nodes]
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[names[c]] = names[i]
    scene = g["scenes"][g.get("scene", 0)]
    top = [names[i] for i in scene["nodes"]]
    problems = []
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        problems.append("duplicate names: " + ", ".join(dupes))
    if top != ["root"]:
        problems.append(f"top-level nodes should be ['root'], got {top}")

    if name in RIGGED:
        spec = RIGGED[name]
        skins = g.get("skins", [])
        if len(skins) != 1:
            problems.append(f"expected exactly 1 skin, got {len(skins)}")
        joints = {names[j] for s in skins for j in s["joints"]}
        missing = [b for b in spec["bones"] if b not in joints]
        if missing:
            problems.append("missing joints: " + ", ".join(missing))
        for group in spec.get("any_of", []):
            if not any(b in joints for b in group):
                problems.append("need at least one of joints: " + ", ".join(group))
        for obj, par in spec["rigid"].items():
            if obj not in names:
                problems.append(f"missing rigid attachment {obj}")
            elif obj in joints:
                problems.append(f"{obj} must be a rigid attachment, not a skinned joint")
            elif par and parent.get(obj) != par:
                problems.append(f"{obj} parent is {parent.get(obj)!r}, expected {par!r}")
        humanoid = "hips" in spec["bones"]
        exp = dict(BONE_PARENTS["_humanoid"]) if humanoid else dict(BONE_PARENTS.get(name, {}))
        for child, par in exp.items():
            if child in names and parent.get(child) != par:
                problems.append(f"bone {child} parent is {parent.get(child)!r}, expected {par!r}")
        kind = f"rig {len(joints)} joints"
    else:
        missing = [r for r in REQUIRED[name] if r not in names]
        if missing:
            problems.append("missing nodes: " + ", ".join(missing))
        for child, par in PARENTS.get(name, {}).items():
            if parent.get(child) != par:
                problems.append(f"{child} parent is {parent.get(child)!r}, expected {par!r}")
        for n in nodes:
            r = n.get("rotation")
            if r and n.get("name") not in NO_ROT_EXEMPT:
                if any(abs(a - b) > 1e-4 for a, b in zip(r, (0, 0, 0, 1))):
                    problems.append(f"{n.get('name')} has non-identity rest rotation {r}")
        kind = "rigid parts"
    tris = tri_count(g)
    budget = BUDGET.get(name, 3000)
    if tris > budget:
        problems.append(f"{tris} tris > {budget} budget")
    status = "OK  " if not problems else "FAIL"
    msg = f"{status} {name:7s} {tris:5d} tris  {kind}  nodes: {', '.join(names)}"
    for pr in problems:
        msg += f"\n       - {pr}"
    return not problems, msg


def main():
    targets = sys.argv[1:] or ALL
    # model_npc.py builds all four NPCs in one run
    targets = [t for n in targets for t in (["npc_marta", "npc_bail", "npc_poppy", "npc_shopkeeper"] if n == "npc" else [n])]
    ok_all = True
    for t in targets:
        try:
            ok, msg = check(t)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, f"FAIL {t}: {e}"
        ok_all &= ok
        print(msg)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
