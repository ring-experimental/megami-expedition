"""Verify props.glb / arena.glb node structure (standard library only).

    python tools/blender/verify_env.py
Exit code 0 = all checks passed.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.normpath(os.path.join(HERE, "..", "..", "public", "models"))

PROPS = ["prop_lamp", "prop_pipe", "prop_pipe_arch", "prop_vent", "prop_crystal", "prop_rock_a", "prop_rock_b",
         "prop_tree", "prop_tree_b", "prop_bush", "prop_gear_monument", "prop_clocktower", "prop_airship",
         "prop_rest", "prop_chest", "prop_fence", "prop_crate", "prop_barrel", "prop_signpost"]
ANIMATED = {"propeller": "prop_airship", "crystal": "prop_rest", "lid": "prop_chest"}
# hi-poly "medium" tier budgets (2026-10-11) — keep in sync with BUDGET in props_*.py
BUDGET = {"prop_tree": 5000, "prop_tree_b": 5000, "prop_bush": 1000, "prop_rock_a": 2500, "prop_rock_b": 2500,
          "prop_crystal": 6000, "prop_lamp": 6000, "prop_pipe": 6000, "prop_pipe_arch": 8000, "prop_vent": 4000,
          "prop_fence": 4000, "prop_gear_monument": 15000, "prop_rest": 12000, "prop_chest": 6000,
          "prop_crate": 3000, "prop_barrel": 4000, "prop_signpost": 4000, "prop_clocktower": 40000,
          "prop_airship": 40000}
ARENA_BUDGET = 60000

errors = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def load_gltf(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError(f"{path}: not a GLB")
    chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON":
        raise ValueError(f"{path}: first chunk is not JSON")
    return json.loads(data[20:20 + chunk_len].decode("utf-8")), version, length


def tri_count(gltf, mesh_idx):
    n = 0
    for prim in gltf["meshes"][mesh_idx]["primitives"]:
        if "indices" in prim:
            n += gltf["accessors"][prim["indices"]]["count"] // 3
        else:
            n += gltf["accessors"][prim["attributes"]["POSITION"]]["count"] // 3
    return n


def subtree(gltf, idx):
    out = [idx]
    for c in gltf["nodes"][idx].get("children", []):
        out += subtree(gltf, c)
    return out


def is_identity_rot(node):
    r = node.get("rotation", [0, 0, 0, 1])
    return all(abs(a - b) < 1e-5 for a, b in zip(r, [0, 0, 0, 1])) and "matrix" not in node


def verify_props():
    path = os.path.join(MODELS, "props.glb")
    print(f"[props] {path}")
    g, ver, length = load_gltf(path)
    nodes = g["nodes"]
    names = [n.get("name", "") for n in nodes]
    scene = g["scenes"][g.get("scene", 0)]
    top = {nodes[i].get("name"): i for i in scene["nodes"]}
    check(len(names) == len(set(names)), f"all {len(names)} node names unique")
    check("root" not in top, "no 'root' node at top level (props.glb exception)")
    for p in PROPS:
        check(p in top, f"top-level node '{p}'")
    extra = sorted(set(top) - set(PROPS))
    check(not extra, f"no unexpected top-level nodes {extra if extra else ''}")
    for child, owner in ANIMATED.items():
        idxs = [i for i, n in enumerate(names) if n == child]
        check(len(idxs) == 1, f"exactly one node named '{child}'")
        if owner in top and idxs:
            check(idxs[0] in subtree(g, top[owner]), f"'{child}' is a descendant of '{owner}'")
            check(is_identity_rot(nodes[idxs[0]]), f"'{child}' rest rotation is identity")
            check("mesh" in nodes[idxs[0]], f"'{child}' carries a mesh")
    print("  tris per prop (from glTF accessors):")
    for p in PROPS:
        if p in top:
            t = sum(tri_count(g, nodes[i]["mesh"]) for i in subtree(g, top[p]) if "mesh" in nodes[i])
            budget = BUDGET[p]
            check(t <= budget, f"{p:20s} {t:6d} tris (budget {budget})")


def verify_arena():
    path = os.path.join(MODELS, "arena.glb")
    print(f"[arena] {path}")
    g, ver, length = load_gltf(path)
    nodes = g["nodes"]
    scene = g["scenes"][g.get("scene", 0)]
    top = [nodes[i].get("name") for i in scene["nodes"]]
    check(top == ["root"], f"single top-level node 'root' (got {top})")
    root = nodes[scene["nodes"][0]]
    check(all(abs(v) < 1e-6 for v in root.get("translation", [0, 0, 0])), "root at origin")
    t = sum(tri_count(g, nodes[i]["mesh"]) for i in subtree(g, scene["nodes"][0]) if "mesh" in nodes[i])
    check(t <= ARENA_BUDGET, f"arena {t} tris (budget {ARENA_BUDGET})")
    # top surface: max Y (glTF is Y-up) of the platform mesh must be 0 within the walkable disc
    plat = [i for i, n in enumerate(nodes) if n.get("name") == "arena_platform"]
    if plat:
        acc = g["accessors"][g["meshes"][nodes[plat[0]]["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
        check(abs(acc["max"][1]) < 1e-4, f"arena_platform top at y=0 (max y = {acc['max'][1]:.5f})")


if __name__ == "__main__":
    verify_props()
    verify_arena()
    if errors:
        print(f"\n{len(errors)} check(s) FAILED")
        sys.exit(1)
    print("\nall checks passed")
