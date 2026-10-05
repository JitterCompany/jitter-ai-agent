#!/usr/bin/env python3
"""Stop the agent from committing a local path or personal data (C3).

Wired as a PreToolUse hook on Bash, next to guard_push.py. Reads the hook JSON on stdin.
When a command runs `git commit`, it scans the lines that commit adds with the same rules
as path_leak_check.py, and denies the command on a finding. Everything else passes untouched.

It runs whether or not the repo has a pre-commit hook. The shared hook is optional and often
missing, which is exactly when an agent leaks a path into a repo that has no CI to catch it.
Only added lines count, so an old leak in a file the commit touches does not block it.

A human committing from their own terminal is unaffected: this only sees the agent's Bash calls.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import path_leak_check  # noqa: E402
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


def added_lines(repo, *diff_args):
    """{file: added text} for one `git diff`, skipping what path_leak_check skips."""
    done = subprocess.run(["git", "-C", repo, "diff", "-U0", "--no-color", "--diff-filter=ACMR", *diff_args],
                          capture_output=True, text=True, errors="replace", check=False)
    added, current = {}, None
    for line in done.stdout.splitlines():
        if line.startswith("+++ "):
            name = line[4:].removeprefix("b/")
            skipped = (Path(name).suffix.lower() in path_leak_check.SKIP_SUFFIXES
                       or any(part in path_leak_check.SKIP_DIRS for part in Path(name).parts))
            current = None if name == "/dev/null" or skipped else name
        elif current and line.startswith("+") and not line.startswith("+++"):
            added.setdefault(current, []).append(line[1:])
    return {name: "\n".join(lines) + "\n" for name, lines in added.items()}


def findings_for(repo, args):
    texts = added_lines(repo, "--cached")
    if takes_unstaged(args):
        for name, text in added_lines(repo).items():
            texts[name] = texts.get(name, "") + text
    found = []
    for name, text in texts.items():
        # scan_text numbers lines within the added text only, which would mislead.
        found += [re.sub(r"^(.*?):\d+: ", r"\1: ", f) for f in path_leak_check.scan_text(text, name)]
    return found


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
        found = findings_for(*target)
        if found:
            listed = "\n".join(str(f) for f in found[:10])
            json.dump({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "C3: this commit adds local paths or personal data:\n" + listed + "\n"
                    "Replace them with ${KIPRJMOD}, $HOME, a relative path or a placeholder such as "
                    "/home/<user>, then commit again."
                ),
            }}, sys.stdout)
            return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001, a broken guard must never block every Bash call
        sys.exit(0)
