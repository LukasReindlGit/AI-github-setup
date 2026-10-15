#!/usr/bin/env python3
"""Install the claude-project-kit workflow into a git repository.

    python3 /path/to/claude-project-kit/bootstrap.py --target . [options]

Idempotent: run it again and nothing that exists is overwritten, except kit-owned files with
--update. Everything it would do is shown first with --dry-run. Needs only Python 3.8+ and git;
`gh` (logged in) is needed for --create-labels / --create-backlog.

What gets installed (see SETUP.md for the full picture and the questions to ask the human):

  kit-owned, refreshed by --update      project-owned, created once, never overwritten
  .claude/hooks/*                       .claude/workflow.json   (all settings)
  .claude/skills/{next,logs}/           scripts/check.sh        (the CI mirror, to be refined)
  scripts/{batch.py,run-batch.sh,...}   .github/ISSUE_TEMPLATE/*
  .github/workflows/close-merged-...    docs/GIT_WORKFLOW.md, docs/ai/README.md

  merged, never replaced: .claude/settings.json, CLAUDE.md (marked block), .gitignore
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
TEMPLATES = KIT / "kit"
VERSION = (KIT / "VERSION").read_text().strip() if (KIT / "VERSION").exists() else "0"

KIT_OWNED = [
    ".claude/hooks/guard_git.py",
    ".claude/hooks/test_guard_git.py",
    ".claude/hooks/format_on_edit.py",
    ".claude/skills/next/SKILL.md",
    ".claude/skills/logs/SKILL.md",
    "scripts/batch.py",
    "scripts/alert_issue.py",
    "scripts/run-batch.sh",
    "scripts/batch-report.sh",
    ".github/workflows/close-merged-issues.yml",
]
PROJECT_OWNED = [
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    "docs/GIT_WORKFLOW.md",
    "docs/ai/README.md",
]
EXECUTABLE = {".py", ".sh"}

LABELS = [
    ("P0", "B60205", "Now"),
    ("P1", "D93F0B", "Next"),
    ("P2", "FBCA04", "Later"),
    ("P3", "C2E0C6", "Someday"),
    ("needs-decision", "D93F0B", "Blocked on a human decision; agents never start these"),
    ("on-hold", "CCCCCC", "Parked by the product owner; never picked until reactivated"),
    ("tracking", "BFDADC", "Epic/tracking issue; not worked directly"),
    ("security", "000000", "Security/privacy relevant"),
    ("documentation", "0075CA", "Documentation only"),
    ("ai-in-progress", "FBCA04", "Claimed by a Claude session"),
    ("ai-merged", "0E8A16", "Done in the agent integration branch, waiting for the human push + PR"),
    ("rework", "AAAAAA", "AI result sent back; see the rework comment. Worked first"),
    ("model:sonnet", "C5DEF5", "Batch runner uses Sonnet for this issue"),
    ("model:opus", "5319E7", "Batch runner uses Opus for this issue"),
]

BACKLOG_BODY = """**This issue is the single source of truth for priorities.** The order of the lists *is* the priority.
Agents (`/next`, `scripts/batch.py`) walk **Now**, then **Next**, top to bottom. Keep one line per
issue as `- [ ] #<n> Title`; add *needs approval* / *server access* / ⚠️ to a line to keep agents off it.

## 🔥 Now (P0)

## ⏭️ Next (P1)

## 🕐 Later (P2)

## 🧭 Needs decision: do not start
"""

BLOCK_START = "<!-- claude-project-kit:start (managed by bootstrap.py; edit outside the markers) -->"
BLOCK_END = "<!-- claude-project-kit:end -->"


class Run:
    def __init__(self, dry):
        self.dry = dry
        self.done = []

    def note(self, what, path=""):
        self.done.append((what, str(path)))
        print(f"{'would ' if self.dry else ''}{what:<9} {path}")

    def write(self, path, text, what="create", exe=False):
        self.note(what, path)
        if self.dry:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if exe:
            path.chmod(0o755)


def sh(*cmd, cwd=None, check=False):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if check and out.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed: {out.stderr.strip()}")
    return out.stdout.strip() if out.returncode == 0 else None


# ---------- detection ----------


def detect_base(target):
    head = sh("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=target)
    if head:
        return head.split("/", 1)[-1]
    for name in ("main", "master", "develop"):
        if sh("git", "rev-parse", "--verify", "-q", name, cwd=target):
            return name
    return sh("git", "branch", "--show-current", cwd=target) or "main"


def detect_repo(target):
    url = sh("git", "remote", "get-url", "origin", cwd=target) or ""
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?$", url)
    return m[1] if m else None


def detect_check(target):
    """Best-effort commands for scripts/check.sh. Claude is expected to refine them."""
    cmds, notes = [], []
    pkg = target / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text()).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        tool = "npm"
        if (target / "pnpm-lock.yaml").exists():
            tool = "pnpm"
        elif (target / "yarn.lock").exists():
            tool = "yarn"
        for name in ("lint", "typecheck", "build", "test"):
            if name in scripts:
                cmds.append(f"{tool} run {name}")
        notes.append(f"package.json scripts: {', '.join(scripts) or 'none'}")
    if (target / "pyproject.toml").exists() or (target / "setup.py").exists():
        text = (target / "pyproject.toml").read_text() if (target / "pyproject.toml").exists() else ""
        if "ruff" in text:
            cmds += ["ruff check .", "ruff format --check ."]
        if (target / "tests").is_dir() or "pytest" in text:
            cmds.append("python3 -m pytest -q")
    if (target / "go.mod").exists():
        cmds += ["go vet ./...", "go test ./..."]
    if (target / "Cargo.toml").exists():
        cmds += ["cargo clippy -- -D warnings", "cargo test"]
    if not cmds and (target / "Makefile").exists():
        mk = (target / "Makefile").read_text()
        for name in ("lint", "test", "check"):
            if re.search(rf"^{name}:", mk, re.M):
                cmds.append(f"make {name}")
    return cmds, notes


def detect_format(target):
    fmt = {}
    pyproject = target / "pyproject.toml"
    if pyproject.exists() and "ruff" in pyproject.read_text():
        fmt[".py"] = "ruff format --quiet {file}"
    if (target / "package.json").exists():
        text = (target / "package.json").read_text()
        if "prettier" in text:
            for ext in (".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".md"):
                fmt[ext] = "npx --no-install prettier --write {file}"
    if (target / "go.mod").exists():
        fmt[".go"] = "gofmt -w {file}"
    if (target / "Cargo.toml").exists():
        fmt[".rs"] = "rustfmt {file}"
    return fmt


# ---------- rendering ----------


def tokens(args, base, repo, cfg):
    protected = list(dict.fromkeys([*cfg["protected_branches"], base]))
    names = ", ".join(f"`{b}`" for b in protected)
    if args.allow_push:
        push_rule = "push only the `" + cfg["integration_branch"] + "` and topic branches (allow_push)."
        push_bullet = "push to a protected branch (pushing the integration and topic branches is allowed)"
        push_note = " to protected branches"
    else:
        push_rule = "**never push** (the human does)."
        push_bullet = (
            "**push**. The human always does that; the agent leaves branches that go up with a "
            "plain `git push -u origin <branch>`"
        )
        push_note = ""
    return {
        "BASE": base,
        "INTEGRATION": cfg["integration_branch"],
        "PREFIX": cfg["branch_prefix"],
        "BACKLOG": str(cfg["backlog_issue"] or "<backlog>"),
        "CHECK": cfg["check_command"],
        "REPO": repo or "<owner>/<repo>",
        "PROTECTED_LIST": names,
        "PUSH_RULE": push_rule,
        "PUSH_BULLET": push_bullet,
        "PUSH_NOTE": push_note,
        "KIT_URL": args.kit_url,
    }


def render(text, toks):
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: toks.get(m[1], m[0]), text)


def render_json(obj, toks):
    if isinstance(obj, str):
        return render(obj, toks)
    if isinstance(obj, list):
        return [render_json(x, toks) for x in obj]
    if isinstance(obj, dict):
        return {k: render_json(v, toks) for k, v in obj.items()}
    return obj


# ---------- installation steps ----------


def install_files(run, target, toks, update, force):
    for rel in KIT_OWNED + PROJECT_OWNED:
        src, dst = TEMPLATES / rel, target / rel
        text = render((src).read_text(), toks)
        exe = dst.suffix in EXECUTABLE
        if not dst.exists():
            run.write(dst, text, "create", exe)
        elif dst.read_text() == text:
            continue
        elif rel in KIT_OWNED and (update or force):
            run.write(dst, text, "update", exe)
        elif force:
            run.write(dst, text, "overwrite", exe)
        else:
            run.note("keep", f"{rel} (exists; --update refreshes kit-owned files)")


def install_config(run, target, cfg, toks, update):
    path = target / ".claude" / "workflow.json"
    if path.exists():
        current = json.loads(path.read_text())
        merged = {**cfg, **current}  # existing values win; new keys are added
        for key in ("triage", "limits"):
            merged[key] = {**cfg.get(key, {}), **current.get(key, {})}
        merged["kit"] = {"url": toks["KIT_URL"], "version": VERSION}
        if merged != current:
            run.write(path, json.dumps(merged, indent=2) + "\n", "update")
        return merged
    cfg = {**cfg, "kit": {"url": toks["KIT_URL"], "version": VERSION}}
    run.write(path, json.dumps(cfg, indent=2) + "\n")
    return cfg


def allow_rules(cfg):
    check = cfg["check_command"]
    rules = [
        f"Bash({check})",
        f"Bash({check} *)",
        "Bash(scripts/batch-report.sh *)",
        "Bash(git status)",
        "Bash(git status *)",
        "Bash(git diff *)",
        "Bash(git log *)",
        "Bash(git show *)",
        "Bash(git branch *)",
        "Bash(git add *)",
        "Bash(git switch *)",
        "Bash(git commit *)",
        "Bash(git merge *)",
        "Bash(git fetch *)",
        "Bash(git merge-base *)",
        "Bash(git rev-parse *)",
        "Bash(gh issue view *)",
        "Bash(gh issue list *)",
        "Bash(gh issue edit *)",
        "Bash(gh issue comment *)",
        "Bash(gh issue create *)",
        "Bash(gh pr view *)",
        "Bash(gh pr list *)",
    ]
    return list(dict.fromkeys(rules))


def install_settings(run, target, cfg):
    path = target / ".claude" / "settings.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data.setdefault("$schema", "https://json.schemastore.org/claude-code-settings.json")
    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    allow += [r for r in allow_rules(cfg) if r not in allow]
    if not cfg.get("allow_push"):
        deny = perms.setdefault("deny", [])
        deny += [r for r in ("Bash(git push)", "Bash(git push *)") if r not in deny]
    hooks = data.setdefault("hooks", {})

    def add(event, matcher, command):
        entries = hooks.setdefault(event, [])
        if any(h.get("command") == command for e in entries for h in e.get("hooks", [])):
            return
        entries.append({"matcher": matcher, "hooks": [{"type": "command", "command": command}]})

    add("PreToolUse", "Bash", 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard_git.py')
    add("PostToolUse", "Edit|Write", 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/format_on_edit.py')
    new = json.dumps(data, indent=2) + "\n"
    if not path.exists():
        run.write(path, new)
    elif path.read_text() != new:
        run.write(path, new, "merge")


def install_claude_md(run, target, toks):
    snippet = render((TEMPLATES / "CLAUDE.snippet.md").read_text(), toks).rstrip()
    block = f"{BLOCK_START}\n{snippet}\n{BLOCK_END}\n"
    path = target / "CLAUDE.md"
    if not path.exists():
        run.write(path, f"# {target.resolve().name}: CLAUDE.md\n\n(Describe the project here: what it is, "
                  f"how to build/run it, gotchas. Keep it short.)\n\n{block}")
        return
    text = path.read_text()
    pattern = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", re.S)
    if pattern.search(text):
        new = pattern.sub(lambda _: block, text)
        if new != text:
            run.write(path, new, "update")
    else:
        run.write(path, text.rstrip() + "\n\n" + block, "append")


def install_gitignore(run, target):
    path = target / ".gitignore"
    text = path.read_text() if path.exists() else ""
    if re.search(r"^/?\.batch/?$", text, re.M):
        return
    run.write(path, text.rstrip("\n") + ("\n" if text else "") + "# claude-project-kit batch logs\n.batch/\n",
              "update" if path.exists() else "create")


def install_check(run, target, args):
    path = target / "scripts" / "check.sh"
    if path.exists():
        return
    cmds, notes = detect_check(target)
    if args.check_cmds:
        cmds = args.check_cmds
    if cmds:
        body = "\n".join(f"echo '==> {c}'\n{c}" for c in cmds)
    else:
        body = (
            "echo 'scripts/check.sh is not configured yet: put exactly what CI runs here' >&2\n"
            "exit 1"
        )
    text = f"""#!/usr/bin/env bash
# Local mirror of CI: run this before every merge. Exit non-zero on any failure.
# Must work from a clean checkout, need no secrets, and accept optional test selectors in "$@"
# (e.g. a test path or name) so single tests can be run quickly. Keep it in sync with CI.
# Detected by claude-project-kit{' (' + '; '.join(notes) + ')' if notes else ''}; refine as needed.
set -euo pipefail
cd "$(dirname "${{BASH_SOURCE[0]}}")/.."

{body}
"""
    run.write(path, text, "create", exe=True)


def gh_ok():
    return sh("gh", "auth", "status") is not None


def create_labels(run, target):
    for name, color, desc in LABELS:
        run.note("label", name)
        if not run.dry:
            sh("gh", "label", "create", name, "--color", color, "--description", desc, "--force", cwd=target)


def create_backlog(run, target):
    run.note("issue", "pinned backlog")
    if run.dry:
        return None
    url = sh(
        "gh", "issue", "create", "--title", "Backlog & priorities",
        "--body", BACKLOG_BODY, cwd=target, check=True,
    )  # fmt: skip
    number = int(url.rstrip("/").rsplit("/", 1)[-1])
    sh("gh", "issue", "pin", str(number), cwd=target)  # best effort; needs a recent gh
    print(f"          backlog issue: {url}")
    return number


# ---------- main ----------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="the repository to set up (default: cwd)")
    ap.add_argument("--base", help="human integration branch the work lands on (default: detected)")
    ap.add_argument("--integration", help="agent integration branch (default: ai/develop)")
    ap.add_argument("--prefix", default="ai/", help="topic branch prefix (default: ai/)")
    ap.add_argument("--protected", default="main,master,develop", help="extra human-only branches")
    ap.add_argument("--allow-push", action="store_true", help="agents may push non-protected branches")
    ap.add_argument("--check", help="check command (default: scripts/check.sh, generated)")
    ap.add_argument("--check-cmd", action="append", dest="check_cmds", metavar="CMD",
                    help="a command for the generated scripts/check.sh (repeatable)")
    ap.add_argument("--description", default="", help="one-line project description for model triage")
    ap.add_argument("--repo", help="owner/name (default: from the origin remote)")
    ap.add_argument("--backlog", type=int, help="number of an existing pinned backlog issue")
    ap.add_argument("--create-backlog", action="store_true", help="create + pin the backlog issue")
    ap.add_argument("--create-labels", action="store_true", help="create the workflow labels (gh)")
    ap.add_argument("--kit-url", default="https://github.com/lukasreindlgit/claude-project-kit")
    ap.add_argument("--update", action="store_true", help="refresh kit-owned files in place")
    ap.add_argument("--force", action="store_true", help="overwrite project-owned files too")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if sh("git", "rev-parse", "--show-toplevel", cwd=target) is None:
        sys.exit(f"{target} is not inside a git repository")
    target = Path(sh("git", "rev-parse", "--show-toplevel", cwd=target))

    base = args.base or detect_base(target)
    existing = target / ".claude" / "workflow.json"
    stored = json.loads(existing.read_text()) if existing.exists() else {}
    repo = args.repo or detect_repo(target) or stored.get("repo")
    cfg = {
        **json.loads((TEMPLATES / ".claude" / "workflow.json").read_text()),
        "base_branch": base,
        "integration_branch": args.integration or "ai/develop",
        "branch_prefix": args.prefix,
        "protected_branches": [b for b in args.protected.split(",") if b],
        "allow_push": args.allow_push,
        "check_command": args.check or "scripts/check.sh",
        "project_description": args.description,
        "backlog_issue": args.backlog,
        "repo": repo,
        "format": detect_format(target),
    }
    if existing.exists():  # re-runs and --update keep the project's own values
        current = json.loads(existing.read_text())
        cfg.update({k: v for k, v in current.items() if v not in (None, "")})
        if args.backlog:
            cfg["backlog_issue"] = args.backlog
    if not cfg["integration_branch"].startswith(cfg["branch_prefix"]):
        sys.exit(f"integration branch '{cfg['integration_branch']}' must start with the prefix "
                 f"'{cfg['branch_prefix']}', so the agent's own branches are recognised")

    run = Run(args.dry_run)
    want_gh = args.create_labels or args.create_backlog
    if want_gh and not args.dry_run and not gh_ok():
        sys.exit("gh is not logged in: run `gh auth login`, or drop --create-labels/--create-backlog")
    if want_gh and not args.dry_run and not repo:
        sys.exit("no GitHub origin remote found: add one or pass --repo owner/name")

    print(f"target {target}\nbase {base}, integration {cfg['integration_branch']}, repo {repo}\n")
    if args.create_labels:
        create_labels(run, target)
    if args.create_backlog and not cfg.get("backlog_issue"):
        cfg["backlog_issue"] = create_backlog(run, target)
    toks = tokens(args, base, repo, cfg)
    install_check(run, target, args)
    install_files(run, target, toks, args.update, args.force)
    cfg = install_config(run, target, render_json(cfg, toks), toks, args.update)
    install_settings(run, target, cfg)
    install_claude_md(run, target, toks)
    install_gitignore(run, target)

    print()
    if not cfg.get("backlog_issue"):
        print("NOTE: no backlog issue yet. Create one (--create-backlog) and set `backlog_issue` in "
              ".claude/workflow.json; /next and the batch runner need it.")
    if not run.dry:
        shutil.rmtree(target / ".claude" / "hooks" / "__pycache__", ignore_errors=True)
    print(f"{'Dry run: ' if run.dry else ''}{len(run.done)} change(s). Next: SETUP.md step 4 (adapt + verify).")


if __name__ == "__main__":
    main()
