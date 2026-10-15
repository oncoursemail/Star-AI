#!/bin/bash
# Install or refresh the star-training-gen systemd unit INSIDE the container (run as root). It does not start
# or enable the unit and touches nothing outside /opt/star/training and /etc/systemd/system/star-training-gen.service.
set -eu
HOME_DIR=/opt/star/training
test -f "$HOME_DIR/app/star-training-gen.service" || { echo "deploy first"; exit 1; }
install -d -o star -g star -m 0750 "$HOME_DIR" "$HOME_DIR/data" "$HOME_DIR/decontam" "$HOME_DIR/suites"
[ -e "$HOME_DIR/env" ] || { : > "$HOME_DIR/env"; chown star:star "$HOME_DIR/env"; }
install -o root -g root -m 0644 "$HOME_DIR/app/star-training-gen.service" /etc/systemd/system/star-training-gen.service
systemctl daemon-reload
systemctl cat star-training-gen >/dev/null && echo "unit installed (not started, not enabled)"
