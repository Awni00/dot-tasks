#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_TASKS="$ROOT_DIR/examples/basic-demo/.tasks"
WORK_DIR="/tmp/dot-tasks-gif-demo"
OUTPUT_DIR="$ROOT_DIR/assets/demo"
TAPE_FILE="$OUTPUT_DIR/cli-demo.tape"
MP4_FILE="$OUTPUT_DIR/cli-demo.mp4"
GIF_FILE="$OUTPUT_DIR/cli-demo.gif"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command '$cmd' is not installed or not in PATH." >&2
    if [[ "$cmd" == "dot-tasks" ]]; then
      echo "Install dot-tasks in your environment (for example: pip install -e .)." >&2
    else
      echo "Install dependencies (example on macOS): brew install vhs ffmpeg gifsicle" >&2
    fi
    exit 1
  fi
}

require_cmd dot-tasks
require_cmd vhs
require_cmd ffmpeg

if [[ ! -d "$SOURCE_TASKS" ]]; then
  echo "Error: source tasks directory not found: $SOURCE_TASKS" >&2
  exit 1
fi

if [[ ! -f "$TAPE_FILE" ]]; then
  echo "Error: tape file not found: $TAPE_FILE" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp -R "$SOURCE_TASKS" "$WORK_DIR/.tasks"

(
  cd "$OUTPUT_DIR"
  vhs "$TAPE_FILE"
)

if command -v gifsicle >/dev/null 2>&1; then
  gifsicle -O3 --colors 128 "$GIF_FILE" -o "$GIF_FILE"
fi

if [[ ! -s "$MP4_FILE" ]]; then
  echo "Error: expected MP4 output missing or empty: $MP4_FILE" >&2
  exit 1
fi
if [[ ! -s "$GIF_FILE" ]]; then
  echo "Error: expected GIF output missing or empty: $GIF_FILE" >&2
  exit 1
fi

echo "Generated demo assets:"
echo "- $MP4_FILE"
echo "- $GIF_FILE"
