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
UPDATE_OFFERED = MARKER.with_name("update-offered")

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


def hook_file():
    """The pre-commit hook git would run here, or None outside a repo."""
    if not git("rev-parse", "--git-dir"):
        return None
    hooks_path = git("config", "core.hooksPath")
    if hooks_path:
        return Path(os.path.expanduser(hooks_path)) / "pre-commit"
    return Path(git("rev-parse", "--git-path", "hooks/pre-commit"))


def hook_active():
    """True or False inside a repo, None outside one."""
    hook = hook_file()
    return None if hook is None else os.access(hook, os.X_OK)


def clone_state(folder):
    """(top level, branch, commits behind the last fetch) of the clone holding folder."""
    top = git("-C", str(folder), "rev-parse", "--show-toplevel")
    if not top:
        return None
    branch = git("-C", top, "symbolic-ref", "--short", "HEAD")
    behind = git("-C", top, "rev-list", "--count", "HEAD..@{upstream}")
    return top, branch, int(behind or 0)


def outdated():
    """What makes a setup the person accepted quietly do less than it should. No network."""
    problems = []
    hook = hook_file()
    if hook is not None and hook.is_file():
        real = hook.resolve()
        state = clone_state(real.parent)
        if state and "git_utils" in git("-C", state[0], "remote", "get-url", "origin"):
            if "checks-path" not in real.read_text(encoding="utf-8", errors="replace"):
                problems.append(f"the git_utils hook in {state[0]} is too old to run the shared checks")
            elif state[2]:
                problems.append(f"the git_utils clone {state[0]} is {state[2]} commits behind its last fetch")
    text = CHECKS.read_text(encoding="utf-8") if CHECKS.is_file() else ""
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        path = Path(os.path.expanduser(line.strip()))
        if not path.exists():
            problems.append(f"checks-path entry {path} no longer exists")
            continue
        state = clone_state(path if path.is_dir() else path.parent)
        if state and state[1] not in ("master", "main", ""):
            problems.append(f"checks-path entry {path} is a clone on branch {state[1]}, not master")
    return problems


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
        return
    problems = outdated()
    report = "; ".join(problems)
    offered = UPDATE_OFFERED.read_text(encoding="utf-8").strip() if UPDATE_OFFERED.is_file() else ""
    if problems and report != offered:
        UPDATE_OFFERED.write_text(report + "\n", encoding="utf-8")
        print(
            f"The commit-time setup this person accepted is out of date: {report}. Offer once to update "
            "it, with the setup-extras skill (Keep it current), and take a no."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001, a hook must never break the session
        print(f"extras_session: {e}")
    sys.exit(0)
