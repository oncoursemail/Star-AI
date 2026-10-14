#!/usr/bin/env bash
# PREPARED, NOT RUN. Switch the knowledge service to the fine-tuned embedding model, with a one-command rollback.
# Run by hand only after the owner/lead agrees (docs/agents/gpu-training-pilot.md has the evidence).
#
#   STAR_SERVER_SSH=<user@host> bash deploy_embed_ft.sh stage  <local Q8_0.gguf>   # copy model + router entry (no restart)
#   STAR_SERVER_SSH=<user@host> bash deploy_embed_ft.sh embed                      # embed the index with the new model (resumable, duty 0.5)
#   STAR_SERVER_SSH=<user@host> bash deploy_embed_ft.sh switch                     # knowledge service + refresh use the new model
#   STAR_SERVER_SSH=<user@host> bash deploy_embed_ft.sh rollback                   # back to star-embed (old vectors are kept)
#
# Design: the new model gets its OWN router alias (star-embed-ft1) and its vectors are stored in the same index under
# that model name, next to the existing `star-embed` rows (embeddings PRIMARY KEY is (text_sha, model)). The service
# reads STAR_EMBED_MODEL (starkb/client.py), so switching and rolling back are a systemd drop-in plus a restart of
# star-knowledge only. Nothing is deleted. Adding a router model needs a star-brain restart (models.ini is read at start,
# and --models-max must be raised by one): do it in a quiet window and hold the server lock.
set -euo pipefail
HOST="${STAR_SERVER_SSH:?set STAR_SERVER_SSH=user@host}"
ALIAS=star-embed-ft1
DIR=/opt/star/models/embeddinggemma-300m-star-ft1
FILE=embeddinggemma-300m-star-ft1-Q8_0.gguf
run() { ssh -o BatchMode=yes "$HOST" "lxc exec starai -- bash -c $(printf %q "$1")"; }

case "${1:-}" in
  stage)
    src="${2:?local gguf path}"
    run "mkdir -p $DIR && chown star:star $DIR"
    ssh -o BatchMode=yes "$HOST" "lxc exec starai -- tee $DIR/$FILE >/dev/null" < "$src"
    run "chown star:star $DIR/$FILE && sha256sum $DIR/$FILE"
    run "grep -q '^\[$ALIAS\]' /opt/star/config/models.ini || { cp /opt/star/config/models.ini /opt/star/config/models.ini.bak-\$(date -u +%Y%m%d%H%M); printf '\n[%s]\nmodel = %s\nembedding = true\nthreads = 8\nthreads-batch = 8\nload-on-startup = true\n' $ALIAS $DIR/$FILE >> /opt/star/config/models.ini; }"
    echo "staged. NEXT (by hand, quiet window): raise --models-max by 1 in star-brain.service, then systemctl restart star-brain"
    ;;
  embed)
    run "cd /opt/star/knowledge/app && sudo -u star env STAR_KB_HOME=/opt/star/knowledge STAR_EMBED_MODEL=$ALIAS /opt/star/knowledge/venv/bin/python -m starkb embed --duty 0.5"
    ;;
  switch)
    for unit in star-knowledge star-knowledge-refresh; do
      run "mkdir -p /etc/systemd/system/$unit.service.d && printf '[Service]\nEnvironment=STAR_EMBED_MODEL=$ALIAS\n' > /etc/systemd/system/$unit.service.d/embed-ft1.conf"
    done
    run "systemctl daemon-reload && systemctl restart star-knowledge && sleep 5 && systemctl is-active star-knowledge"
    echo "switched. Check: python -m starkb eval (dev 30) on the server; expect the PC numbers in gpu-training-pilot.md"
    ;;
  rollback)
    run "rm -f /etc/systemd/system/star-knowledge.service.d/embed-ft1.conf /etc/systemd/system/star-knowledge-refresh.service.d/embed-ft1.conf && systemctl daemon-reload && systemctl restart star-knowledge && systemctl is-active star-knowledge"
    echo "rolled back to star-embed (its vectors were never touched)"
    ;;
  *) sed -n 2,16p "$0"; exit 2 ;;
esac
