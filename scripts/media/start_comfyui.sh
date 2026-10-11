#!/usr/bin/env bash
# Start the ComfyUI installed by setup_comfyui.sh, reachable from this computer only.
#   MEDIA_HOME=/path/to/media bash scripts/media/start_comfyui.sh [port]
set -euo pipefail
MEDIA_HOME="${MEDIA_HOME:?set MEDIA_HOME to the folder that holds ComfyUI}"
PORT="${1:-8188}"
COMFY="$MEDIA_HOME/ComfyUI"
PY="$COMFY/.venv/Scripts/python.exe"; [ -f "$PY" ] || PY="$COMFY/.venv/bin/python"
cd "$COMFY"
# 127.0.0.1 only: ComfyUI has no sign-in, so it must not listen on the network.
exec "$PY" main.py --listen 127.0.0.1 --port "$PORT" --disable-auto-launch
