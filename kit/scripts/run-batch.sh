#!/usr/bin/env bash
# One-shot start for an unattended batch (scripts/batch.py) in its own tmux session.
#
#   scripts/run-batch.sh        # 4 issues
#   scripts/run-batch.sh 2      # 2 issues (a leading number is the --max-issues limit)
#   scripts/run-batch.sh --contains "login page"     # no number: default of 4
#   scripts/run-batch.sh 2 --contains "login page"   # extra args go to batch.py (dry run and batch)
#   scripts/run-batch.sh 6 --epic 147                 # only the issues of epic #147, in its order
#
# Running it again while a batch is active just takes you back to it; a finished one is replaced.
# Detach: Ctrl-b d   ·   stop after the current issue: touch .batch/STOP
# Full output is also written to .batch/batch-<date>.log
set -euo pipefail

N=4
if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  N="$1"
  shift
fi
# printf with no arguments would still print one quoted empty string (' '') and break argparse.
EXTRA=""
if [ $# -gt 0 ]; then
  EXTRA="$(printf ' %q' "$@")"
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTEGRATION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["integration_branch"])' "$ROOT/.claude/workflow.json")"
SESSION="batch-$(basename "$ROOT" | tr '[:upper:].' '[:lower:]_')"

attach() {
  if [ -n "${TMUX:-}" ]; then
    tmux switch-client -t "$SESSION"
  else
    exec tmux attach -t "$SESSION"
  fi
}

# True while a batch.py runs from this repo (its cwd is $ROOT), dry runs included. Matches the
# python process only: the tmux window's own `bash -c "… scripts/batch.py …"` outlives the batch.
batch_running() {
  local pid
  for pid in $(pgrep -f '^[^ ]*python[0-9.]* [^ ]*scripts/batch\.py' || true); do
    [ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" = "$ROOT" ] && return 0
  done
  return 1
}

if tmux has-session -t "$SESSION" 2>/dev/null; then
  if batch_running; then
    echo "Batch session '$SESSION' is already running; attaching."
    attach
    exit 0
  fi
  # A finished batch waits for Enter in its window; replace it instead of re-attaching.
  echo "Batch session '$SESSION' has finished; closing it and starting a new batch."
  tmux kill-session -t "$SESSION"
fi

mkdir -p "$ROOT/.batch"
LOG="$ROOT/.batch/batch-$(date +%Y%m%d-%H%M).log"

tmux new-session -d -s "$SESSION" -c "$ROOT" bash -c "
  {
    echo '== Dry run: what the batch will pick =='
    scripts/batch.py --dry-run --max-issues $N$EXTRA
    echo
    echo '== Batch: $N issue(s) =='
    scripts/batch.py --max-issues $N$EXTRA
  } 2>&1 | tee '$LOG'
  echo
  echo 'Batch finished. Log: $LOG'
  echo 'Review: git log --oneline --first-parent origin/$INTEGRATION..$INTEGRATION'
  echo 'Press Enter to close this window.'
  read -r
"

echo "Started batch of $N issue(s) in tmux session '$SESSION' (log: $LOG)."
attach
