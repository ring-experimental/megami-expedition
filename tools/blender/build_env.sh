#!/usr/bin/env bash
# Build environment models (props.glb, arena.glb) and verify their node structure.
#   bash tools/blender/build_env.sh             # export + overview previews
#   bash tools/blender/build_env.sh --previews  # also per-prop / extra arena previews
# Override the Blender path with BLENDER=/path/to/blender.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BLENDER="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"
PY="${PYTHON:-python}"

cd "$ROOT"
for script in model_props.py model_arena.py; do
  echo "=== $script"
  log="$("$BLENDER" -b --factory-startup -P "tools/blender/$script" -- "$@" 2>&1)" || true
  echo "$log" | grep -E '^\[(tris|export|preview)\]' || true
  # blender -b exits 0 even when the script raises, so check the log
  if echo "$log" | grep -q 'Traceback'; then
    echo "$log" | sed -n '/Traceback/,$p'
    echo "!!! $script failed" >&2
    exit 1
  fi
done

echo "=== verify"
"$PY" "$HERE/verify_env.py"
