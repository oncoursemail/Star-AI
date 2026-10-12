#!/usr/bin/env bash
# ONLY in a FRESH, SEPARATE LXD or Docker container. NEVER in the model container.
# This container must have no secrets, host mounts, Docker socket, or LAN services.
set +x
set -euo pipefail
umask 077
[[ ! -e /opt/star/secrets && ! -L /opt/star/secrets ]] || { echo 'Refusing model/secrets container' >&2; exit 1; }
[[ $EUID -eq 0 ]] || { echo 'Run this installer as container root' >&2; exit 1; }
case "$(systemd-detect-virt --container 2>/dev/null || true)" in
  lxc|docker) ;; *) echo 'A separate LXD/Docker container is required' >&2; exit 1 ;;
esac
[[ -d /run/systemd/system ]] || { echo 'systemd must be PID 1 in this container' >&2; exit 1; }
[[ ! -e /opt/star-workbench && ! -e /etc/star-workbench && ! -e /work ]] || {
  echo 'Fresh installation only; refusing existing control state or workspace' >&2; exit 1;
}
source /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 13 ]] || { echo 'Use a fresh Debian 13 container' >&2; exit 1; }
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
trap 'install -d -m 700 /etc/star-workbench; touch /etc/star-workbench/PAUSED; systemctl stop star-workbench.service 2>/dev/null || true' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev nodejs npm git build-essential \
  bubblewrap util-linux nftables openssl ca-certificates curl
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if (!(a>22 || a===22&&b>=12 || a===20&&b>=19)) process.exit(1)'
useradd --system --user-group --home-dir /work --shell /usr/sbin/nologin star-workbench
install -d -o star-workbench -g star-workbench -m 700 /work /var/lib/star-workbench
install -d -o root -g star-workbench -m 750 /var/log/star-workbench
install -o root -g star-workbench -m 620 /dev/null /var/log/star-workbench/audit.jsonl
install -d -m 755 /opt/star-workbench
# 0755 permits the service to see PAUSED but not alter it; token itself is 0600.
install -d -m 755 /etc/star-workbench
install -m 644 "$HERE/app.py" "$HERE/requirements.txt" /opt/star-workbench/
install -m 755 "$HERE/tunnel.sh" /opt/star-workbench/tunnel.sh
printf 'nameserver 1.1.1.1\nnameserver 1.0.0.1\n' > /opt/star-workbench/resolv.conf
chmod 644 /opt/star-workbench/resolv.conf
python3 -m venv /opt/star-workbench/venv
/opt/star-workbench/venv/bin/pip install --disable-pip-version-check -r /opt/star-workbench/requirements.txt
# umask 077 protects credentials, but the unprivileged service must read its runtime.
# Only publish immutable runtime files; NEVER apply this to the token/control directories.
chmod -R go+rX /opt/star-workbench/venv
# Root source stays unreadable to the service. systemd supplies a private, read-only copy.
openssl rand -hex 32 > /etc/star-workbench/token
chmod 600 /etc/star-workbench/token
WORK_UID=$(id -u star-workbench)
# Separate table; never flush the host/container's other firewall rules.
cat > /etc/star-workbench/egress.nft <<EOF
 table inet star_workbench {
  chain output {
   type filter hook output priority 0; policy accept;
   meta skuid $WORK_UID ct state established,related accept
   meta skuid $WORK_UID meta nfproto ipv6 reject
   meta skuid $WORK_UID ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, 192.0.2.0/24, 192.168.0.0/16, 198.18.0.0/15, 198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/4, 240.0.0.0/4 } reject
   meta skuid $WORK_UID ip daddr { 1.1.1.1, 1.0.0.1 } udp dport 53 accept
   meta skuid $WORK_UID ip daddr { 1.1.1.1, 1.0.0.1 } tcp dport 53 accept
   meta skuid $WORK_UID tcp dport 443 accept
   meta skuid $WORK_UID reject
  }
 }
EOF
chmod 600 /etc/star-workbench/egress.nft
cat > /etc/systemd/system/star-workbench-firewall.service <<'EOF'
[Unit]
Description=STAR Workbench private-network egress barrier
Before=star-workbench.service
[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/star-workbench/egress.nft
RemainAfterExit=yes
# Deliberately no ExecStop: stopping a service must not open network access.
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/star-workbench.service <<'EOF'
[Unit]
Description=Isolated STAR MCP Workbench
Requires=star-workbench-firewall.service
After=network-online.target star-workbench-firewall.service
[Service]
Type=simple
User=star-workbench
Group=star-workbench
WorkingDirectory=/work
LoadCredential=token:/etc/star-workbench/token
Environment=WORKBENCH_PORT=8765
ExecStart=/opt/star-workbench/venv/bin/python /opt/star-workbench/app.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/work /var/lib/star-workbench /var/log/star-workbench/audit.jsonl
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
# bubblewrap needs unprivileged user/mount/PID namespaces; do not disable them here.
MemoryMax=4G
MemorySwapMax=0
TasksMax=384
CPUQuota=200%
UMask=0077
KillMode=control-group
TimeoutStopSec=10
# Never persist a URL-path credential in server tracebacks/access logs.
StandardOutput=null
StandardError=null
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now star-workbench-firewall.service
# REAL sandbox/network/toolchain smoke test; abort rather than silently running unsandboxed.
# Preparation is unprivileged and uses the same bwrap/prlimit launcher as all MCP commands.
runuser -u star-workbench -- /opt/star-workbench/venv/bin/python /opt/star-workbench/app.py --prepare
systemctl enable --now star-workbench.service
systemctl is-active --quiet star-workbench.service
# Only the path is printed, never the token or a token-bearing URL.
printf '\nToken file: /etc/star-workbench/token\n'
printf 'Next: bash /opt/star-workbench/tunnel.sh install\n'
