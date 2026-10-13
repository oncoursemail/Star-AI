#!/bin/bash
# Apply (or roll back) the proposed STAR Brain configuration. Run from the PC in Git Bash:
#
#   bash server/setup/proposed/apply.sh check      # change nothing: validate the files against the server
#   bash server/setup/proposed/apply.sh            # measure, apply, measure again, print the comparison
#   bash server/setup/proposed/apply.sh rollback   # restore the unit + models.ini saved by the last apply
#   bash server/setup/proposed/apply.sh status     # what is loaded, with which threads, on which memory nodes
#
# What "apply" does, in order:
#   1. takes the SERVER LOCK (/opt/star/lock) so no other agent measures or restarts at the same time
#   2. runs validate.py against the live brain            -> validate-before.json
#   3. copies models.ini, star-brain.service and star-brain-prestart.sh into /opt/star/setup-proposed
#   4. pre-flight inside the container (files exist, every models.ini key is a real llama-server option, RAM)
#   5. backs up the live unit + models.ini to /opt/star/config/backups/<UTC time>/
#   6. moves the newly chosen model files from /opt/star/models-candidates into /opt/star/models (same disk: instant)
#   7. installs the three files, daemon-reload, restart; waits until every load-on-startup model reports "loaded"
#   8. if that fails: restores the backup and restarts (automatic rollback)
#   9. runs validate.py again                             -> validate-after.json, then prints the comparison
#  10. releases the lock
# The API key never leaves its files. Nothing outside the starai container is touched.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOST=${STAR_SSH_HOST:?set STAR_SSH_HOST=user@brain-host}
CONTAINER=${STAR_CONTAINER:-starai}
BASE=${STAR_BRAIN_URL:?set STAR_BRAIN_URL=http://brain:8080}
MODELS=${STAR_VALIDATE_MODELS:-star-fast,star-voice}
MODE=${1:-apply}

remote() { # remote <MODE> [extra env assignments]   (reads the script to run from stdin)
  local m=$1; shift
  ssh -o BatchMode=yes "$HOST" "lxc exec $CONTAINER -- env MODE=$m $* bash -s"
}
run_remote() { remote "$@" < "$HERE/apply-remote.sh"; }
stage_and() { # stage_and <MODE>: ship the three files (base64 inside the script, checked by md5) and run the remote half
  {
    echo 'set -u; STAGE=/opt/star/setup-proposed; mkdir -p "$STAGE"'
    for f in models.ini star-brain.service star-brain-prestart.sh; do
      echo "base64 -d > \"\$STAGE/$f\" <<'STAR_B64_EOF'"
      base64 -w 76 "$HERE/$f"
      echo 'STAR_B64_EOF'
      echo "[ \"\$(md5sum < \"\$STAGE/$f\" | cut -d' ' -f1)\" = \"$(md5sum < "$HERE/$f" | cut -d' ' -f1)\" ] || { echo '[apply] ERROR: $f was damaged in transfer'; exit 1; }"
    done
    cat "$HERE/apply-remote.sh"
  } | remote "$1"
}
find_python() {
  for c in "${PYTHON:-}" "$HERE/../../../worktrees/pr39/.venv-audit/Scripts/python.exe" python3 python py; do
    [ -n "$c" ] || continue
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then echo "$c"; return 0; fi
  done
  return 1
}
validate() { # validate <tag>
  local py
  if py=$(find_python); then
    "$py" "$HERE/bench/validate.py" --base "$BASE" --models "$MODELS" --tag "$1" || echo "[apply] validate.py reported a problem for '$1' (see above)"
  else
    echo "[apply] no Python 3.8+ found (set PYTHON=...); skipping the '$1' measurement"
  fi
}

for f in models.ini star-brain.service star-brain-prestart.sh apply-remote.sh bench/validate.py; do
  [ -s "$HERE/$f" ] || { echo "[apply] missing $HERE/$f"; exit 1; }
done

case "$MODE" in
  check)
    stage_and check
    ;;
  status)
    run_remote status
    ;;
  rollback)
    run_remote rollback "${2:+STAMP=$2}"
    rc=$?
    run_remote unlock
    exit $rc
    ;;
  apply)
    trap 'run_remote unlock' EXIT
    run_remote lock || exit 1
    validate before
    stage_and apply
    rc=$?
    if [ $rc -eq 0 ]; then
      validate after
      if py=$(find_python) && [ -s "$HERE/bench/validate-before.json" ] && [ -s "$HERE/bench/validate-after.json" ]; then
        "$py" "$HERE/bench/validate.py" --compare "$HERE/bench/validate-before.json" "$HERE/bench/validate-after.json"
      fi
      echo "[apply] done. If the numbers are worse than before: bash $0 rollback"
    else
      echo "[apply] apply failed (exit $rc); the previous configuration was restored if the restart had already happened."
    fi
    exit $rc
    ;;
  *)
    echo "usage: bash apply.sh [check|apply|rollback [backup-id]|status]"; exit 2
    ;;
esac
