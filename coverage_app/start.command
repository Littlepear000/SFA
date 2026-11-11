#!/usr/bin/env bash
# macOS: double-click this file in Finder to start the DSA coverage app (it opens the browser).
# In the Terminal window:  r + Enter = restart the app (picks up code changes; then refresh the browser tab)
#                          q + Enter = quit        (Ctrl+C or closing the window also quits)
cd "$(dirname "$0")/.." || exit 1   # the project folder, so relative paths in the code resolve

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  # Finder starts this without your shell setup, so also look where Anaconda / Homebrew usually live
  for p in python3 python "$HOME/anaconda3/bin/python" "$HOME/miniconda3/bin/python" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c "import pandas, openpyxl" >/dev/null 2>&1; then PYTHON="$p"; break; fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "No Python with pandas and openpyxl found. Install them (python3 -m pip install pandas openpyxl),"
  echo "or run:  PYTHON=/path/to/python \"$0\""
  read -r -p "Press Enter to close." _
  exit 1
fi
echo "Using $PYTHON"

PID=""
start_app() {           # $@: extra options for server.py
  "$PYTHON" -u coverage_app/server.py "$@" &
  PID=$!
}
stop_app() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null
    wait "$PID" 2>/dev/null
  fi
  PID=""
}
trap 'stop_app; exit 0' INT TERM HUP

start_app "$@"           # first start opens the browser
sleep 1
echo
echo "Type r + Enter to restart, q + Enter to quit."

while true; do
  if ! read -r cmd; then stop_app; exit 0; fi   # input closed (window closed)
  case "$cmd" in
    r|R)
      echo "Restarting…"
      stop_app
      start_app "$@" --no-browser                # the browser tab stays open; refresh it
      sleep 1
      echo "Restarted. Refresh the browser tab. (r = restart, q = quit)"
      ;;
    q|Q)
      stop_app
      echo "Stopped."
      exit 0
      ;;
    "")
      ;;
    *)
      echo "r = restart, q = quit"
      ;;
  esac
  if [ -n "$PID" ] && ! kill -0 "$PID" 2>/dev/null; then
    echo "The app is not running (it stopped with an error above). Fix it, then type r + Enter to start it again."
    PID=""
  fi
done
