#!/bin/bash
# Control the training-data generator INSIDE the server container (run as root, or through deploy.sh --ctl).
#   trainctl.sh start|stop|restart|status|pause|resume|report|logs|lock-status
set -eu
HOME_DIR=/opt/star/training
UNIT=star-training-gen
PY=/usr/bin/python3
run_as_star() { runuser -u star -- env STAR_TRAIN_HOME="$HOME_DIR" "$@"; }
case "${1:-status}" in
  start)   systemctl start "$UNIT"; sleep 2; systemctl is-active "$UNIT" ;;
  stop)    systemctl stop "$UNIT"; echo stopped ;;
  restart) systemctl restart "$UNIT"; sleep 2; systemctl is-active "$UNIT" ;;
  pause)   run_as_star touch "$HOME_DIR/PAUSE"; echo "paused (the service keeps running and waits)" ;;
  resume)  rm -f "$HOME_DIR/PAUSE"; echo resumed ;;
  status)
    systemctl is-active "$UNIT" || true
    [ -e "$HOME_DIR/PAUSE" ] && echo "PAUSE file present" || true
    [ -e /opt/star/lock ] && echo "server quiet lock present" || true
    cd "$HOME_DIR/app" && run_as_star "$PY" -m startrain status ;;
  report)  cd "$HOME_DIR/app" && run_as_star "$PY" -m startrain report && cat "$HOME_DIR/data/report.md" ;;
  logs)    journalctl -u "$UNIT" --no-pager -n "${2:-40}" ;;
  *) echo "usage: trainctl.sh start|stop|restart|status|pause|resume|report|logs [n]"; exit 2 ;;
esac
