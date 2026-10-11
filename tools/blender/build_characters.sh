#!/usr/bin/env bash
# Build all character / enemy GLBs (+ previews) and verify their node names.
# Usage (Git Bash, from anywhere):  bash tools/blender/build_characters.sh [name ...]
# Override the Blender binary with BLENDER=/path/to/blender if needed.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BLENDER="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"
MODELS=("$@")
[ ${#MODELS[@]} -eq 0 ] && MODELS=(kai lyra knight cograt slime beetle wisp golem)

cd "$ROOT" || exit 1
fail=0
for m in "${MODELS[@]}"; do
  log="$(mktemp)"
  if "$BLENDER" -b --factory-startup -P "tools/blender/model_${m}.py" >"$log" 2>&1 \
     && grep -q "^\[export\]" "$log" && ! grep -q "Traceback" "$log"; then
    echo "built  $m  $(grep -o '(~[0-9]* tris)' "$log")"
    grep "\[WARN\]" "$log"
  else
    echo "FAILED $m (log below)"; tail -n 30 "$log"; fail=1
  fi
  rm -f "$log"
done

echo "--- node check ---"
python "$HERE/check_glb.py" "${MODELS[@]}" || fail=1
exit $fail
