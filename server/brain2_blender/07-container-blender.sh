#!/bin/bash
# One-time setup of STAR's Blender Lab inside brain 2's STAR container (run as root in the container).
# Blender itself (5.1 or newer; tested 5.2.2 LTS) must already be in /opt/blender with a /usr/local/bin/blender link.
# What this adds, all pinned and checksummed:
#   * python3-venv + python3-pip (apt) and a virtualenv for the Lab MCP server (mcp SDK, docutils, pyyaml)
#   * the official Blender Lab MCP add-on 1.0.3 (blender_mcp, https://projects.blender.org/lab/blender_mcp) as a
#     user extension of the desktop user. It is NOT enabled in the preferences: blender-lab.sh enables it per session,
#     bound to 127.0.0.1, so a Blender started by hand has no code-executing socket.
#   * the launcher blender-lab.sh (+ startup script) in the user's bin and lab folders.
# Usage: ./07-container-blender.sh [desktop user, default star]
set -eu
U=${1:-star}
H=$(getent passwd "$U" | cut -d: -f6)
LAB=$H/blender-lab
HERE=$(cd "$(dirname "$0")" && pwd)
ADDON_URL=https://projects.blender.org/lab/blender_mcp/releases/download/v1.0.3/mcp-1.0.3.zip
ADDON_SHA=a7a9da816192502e5a0a202a396444e266b47d8fc4f74ad4698048bd43040707
BUNDLE_URL=https://projects.blender.org/lab/blender_mcp/releases/download/v1.0.3/blender-1.0.3.mcpb
BUNDLE_SHA=d6fe04dd17767f7c7fb452142f1f0e6787db575db49f3976a166142683b5b97e

[ -x /opt/blender/blender ] || { echo "Blender not found in /opt/blender" >&2; exit 3; }
apt-get install -y --no-install-recommends python3-venv python3-pip imagemagick xdotool bc >/dev/null
sudo -u "$U" mkdir -p "$LAB"/{dl,mcp,sandbox/shots,logs} "$H/bin"
fetch() {  # url sha file
  [ -f "$LAB/dl/$3" ] || sudo -u "$U" curl -fsSL -m 120 -o "$LAB/dl/$3" "$1"
  echo "$2  $LAB/dl/$3" | sha256sum -c - >/dev/null || { echo "checksum mismatch for $3" >&2; exit 4; }
}
fetch "$ADDON_URL" "$ADDON_SHA" mcp-1.0.3.zip
fetch "$BUNDLE_URL" "$BUNDLE_SHA" blender-1.0.3.mcpb
sudo -u "$U" python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$LAB/dl/blender-1.0.3.mcpb" "$LAB/mcp"
[ -x "$LAB/venv/bin/python" ] || sudo -u "$U" python3 -m venv "$LAB/venv"
sudo -u "$U" "$LAB/venv/bin/pip" install -q -r "$LAB/mcp/requirements.txt"
# User extension (not enabled in the preferences). --online-mode only for this one install command.
sudo -u "$U" -H /opt/blender/blender -b --factory-startup --online-mode --command extension install-file \
  -r user_default "$LAB/dl/mcp-1.0.3.zip" >/dev/null
install -o "$U" -g "$U" -m 755 "$HERE/blender-lab.sh" "$H/bin/blender-lab.sh"
install -o "$U" -g "$U" -m 644 "$HERE/blender-lab-startup.py" "$LAB/startup.py"
echo "done. Try: sudo -u $U -H $H/bin/blender-lab.sh status"
