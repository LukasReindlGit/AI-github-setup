#!/usr/bin/env python3
"""Open or update a GitHub issue when unattended automation fails .

Used by scripts/batch.py (abnormal batch stops); other scripts may call it with a new kind.
One open issue per kind: if an open issue with the kind's title prefix exists, a comment is added
instead of a second issue. The issues get `bug` + `P0`, are not added to the backlog and get no
`model:*` label, so the batch never picks them up.

Alerting never breaks what it reports on: any failure (no `gh`, no network, not logged in) is
printed and ignored, and the exit code is always 0.

    echo "body" | scripts/alert_issue.py batch "reason the batch stopped"

Off switch (default on): `git config claudekit.alertIssues false`, or
CLAUDE_KIT_ALERT_ISSUES=0 in the environment.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = {
    "batch": "[auto] Batch stopped:",
}
LABELS = ("bug", "P0")
OFF = {"0", "false", "no", "off"}


def _run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)


def enabled():
    env = os.environ.get("CLAUDE_KIT_ALERT_ISSUES")
    if env is not None:
        return env.strip().lower() not in OFF
    try:
        value = _run("git", "config", "--get", "claudekit.alertIssues").stdout
    except (OSError, subprocess.SubprocessError):
        value = ""
    return value.strip().lower() not in OFF


def find_open(prefix, titles):
    """Number of the first open issue whose title starts with prefix, from gh's JSON list."""
    for issue in titles:
        if issue.get("title", "").startswith(prefix):
            return issue["number"]
    return None


def alert(kind, title, body):
    """Open or comment on the kind's issue. Returns a one-line report; never raises."""
    if not enabled():
        return "alert issues disabled"
    prefix = PREFIXES[kind]
    full_title = f"{prefix} {title}"
    try:
        # The plain list API, not --search: the search index lags behind new issues, so two
        # failures in quick succession would each open an issue.
        listed = _run(
            "gh", "issue", "list", "--state", "open", "--label", LABELS[1],
            "--json", "number,title", "--limit", "200",
        )  # fmt: skip
        if listed.returncode != 0:
            return f"alert failed: gh issue list: {listed.stderr.strip()[:200]}"
        existing = find_open(prefix, json.loads(listed.stdout or "[]"))
        if existing:
            out = _run(
                "gh", "issue", "comment", str(existing), "--body", f"**{full_title}**\n\n{body}"
            )
            what = f"commented on #{existing}"
        else:
            labels = [arg for label in LABELS for arg in ("--label", label)]
            out = _run("gh", "issue", "create", "--title", full_title, "--body", body, *labels)
            what = "opened issue"
        if out.returncode != 0:
            return f"alert failed: {out.stderr.strip()[:200]}"
        return f"alert: {what} {out.stdout.strip()}".rstrip()
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return f"alert failed: {exc}"


def main(argv):
    if len(argv) != 3 or argv[1] not in PREFIXES:
        print(f"usage: {argv[0]} {'|'.join(PREFIXES)} <title>  (body on stdin)", file=sys.stderr)
        return 0
    print(alert(argv[1], argv[2], sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
