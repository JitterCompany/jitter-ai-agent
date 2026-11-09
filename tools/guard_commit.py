#!/usr/bin/env python3
"""Run the commit-time checks on the agent's commits, the same way the shared git hook does.

Wired as a PreToolUse hook on Bash, next to guard_push.py. Reads the hook JSON on stdin.
When a command runs `git commit`, it calls every `tools/precommit/*.py --staged`, exactly as
git_utils/scripts/pre-commit does, and denies the command when one fails. It has no checks
of its own, so a person with the git hook and an agent without it get the same answer.

For `commit -a` or a pathspec, the scripts see a temporary index with those changes staged,
which is what git would commit. Everything else passes untouched.

A human committing from their own terminal is unaffected: this only sees the agent's Bash calls.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKS = Path(__file__).resolve().parent / "precommit"
sys.path.insert(0, str(CHECKS.parent))

from guard_push import (  # noqa: E402
    DRY_RUN, GIT_FLAG, GIT_OPTION_WITH_VALUE, HELP, RUNS_A_STRING, WRAPPERS, segments, strip_prefix, words,
)

# Options whose value is the next word, so it is not mistaken for a pathspec.
COMMIT_OPTION_WITH_VALUE = {"-m", "--message", "-F", "--file", "-C", "-c", "--reuse-message",
                            "--reedit-message", "--fixup", "--squash", "--author", "--date", "-t",
                            "--template", "--cleanup", "--trailer", "-S", "--gpg-sign"}


def commit_in(tokens, cwd, depth=0):
    """(repo, commit args) when these tokens run `git commit`, else None."""
    tokens = strip_prefix(list(tokens))
    if not tokens:
        return None
    program = tokens[0].rsplit("/", 1)[-1]

    if depth < 3 and program in RUNS_A_STRING:
        for token in tokens[1:]:
            for piece in segments(token):
                found = commit_in(words(piece), cwd, depth + 1)
                if found:
                    return found
        return None

    if program in WRAPPERS:
        for index, token in enumerate(tokens[1:], start=1):
            previous = tokens[index - 1]
            if previous.startswith("-") and "=" not in previous:
                continue
            name = token.rsplit("/", 1)[-1]
            if name in RUNS_A_STRING or name in WRAPPERS or name == "git":
                return commit_in(tokens[index:], cwd, depth)
        return None

    if program != "git" or DRY_RUN & set(tokens) or HELP & set(tokens):
        return None
    rest = tokens[1:]
    repo = cwd
    while rest and (rest[0] in GIT_OPTION_WITH_VALUE or rest[0] in GIT_FLAG or rest[0].startswith("--git-dir=")):
        if rest[0] == "-C" and len(rest) > 1:
            repo = os.path.join(repo, os.path.expanduser(rest[1]))
        rest = rest[2:] if rest[0] in GIT_OPTION_WITH_VALUE else rest[1:]
    if rest[:1] != ["commit"]:
        return None
    return repo, rest[1:]


def takes_unstaged(args):
    """Does this commit also take working-tree changes, through -a or a pathspec?"""
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in COMMIT_OPTION_WITH_VALUE:
            skip = True
        elif arg in ("--all", "--") or not arg.startswith("-"):
            return True
        elif not arg.startswith("--"):
            # A cluster such as -am: letters up to the first one that takes a value.
            for i, ch in enumerate(arg[1:], start=1):
                if ch == "a":
                    return True
                if "-" + ch in COMMIT_OPTION_WITH_VALUE:
                    skip = i == len(arg) - 1
                    break
    return False


def run_checks(repo, args):
    """stderr of every failing check, or "" when the commit may go ahead."""
    env = dict(os.environ)
    with tempfile.TemporaryDirectory() as tmp:
        if takes_unstaged(args):
            index = subprocess.run(["git", "-C", repo, "rev-parse", "--git-path", "index"],
                                   capture_output=True, text=True, check=False).stdout.strip()
            env["GIT_INDEX_FILE"] = os.path.join(tmp, "index")
            shutil.copyfile(os.path.join(repo, index), env["GIT_INDEX_FILE"])
            subprocess.run(["git", "-C", repo, "add", "-u"], env=env, capture_output=True, check=False)
        failed = []
        for script in sorted(CHECKS.glob("*.py")):
            done = subprocess.run([sys.executable, str(script), "--staged"], cwd=repo, env=env,
                                  capture_output=True, text=True, check=False)
            if done.returncode:
                failed.append((done.stderr or done.stdout).strip())
    return "\n".join(failed)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()

    for segment in segments(command):
        target = commit_in(words(segment), cwd)
        if not target:
            continue
        failed = run_checks(*target)
        if failed:
            json.dump({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "The commit-time checks failed:\n" + failed,
            }}, sys.stdout)
            return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001, a broken guard must never block every Bash call
        sys.exit(0)
