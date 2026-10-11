"""props2.glb — chapter-1 town / factory / tower props as top-level nodes (same conventions as props.glb,
see ASSET_SPEC.md "props.glb"; the game looks props up by name in props.glb, then props2.glb).

Builders live in group modules (same interface as the props_*.py modules of model_props.py):
    props_town.py   prop_house, prop_locomotive, prop_nail_board, prop_organ, prop_chimney, prop_drive_shaft
Each module exposes setup_mats(), PROPS = [(name, builder, preview_kwargs), ...] and BUDGET = {name: tris}.

Run (from project root):
    blender -b --factory-startup -P tools/blender/model_props2.py              # export public/models/props2.glb
Options (after `--`):
    --previews             render every prop alone (EEVEE) -> <preview dir>/<name>.png (+ _back)
    --only=a,b             restrict previews to these prop names
    --no-export            skip the export (preview iteration only)
    --out=DIR              export to DIR/props2.glb instead of public/models
    --preview-dir=DIR      where previews go (default tools/blender/previews)

Blender object names are unique, so repeated child names (`steam_point` in several props) are built
as `steam_point.001` ... and the suffix is stripped in the exported GLB (fix_glb_names); look child nodes
up inside the prop (prop.getObjectByName('steam_point')).
"""
import importlib
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: E402,F401,F403
from env_helpers import tree_bbox  # noqa: E402
import hp_helpers as hp  # noqa: E402

GROUPS = ["town"]
# child names that may repeat across props (Blender appends .001 -> stripped in the GLB)
SHARED_CHILD_NAMES = ("steam_point",)


def load_groups(names):
    return [importlib.import_module("props_" + g) for g in names]


def setup_mats(mods):
    for m in mods:
        m.setup_mats()


def _report(name, root, budget):
    tris = hp.tree_tris(root)
    mins, maxs = tree_bbox(root)
    size = maxs - mins
    flag = "" if tris <= budget else "  !!! OVER BUDGET"
    print(f"[tris] {name:22s} {tris:6d} / {budget}  size=({size.x:.2f}, {size.y:.2f}, {size.z:.2f})"
          f"  min=({mins.x:.2f}, {mins.y:.2f}, {mins.z:.3f}) max=({maxs.x:.2f}, {maxs.y:.2f}, {maxs.z:.2f}){flag}")
    return tris


def fix_glb_names(path):
    """Strip Blender's '.NNN' uniqueness suffix from shared child node names inside the GLB."""
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    jlen, jtype = struct.unpack_from("<I4s", data, 12)
    g = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    pat = re.compile(r"^(%s)\.\d{3}$" % "|".join(SHARED_CHILD_NAMES))
    n = 0
    for node in g.get("nodes", []):
        m = pat.match(node.get("name", ""))
        if m:
            node["name"] = m.group(1)
            n += 1
    js = json.dumps(g, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    out = struct.pack("<4sII", b"glTF", version, 12 + 8 + len(js) + len(rest)) + struct.pack("<I4s", len(js), b"JSON") + js + rest
    with open(path, "wb") as f:
        f.write(out)
    print(f"[export] renamed {n} shared child node(s) in {os.path.basename(path)}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = None
    out_dir = None
    for a in argv:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
        elif a.startswith("--out="):
            out_dir = a.split("=", 1)[1]
        elif a.startswith("--preview-dir="):
            hp.PREVIEW_DIR = a.split("=", 1)[1]
    mods = load_groups(GROUPS)
    entries = [(name, fn, pv, m.BUDGET.get(name, 1500)) for m in mods for (name, fn, pv) in m.PROPS]

    if "--previews" in argv:
        for name, fn, pv, budget in entries:
            if only and name not in only:
                continue
            reset_scene()
            setup_mats(mods)
            root = fn()
            bpy.context.view_layer.update()
            _report(name, root, budget)
            views = pv.get("views", (("", 35, 18), ("_back", 215, 22)))
            kw = {k: v for k, v in pv.items() if k != "views"}
            for suffix, az, el in views:
                hp.render_hp(name + suffix, azimuth=az, elevation=el, **kw)
    if "--no-export" in argv:
        return
    reset_scene()
    setup_mats(mods)
    x = 0.0
    total = 0
    for name, fn, _, budget in entries:
        root = fn()
        bpy.context.view_layer.update()
        mins, maxs = tree_bbox(root)
        root.location.x = x - mins.x
        x += (maxs.x - mins.x) + 3.0
        bpy.context.view_layer.update()
        total += _report(name, root, budget)
    print(f"[tris] total {total}")
    path = hp.export_glb_hp("props2", out_dir=out_dir)
    fix_glb_names(path)


main()
