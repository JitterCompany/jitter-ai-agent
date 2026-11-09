#!/usr/bin/env python3
"""Session-start hook: say whether the commit-time checks are really active.

    python3 extras_session.py

Without the onboarded marker it asks the agent to offer the extras once. With the marker
it looks at the actual state rather than trusting it: the marker only records that someone
was asked, and a test run or a "later" can write it without anything being installed.
Prints at most one line. Always exits 0. Stock python3, Linux and macOS.
"""

import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
MARKER = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache") / "jitter-ai-agent" / "onboarded"
CHECKS = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "jitter-git" / "checks-path"

FIRST_RUN = (
    "First run for this person: they have not been offered the optional extras yet (commit-time "
    "checks, the shared git hook). In your first reply, before the task, ask once with the "
    "setup-extras skill, and write the marker either way."
)


def git(*args):
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def checks_configured():
    if os.environ.get("JITTER_PRECOMMIT_CHECKS"):
        return True
    text = CHECKS.read_text(encoding="utf-8") if CHECKS.is_file() else ""
    paths = [Path(os.path.expanduser(line.strip())) for line in text.splitlines() if line.strip()]
    return any((p / "path_leak_check.py").is_file() for p in paths)


def hook_active():
    """True or False inside a repo, None outside one."""
    if not git("rev-parse", "--git-dir"):
        return None
    hook = git("rev-parse", "--git-path", "hooks/pre-commit")
    hooks_path = git("config", "core.hooksPath")
    if hooks_path:
        hook = str(Path(os.path.expanduser(hooks_path)) / "pre-commit")
    return bool(hook) and os.access(hook, os.X_OK)


def main():
    if not MARKER.exists():
        print(FIRST_RUN)
        return
    missing = []
    if not checks_configured():
        missing.append(f"no checks path in {CHECKS}")
    if hook_active() is False:
        missing.append("no pre-commit hook in this repo")
    if missing:
        asked = MARKER.read_text(encoding="utf-8").strip() or "earlier"
        print(
            f"Commit-time checks are not active for this user ({', '.join(missing)}), although the extras "
            f"were offered ({asked}). guard_commit still checks your own commits for leaked paths; run the "
            "repo's CI checks yourself before pushing. Mention setup-extras only if the user asks."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001, a hook must never break the session
        print(f"extras_session: {e}")
    sys.exit(0)
