#!/bin/bash
# Install or update STAR's SearXNG + search gateway INSIDE the server's starai LXD container (as root).
# Normally run through deploy.sh from the PC. Expects this folder's files in the current directory.
#
# Stage 1 (once; needs internet): user `searxng`, official source github.com/searxng/searxng in
#   /usr/local/searxng/searxng-src, venv /usr/local/searxng/searx-pyenv (pip install -e . + granian).
# Stage 2 (every run): /etc/searxng/settings.yml (random secret kept across runs), searxng.service on
#   127.0.0.1:8888, /opt/star/search-gateway/gateway.py + star-search-gateway.service on :8093.
# It never touches star-brain, star-knowledge, /opt/star/config or /opt/star/models.
# Backup/rollback: see README.md (previous settings.yml and gateway.py are kept as *.bak-<stamp>).
set -eu
cd "$(dirname "$0")"
STAMP="$(date -u +%Y%m%d%H%M%S)"
SX=/usr/local/searxng

# ---- stage 1 ---------------------------------------------------------------------------------
id searxng >/dev/null 2>&1 || useradd --system --shell /usr/sbin/nologin --home-dir "$SX" --create-home searxng
chmod 0755 "$SX"
if [ ! -d "$SX/searxng-src/.git" ]; then
  runuser -u searxng -- git clone --depth 1 https://github.com/searxng/searxng.git "$SX/searxng-src"
elif [ "${SEARXNG_UPDATE:-0}" = "1" ]; then
  runuser -u searxng -- git -C "$SX/searxng-src" rev-parse HEAD > "$SX/previous-commit.txt"
  runuser -u searxng -- git -C "$SX/searxng-src" pull --ff-only
fi
if [ ! -x "$SX/searx-pyenv/bin/granian" ] || [ "${SEARXNG_UPDATE:-0}" = "1" ]; then
  [ -x "$SX/searx-pyenv/bin/python" ] || runuser -u searxng -- python3 -m venv "$SX/searx-pyenv"
  runuser -u searxng -- nice -n 19 "$SX/searx-pyenv/bin/pip" install -q -U pip setuptools wheel pyyaml msgspec typing_extensions
  (cd "$SX/searxng-src" && runuser -u searxng -- nice -n 19 "$SX/searx-pyenv/bin/pip" install -q --use-pep517 --no-build-isolation -e .)
  runuser -u searxng -- nice -n 19 "$SX/searx-pyenv/bin/pip" install -q -r "$SX/searxng-src/requirements-server.txt"
fi
runuser -u searxng -- git -C "$SX/searxng-src" log -1 --format='searxng %H %cs' | tee "$SX/VERSION"

# ---- stage 2 ---------------------------------------------------------------------------------
install -d -o root -g searxng -m 0750 /etc/searxng
if [ -f /etc/searxng/settings.yml ]; then
  cp -p /etc/searxng/settings.yml "/etc/searxng/settings.yml.bak-$STAMP"
  SECRET="$(sed -n 's/^  secret_key: "\(.*\)"$/\1/p' /etc/searxng/settings.yml | head -1)"
fi
if [ -z "${SECRET:-}" ] || [ "$SECRET" = "__SECRET__" ]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
fi
sed "s/__SECRET__/$SECRET/" settings.yml > /etc/searxng/settings.yml.new
chown root:searxng /etc/searxng/settings.yml.new
chmod 0640 /etc/searxng/settings.yml.new
mv /etc/searxng/settings.yml.new /etc/searxng/settings.yml

install -d -o star -g star -m 0755 /opt/star/search-gateway
[ -f /opt/star/search-gateway/gateway.py ] && cp -p /opt/star/search-gateway/gateway.py "/opt/star/search-gateway/gateway.py.bak-$STAMP"
install -o star -g star -m 0644 gateway.py /opt/star/search-gateway/gateway.py
install -o root -g root -m 0644 searxng.service /etc/systemd/system/searxng.service
install -o root -g root -m 0644 star-search-gateway.service /etc/systemd/system/star-search-gateway.service
systemctl daemon-reload
systemctl enable searxng.service star-search-gateway.service >/dev/null 2>&1
systemctl restart searxng.service
systemctl restart star-search-gateway.service
for i in $(seq 1 30); do
  curl -fsS -m 3 -o /dev/null "http://127.0.0.1:8888/healthz" 2>/dev/null && break
  sleep 1
done
systemctl is-active searxng.service star-search-gateway.service
ss -ltn | grep -E ':(8888|8093)\b'
curl -fsS -m 3 http://127.0.0.1:8093/health; echo
