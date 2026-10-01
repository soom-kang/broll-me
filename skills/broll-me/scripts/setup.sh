#!/usr/bin/env bash
# Install only inside a dedicated local runtime; --check performs no writes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ARG="${BROLL_RUNTIME:-./motion}"
CHECK_ONLY=0
PATH_SET=0
for arg in "$@"; do
  case "$arg" in
    --check|--check-only) CHECK_ONLY=1 ;;
    --help|-h) printf 'Usage: bash setup.sh [runtime_path] [--check]\n'; exit 0 ;;
    --*) printf 'Unknown option: %s\n' "$arg" >&2; exit 1 ;;
    *) if [ "$PATH_SET" -eq 1 ]; then printf 'Only one runtime path is allowed\n' >&2; exit 1; fi; RUNTIME_ARG="$arg"; PATH_SET=1 ;;
  esac
done
NODE_BIN="${BROLL_NODE:-node}"
PYTHON_BIN="${BROLL_PYTHON:-python3}"
NPM_BIN="${BROLL_NPM:-npm}"
FFMPEG_BIN="${BROLL_FFMPEG:-ffmpeg}"
FFPROBE_BIN="${BROLL_FFPROBE:-ffprobe}"
for executable in "$NODE_BIN" "$PYTHON_BIN" "$FFMPEG_BIN" "$FFPROBE_BIN"; do
  command -v "$executable" >/dev/null || { printf 'Missing executable: %s\n' "$executable" >&2; exit 1; }
done
"$NODE_BIN" -e 'if(Number(process.versions.node.split(".")[0])<20){console.error("Node 20+ is required");process.exit(1)}'
"$PYTHON_BIN" -c 'import sys; sys.exit("Python 3.11+ is required" if sys.version_info < (3,11) else 0)'
"$PYTHON_BIN" "$SCRIPT_DIR/runtime/check_versions.py" "$SCRIPT_DIR/runtime/versions.json" "$NODE_BIN" "$FFMPEG_BIN" "$FFPROBE_BIN"
RUNTIME_DIR="$("$PYTHON_BIN" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$RUNTIME_ARG")"
if [ "$RUNTIME_DIR" = / ]; then printf 'Use a dedicated project runtime directory\n' >&2; exit 1; fi
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$RUNTIME_DIR/browsers}"
check_runtime() {
  [ -x "$RUNTIME_DIR/.venv/bin/python" ] || { printf 'Runtime virtualenv missing: %s/.venv\n' "$RUNTIME_DIR" >&2; return 1; }
  "$RUNTIME_DIR/.venv/bin/python" "$SCRIPT_DIR/runtime/check_versions.py" "$SCRIPT_DIR/runtime/versions.json" "$NODE_BIN" "$FFMPEG_BIN" "$FFPROBE_BIN"
  "$RUNTIME_DIR/.venv/bin/python" -c 'import numpy; assert numpy.__version__ == "2.3.5", "NumPy version mismatch"'
  "$NODE_BIN" "$SCRIPT_DIR/runtime/browser_check.js" "$RUNTIME_DIR" "$SCRIPT_DIR/runtime/versions.json"
  local encoders
  encoders="$("$FFMPEG_BIN" -hide_banner -encoders 2>/dev/null)"
  [[ "$encoders" == *prores_ks* && "$encoders" == *libx264* ]] || { printf 'FFmpeg requires libx264 and prores_ks encoders\n' >&2; return 1; }
  "$FFPROBE_BIN" -version >/dev/null
}
if [ "$CHECK_ONLY" -eq 1 ]; then
  check_runtime
  printf 'Runtime ready: %s (read-only check)\n' "$RUNTIME_DIR"
  exit 0
fi
command -v "$NPM_BIN" >/dev/null || { printf 'Missing npm; set BROLL_NPM or add npm to PATH\n' >&2; exit 1; }
# Never replace a project's unrelated package manifest or lockfile.
for filename in package.json package-lock.json; do
  if [ -f "$RUNTIME_DIR/$filename" ] && ! cmp -s "$SCRIPT_DIR/runtime/$filename" "$RUNTIME_DIR/$filename"; then
    printf 'Existing %s differs. Choose a dedicated empty runtime directory.\n' "$RUNTIME_DIR/$filename" >&2
    exit 1
  fi
done
mkdir -p "$RUNTIME_DIR"
cp "$SCRIPT_DIR/runtime/package.json" "$SCRIPT_DIR/runtime/package-lock.json" "$RUNTIME_DIR/"
if [ ! -x "$RUNTIME_DIR/.venv/bin/python" ]; then "$PYTHON_BIN" -m venv "$RUNTIME_DIR/.venv"; fi
if ! "$RUNTIME_DIR/.venv/bin/python" -c 'import numpy; assert numpy.__version__ == "2.3.5"' 2>/dev/null; then
  "$RUNTIME_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$SCRIPT_DIR/runtime/requirements.txt"
fi
NODE_RESOLVED="$(command -v "$NODE_BIN")"
export PATH="$(dirname "$NODE_RESOLVED"):$PATH"
(cd "$RUNTIME_DIR" && "$NPM_BIN" ci --ignore-scripts --omit=optional --no-audit --no-fund)
if [ -z "${BROLL_CHROMIUM:-}" ]; then "$NODE_BIN" "$RUNTIME_DIR/node_modules/playwright/cli.js" install chromium; fi
check_runtime
printf 'Runtime ready. Use these environment settings:\n'
printf 'export BROLL_RUNTIME=%q\n' "$RUNTIME_DIR"
printf 'export BROLL_PYTHON=%q\n' "$RUNTIME_DIR/.venv/bin/python"
printf 'export NODE_PATH=%q\n' "$RUNTIME_DIR/node_modules"
printf 'export PLAYWRIGHT_BROWSERS_PATH=%q\n' "$PLAYWRIGHT_BROWSERS_PATH"
