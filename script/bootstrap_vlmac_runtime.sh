#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="${1:-$ROOT_DIR/vlmac-runtime}"
VLMAC_DIR="$ROOT_DIR/vlmac"

if [[ ! -d "$VLMAC_DIR" ]]; then
  echo "vlmac source not found: $VLMAC_DIR" >&2
  exit 2
fi

choose_python() {
  for candidate in \
    "${HIPPODEMO_PYTHON:-}" \
    "$ROOT_DIR/orchestrator-runtime/bin/python" \
    "$ROOT_DIR/orchestrator/.venv/bin/python" \
    "/opt/homebrew/Caskroom/miniconda/base/bin/python" \
    "/opt/homebrew/opt/python@3.13/bin/python3.13" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    "python3.13" \
    "python3.12" \
    "python3"; do
    [[ -n "$candidate" ]] || continue
    if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
      "$candidate" - <<'PY' >/dev/null 2>&1 && {
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
        printf '%s\n' "$candidate"
        return 0
      }
    fi
  done
  return 1
}

PYTHON="$(choose_python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10+ is required to build the bundled vlmac runtime." >&2
  exit 2
fi

rm -rf "$RUNTIME_DIR"
"$PYTHON" -m venv "$RUNTIME_DIR"
"$RUNTIME_DIR/bin/python" -m pip install --upgrade pip wheel
"$RUNTIME_DIR/bin/python" -m pip install -r "$VLMAC_DIR/requirements.txt"
"$RUNTIME_DIR/bin/python" - <<'PY'
import fastapi
import httpx
import imageio_ffmpeg
import uvicorn
import websockets

print(imageio_ffmpeg.get_ffmpeg_exe())
PY

cat <<EOF
vlmac runtime ready:
  runtime: $RUNTIME_DIR
  python:  $RUNTIME_DIR/bin/python
EOF
