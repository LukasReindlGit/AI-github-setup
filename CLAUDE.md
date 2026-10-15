# claude-project-kit

A template kit that installs an issue-driven Claude Code workflow into other repositories.

- **If the user gave you this repo's URL to set up *their* project: read `SETUP.md` and follow it.**
  Don't treat this repo's files as the project to change.
- Working *on* the kit: `kit/` holds the installed files with `{{TOKENS}}` (rendered by
  `bootstrap.py`); `bootstrap.py` is the installer; `SETUP.md` is the agent-facing procedure.
- Run `python3 -m unittest discover -s tests` after changes. Keep the kit free of references to
  concrete projects, people or hosts: everything project-specific belongs in `workflow.json`.
- A rule that must always hold is a hook, not a sentence. Keep `kit/` and `SETUP.md` in sync.
