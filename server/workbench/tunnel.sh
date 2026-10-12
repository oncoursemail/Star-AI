#!/usr/bin/env bash
# Run ONLY inside the separate workbench container, never beside the model/secrets.
set +x
set -euo pipefail
umask 077
[[ ! -e /opt/star/secrets && ! -L /opt/star/secrets ]] || { echo 'Refusing model/secrets container' >&2; exit 1; }
# Log ONLY the first public hostname. Cloudflared error logs may contain request
# URLs, so piping its full stderr to journald would disclose path credentials.
if [[ "${1:-}" == serve ]]; then
  [[ $EUID -ne 0 ]] || { echo 'Refusing root tunnel process' >&2; exit 1; }
  /usr/local/bin/star-cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8765 2>&1 |
    sed -unE 's#.*(https://[a-z0-9-]+\.trycloudflare\.com).*#\1#p' |
    awk '!seen++ { print; fflush() }'
  exit
fi
[[ $EUID -eq 0 ]] || { echo 'Run as container root' >&2; exit 1; }
case "${1:-url}" in
  url)
    # Only the current invocation: never return a dead hostname from an older restart.
    systemctl is-active --quiet star-workbench-tunnel.service
    INVOCATION=$(systemctl show star-workbench-tunnel.service -p InvocationID --value)
    [[ -n "$INVOCATION" ]] || { echo 'Tunnel is not running' >&2; exit 1; }
    journalctl "_SYSTEMD_INVOCATION_ID=$INVOCATION" --no-pager -o cat |
      grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1
    ;;
  install)
    [[ -f /etc/systemd/system/star-workbench.service ]] || { echo 'Install workbench first' >&2; exit 1; }
    [[ ! -e /etc/systemd/system/star-workbench-tunnel.service ]] || { echo 'Tunnel already installed' >&2; exit 1; }
    VERSION=2026.10.0
    # Pinned official release checksums, not downloaded dynamically alongside the binary.
    # https://github.com/cloudflare/cloudflared/releases/tag/2026.10.0
    case "$(uname -m)" in
      x86_64) ARCH=amd64; SHA=d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db ;;
      aarch64) ARCH=arm64; SHA=e6422b9d4f72d3194bc5a38676f13667c06666523217b842a877d72a80b5ac08 ;;
      *) echo 'Unsupported architecture' >&2; exit 1 ;;
    esac
    TEMP=$(mktemp -d)
    trap 'rm -rf -- "$TEMP"' EXIT
    curl --fail --location --proto '=https' --proto-redir '=https' \
      "https://github.com/cloudflare/cloudflared/releases/download/$VERSION/cloudflared-linux-$ARCH" \
      --output "$TEMP/cloudflared"
    printf '%s  %s\n' "$SHA" "$TEMP/cloudflared" | sha256sum --check --status
    install -o root -g root -m 755 "$TEMP/cloudflared" /usr/local/bin/star-cloudflared
    useradd --system --user-group --no-create-home --shell /usr/sbin/nologin star-workbench-tunnel
    cat > /etc/systemd/system/star-workbench-tunnel.service <<'EOF'
[Unit]
Description=STAR Workbench temporary HTTPS tunnel
Requires=star-workbench.service
After=network-online.target star-workbench.service
[Service]
User=star-workbench-tunnel
Group=star-workbench-tunnel
ExecStart=/bin/bash /opt/star-workbench/tunnel.sh serve
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
InaccessiblePaths=/work /etc/star-workbench /var/lib/star-workbench /var/log/star-workbench
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=256M
TasksMax=32
UMask=0077
StandardOutput=journal
StandardError=journal
[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now star-workbench-tunnel.service
    printf 'Read the current public URL with: bash /opt/star-workbench/tunnel.sh url\n'
    ;;
  *) echo 'Usage: tunnel.sh install|url' >&2; exit 2 ;;
esac
