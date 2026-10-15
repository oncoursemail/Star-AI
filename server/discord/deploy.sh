#!/usr/bin/env bash
# Run STAR's Discord bot on a STAR server container (brain 2) instead of the owner's PC. Run from the repository
# root on the PC (Git Bash):
#
#   STAR_DISCORD_SSH=<user@address of the LXD host> bash server/discord/deploy.sh <command>
#
#   install    copy the code (git HEAD: star/, requirements*.txt, server/discord/) to /opt/star/discord/releases/<sha>,
#              point current -> it (the old one becomes previous), create/refresh the venv, install the unit, enable it
#              at boot. Restarts the bot only if it was already running. First install: set STAR_BRAIN_URL
#              (http://<brain 1 LAN address>:8080/v1) to write the bot's STAR settings (state/star-ai/settings.json).
#   secrets    copy ~/.star/discord.env, discord-settings.env, server_api_key and gpu-worker.key (created here
#              the first time, with ~/.star/gpu-worker.env for the PC GPU worker) from this PC to
#              /opt/star/discord/secrets (directory 0700, files 0600, owner star-discord). Contents never printed.
#              Restart the bot afterwards (stop, start) so it reads a new key.
#   doctor     offline readiness check as the service user (prints no token)
#   start      start the bot (stop the PC bot FIRST: two copies would both answer)
#   stop       stop the bot
#   status     service state, the running release and the last journal lines
#   rollback   current <-> previous release, then restart if it was running
#
# The address is operator configuration and is never stored in the repository. Commands run as root inside the
# container through `lxc exec`; the bot itself runs as the unprivileged user star-discord.
set -euo pipefail
target="${STAR_DISCORD_SSH:?set STAR_DISCORD_SSH to user@address of the LXD host}"
container="${STAR_LXC_CONTAINER:-starai}"
base=/opt/star/discord
unit=star-discord.service
cmd="${1:-}"
remote() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$target" "lxc exec $container -- bash -c $(printf '%q' "$*")"; }
# stdin -> a file inside the container, written with umask 077 and handed to star-discord (never echoed).
push_secret() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$target" \
  "lxc exec $container -- bash -c $(printf '%q' "umask 077; cat > $base/secrets/$1.tmp && chown star-discord:star-discord $base/secrets/$1.tmp && chmod 600 $base/secrets/$1.tmp && mv $base/secrets/$1.tmp $base/secrets/$1")"; }
running() { remote "systemctl is-active --quiet $unit"; }

case "$cmd" in
install)
  root="$(git rev-parse --show-toplevel)"; cd "$root"
  sha="$(git rev-parse --short=12 HEAD)"
  echo "== user and folders"
  remote "id star-discord >/dev/null 2>&1 || useradd --system --home-dir $base/state --shell /usr/sbin/nologin star-discord"
  remote "install -d -o root -g root -m 755 $base $base/releases && install -d -o star-discord -g star-discord -m 700 $base/secrets $base/state"
  echo "== code (git HEAD $sha)"
  remote "rm -rf $base/releases/$sha.tmp && install -d -m 755 $base/releases/$sha.tmp"
  git archive HEAD star requirements.txt requirements-discord.txt server/discord |
    ssh -o BatchMode=yes "$target" "lxc exec $container -- tar -x --no-same-owner -C $base/releases/$sha.tmp"
  remote "rm -rf $base/releases/$sha && mv $base/releases/$sha.tmp $base/releases/$sha && chmod -R a+rX,go-w $base/releases/$sha"
  echo "== venv"
  remote "test -x $base/venv/bin/python || python3 -m venv $base/venv"
  remote "$base/venv/bin/python -m pip install -q --disable-pip-version-check -r $base/releases/$sha/requirements.txt -r $base/releases/$sha/requirements-discord.txt"
  remote "cd /tmp && $base/venv/bin/python -c 'import sys; sys.path.insert(0, \"$base/releases/$sha\"); import discord, pillow_heif, star.discord_bot.bot; print(\"imports ok, discord.py\", discord.__version__)'"
  echo "== STAR settings"
  settings=$base/state/star-ai/settings.json
  if remote "test -f $settings"; then
    echo "kept existing $settings"
  else
    url="${STAR_BRAIN_URL:?first install: set STAR_BRAIN_URL=http://<brain 1 LAN address>:8080/v1}"
    case "$url" in http://*:*/v1) ;; *) echo "STAR_BRAIN_URL must look like http://<address>:8080/v1" >&2; exit 2;; esac
    # Model names are the brain's role names (GET /v1/models); the quick/vision roles are discovered at run time too.
    printf '{"provider": "star_server", "server_endpoint": "%s", "model": "star-fast", "vision_model": "star-vision"}\n' "$url" |
      ssh -o BatchMode=yes "$target" "lxc exec $container -- bash -c $(printf '%q' "install -d -o star-discord -g star-discord -m 700 $base/state/star-ai && umask 077 && cat > $settings && chown star-discord:star-discord $settings")"
    echo "wrote $settings"
  fi
  echo "== switch current -> $sha"
  was_running=0; running && was_running=1
  remote "cd $base && old=\$(readlink current || true); if [ -n \"\$old\" ] && [ \"\$old\" != releases/$sha ]; then ln -sfn \"\$old\" previous; fi; ln -sfn releases/$sha current"
  remote "install -m 644 $base/current/server/discord/$unit /etc/systemd/system/$unit && systemctl daemon-reload && systemctl enable $unit"
  # Keep the current, previous and two older releases.
  remote "cd $base/releases && keep=\"\$(readlink ../current | cut -d/ -f2) \$(readlink ../previous 2>/dev/null | cut -d/ -f2)\"; ls -1t | grep -v '\\.tmp\$' | tail -n +5 | while read -r r; do case \" \$keep \" in *\" \$r \"*) ;; *) rm -rf \"\$r\";; esac; done"
  if [ "$was_running" = 1 ]; then remote "systemctl restart $unit"; echo "restarted"; else echo "installed and enabled at boot; not started (bash $0 start)"; fi
  ;;
secrets)
  remote "install -d -o star-discord -g star-discord -m 700 $base/secrets"
  # The PC GPU worker's files (star/discord_bot/gpu_worker.py): a new signing key the first time (shared with
  # the bot, never printed) and the worker's own SSH target (this same STAR_DISCORD_SSH).
  mkdir -p "$HOME/.star"
  if [ ! -s "$HOME/.star/gpu-worker.key" ]; then
    (umask 077; head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$HOME/.star/gpu-worker.key")
    echo "created ~/.star/gpu-worker.key"
  fi
  [ -s "$HOME/.star/gpu-worker.env" ] || printf 'STAR_GPU_WORKER_SSH=%s\nSTAR_GPU_WORKER_CONTAINER=%s\n' "$target" "$container" > "$HOME/.star/gpu-worker.env"
  for name in discord.env discord-settings.env server_api_key gpu-worker.key; do
    file="$HOME/.star/$name"
    [ -f "$file" ] || { echo "missing $file" >&2; exit 2; }
    push_secret "$name" < "$file"
    echo "copied $name"
  done
  remote "ls -l $base/secrets | awk 'NR>1{print \$1, \$3, \$NF}'"
  ;;
doctor)
  remote "cd $base/current && runuser -u star-discord -- env STAR_DISCORD_HOST=server STAR_DISCORD_CONFIG_DIR=$base/secrets XDG_DATA_HOME=$base/state HOME=$base/state $base/venv/bin/python -m star.discord_bot doctor"
  ;;
start|stop)
  remote "systemctl $cmd $unit"
  remote "systemctl is-active $unit" || true
  ;;
status)
  remote "systemctl status $unit --no-pager -n 0 | head -n 12" || true
  remote "echo current: \$(readlink $base/current); echo previous: \$(readlink $base/previous 2>/dev/null || echo none)"
  remote "journalctl -u $unit --no-pager -n 15 -o short-iso" || true
  ;;
rollback)
  remote "cd $base && test -L previous" || { echo "no previous release to roll back to" >&2; exit 2; }
  remote "cd $base && cur=\$(readlink current); prev=\$(readlink previous); ln -sfn \"\$prev\" current; ln -sfn \"\$cur\" previous; echo current: \$prev"
  remote "install -m 644 $base/current/server/discord/$unit /etc/systemd/system/$unit && systemctl daemon-reload"
  if running; then remote "systemctl restart $unit"; echo "restarted"; fi
  ;;
*)
  sed -n '2,24p' "$0"; exit 2
  ;;
esac
