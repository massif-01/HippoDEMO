#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-install}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
VENV_DIR="$RUNTIME_DIR/python"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
STAMP_FILE="$RUNTIME_DIR/runtime-bootstrap.stamp"

python_candidate() {
  for candidate in \
    "$VENV_DIR/bin/python" \
    "/opt/homebrew/bin/python3.13" \
    "/opt/homebrew/bin/python3.12" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3.13" \
    "/usr/local/bin/python3.12" \
    "/usr/bin/python3"
  do
    if [[ -x "$candidate" ]]; then
      "$candidate" - <<'PY' >/dev/null 2>&1 && { echo "$candidate"; return 0; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
    fi
  done
  return 1
}

check_runtime() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "missing runtime python: $PYTHON_BIN" >&2
    return 1
  fi

  "$PYTHON_BIN" - <<'PY'
import importlib
import sys

if sys.version_info < (3, 12):
    raise SystemExit("Hippo runtime requires Python 3.12+")

modules = [
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "pydantic_settings",
    "openai",
    "loguru",
    "click",
    "sounddevice",
    "soundfile",
    "numpy",
    "litellm",
    "frontmatter",
    "mss",
    "PIL",
    "mcp",
    "minio",
    "basic_memory",
    "openchronicle",
    "ownscribe.config",
]

missing = []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")

if missing:
    print("Hippo runtime dependency check failed:", file=sys.stderr)
    for item in missing:
        print(f"  - {item}", file=sys.stderr)
    raise SystemExit(1)

print("Hippo runtime dependency check passed.")
PY
}

if [[ "$MODE" == "--check" || "$MODE" == "check" ]]; then
  check_runtime
  exit $?
fi

mkdir -p "$RUNTIME_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  BASE_PYTHON="$(python_candidate || true)"
  if [[ -z "${BASE_PYTHON:-}" ]]; then
    echo "Python 3.12+ is required to build the bundled Hippo runtime." >&2
    exit 1
  fi
  echo "Creating Hippo runtime venv with $BASE_PYTHON"
  "$BASE_PYTHON" -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip wheel setuptools

"$PIP_BIN" install -r "$ROOT_DIR/orchestrator/requirements.txt"
"$PIP_BIN" install -r "$ROOT_DIR/vlmac/requirements.txt"

"$PIP_BIN" install -e "$ROOT_DIR/OpenChronicle"
"$PIP_BIN" install -e "$ROOT_DIR/basic-memory"

# ownscribe is used by Hippo as an audio recorder shell plus remote ASR/Summary adapter.
# Do not pull WhisperX/llama.cpp here; Hippo's ownscribe adapter intentionally avoids
# local Whisper/llama runtime paths.
"$PIP_BIN" install --no-deps -e "$ROOT_DIR/ownscribe"
"$PIP_BIN" install click sounddevice soundfile numpy openai ollama

check_runtime

cat >"$STAMP_FILE" <<STAMP
runtime_python=$PYTHON_BIN
bootstrapped_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
STAMP

echo "Hippo runtime bootstrapped at $VENV_DIR"
