#!/usr/bin/env python3
"""Find local paths and personal data in files that are about to leave the machine.

Files:        python3 path_leak_check.py report.md netlist.net
Staged diff:  python3 path_leak_check.py --staged
Pre-commit:   see templates/pre-commit in jitter-ai-agent

Catches /home/<user>, /Users/<user>, C:\\Users\\<user>, personal email addresses, an ssh
private key header and obvious tokens. Exit 0 clean, 1 findings.

A line that must carry an example path can opt out with a `path-leak-check: allow` comment.
Runs on Linux and macOS with a stock python3, no dependencies.
"""

import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "target", "node_modules", "build", "dist", "__pycache__", ".venv"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".zip", ".gz", ".bin", ".elf", ".ico", ".woff2"}

# A generic placeholder such as /home/user or /Users/you is fine, a real account name is not.
PLACEHOLDER = {"user", "username", "you", "youruser", "your-user", "me", "someone", "runner", "ci"}

PATTERNS = [
    ("home path", re.compile(r"/home/([A-Za-z0-9._-]+)")),
    ("macOS home path", re.compile(r"/Users/([A-Za-z0-9._-]+)")),
    ("Windows home path", re.compile(r"[Cc]:\\\\?Users\\\\?([A-Za-z0-9._-]+)")),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----")),
    ("token", re.compile(r"\b(?:ghp|github_pat|sk-[A-Za-z0-9]{8}|xox[baprs])[A-Za-z0-9_-]{10,}")),
]

# An explicit escape hatch for a line that must contain an example path, such as a test
# fixture or documentation of the pattern itself.
ALLOW_MARKER = "path-leak-check: allow"

# Addresses we publish on purpose.
EMAIL_ALLOW = re.compile(r"@(jitter\.company|users\.noreply\.github\.com|noreply\.anthropic\.com|example\.(com|org))$")


def interesting(name, match):
    if name == "email address":
        return not EMAIL_ALLOW.search(match.group(0))
    if name.endswith("home path"):
        return match.group(1).lower() not in PLACEHOLDER
    return True


def scan_text(text, label):
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for name, pattern in PATTERNS:
            for match in pattern.finditer(line):
                if interesting(name, match):
                    findings.append("{}:{}: {}: {}".format(label, lineno, name, match.group(0)))
    return findings


def scan_file(path):
    p = Path(path)
    if p.suffix.lower() in SKIP_SUFFIXES or not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_text(text, path)


def staged_files():
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    files = []
    for name in out.stdout.splitlines():
        if not name:
            continue
        if any(part in SKIP_DIRS for part in Path(name).parts):
            continue
        files.append(name)
    return files


def main(argv):
    if "--staged" in argv:
        targets = staged_files()
    else:
        targets = [a for a in argv if not a.startswith("-")]
    if not targets:
        return 0

    findings = []
    for path in targets:
        findings += scan_file(path)

    if not findings:
        return 0

    sys.stderr.write(
        "C3: local paths or personal data found, these must not leave the machine:\n"
        + "\n".join(findings)
        + "\nReplace them with ${KIPRJMOD}, $HOME, a relative path or a config value.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
