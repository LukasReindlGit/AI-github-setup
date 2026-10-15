#!/usr/bin/env bash
# Read-only snapshot of batch runs (scripts/batch.py) for the /logs skill. Changes nothing.
# Usage: scripts/batch-report.sh [log-lines]   (default 30)
set -uo pipefail

LINES="${1:-30}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
INTEGRATION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["integration_branch"])' .claude/workflow.json)"
SESSION="batch-$(basename "$ROOT" | tr '[:upper:].' '[:lower:]_')"

echo "## Now: $(date '+%Y-%m-%d %H:%M')"

echo "## Batch session"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session '$SESSION': RUNNING"
else
  echo "tmux session '$SESSION': not running"
fi
[ -f .batch/STOP ] && echo "STOP file present (batch stops after the current issue)"

LOG=$(ls -t .batch/batch-*.log 2>/dev/null | head -1)
echo "## Latest batch log: ${LOG:-none} (last $LINES lines)"
[ -n "$LOG" ] && tail -n "$LINES" "$LOG" | cut -c1-220

echo "## Runs (last 12; notes shortened)"
if [ -f .batch/runs.tsv ]; then
  echo "time | issue | model | status | minutes | turns | cost | note"
  tail -n +2 .batch/runs.tsv | tail -n 12 |
    awk -F'\t' '{printf "%s | #%s | %s | %s | %s | %s | $%s | %s\n",
      $1, $2, $3, $4, $5, $6, substr($7, 1, 5), substr($8, 1, 140)}'
else
  echo "no runs yet"
fi

echo "## Issues by state"
for label in rework ai-in-progress ai-merged; do
  echo "- $label: $(gh issue list --label "$label" --state open --limit 100 --json number,title \
    --jq 'map("#\(.number) \(.title[0:50])") | join("; ")' 2>/dev/null)"
done
SINCE=$(date -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)
echo "- needs-decision: $(gh issue list --label needs-decision --state open --limit 200 --json number,title,updatedAt \
  --jq "(length | tostring) + \" open; changed in the last 3 days: \" + (map(select(.updatedAt >= \"$SINCE\")) | map(\"#\\(.number) \\(.title[0:50])\") | join(\"; \"))" 2>/dev/null)"

echo "## Unpushed merges on $INTEGRATION"
git log --oneline --first-parent "origin/$INTEGRATION..$INTEGRATION" 2>/dev/null || echo "(no origin/$INTEGRATION)"

echo "## Working tree"
echo "branch: $(git branch --show-current), uncommitted files: $(git status --porcelain | wc -l)"
