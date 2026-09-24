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
EMAIL_ALLOW = re.compile(
    r"@(jitter\.company|users\.noreply\.github\.com|noreply\.anthropic\.com|example\.(com|org))$"
    # Documentation placeholders: account@server.tld, you@example.test, user@host.invalid.
    r"|@[A-Za-z0-9.-]+\.(tld|invalid|test|example|local)$"
    r"|^(account|user|username|you|your|name|email|address|someone)@"
)
# `git@github.com:Org/repo.git` is a remote, not somebody's mailbox. Submodules carry it (H9).
GIT_REMOTE = re.compile(r"\bgit@[A-Za-z0-9.-]+[:/]")
# A PEM header is a leak when actual key material follows, and a string constant when a parser
# looks for it. Base64 on the same or the next line is the difference.
KEY_MATERIAL = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def interesting(name, match, line="", following=""):
    if name == "email address":
        if GIT_REMOTE.search(line):
            return False
        return not EMAIL_ALLOW.search(match.group(0))
    if name.endswith("home path"):
        return match.group(1).lower() not in PLACEHOLDER
    if name == "private key":
        return bool(KEY_MATERIAL.search(line[match.end():]) or KEY_MATERIAL.search(following))
    return True


def scan_text(text, label):
    findings = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        if ALLOW_MARKER in line:
            continue
        following = lines[lineno] if lineno < len(lines) else ""
        for name, pattern in PATTERNS:
            for match in pattern.finditer(line):
                if interesting(name, match, line, following):
                    finding = "{}:{}: {}: {}".format(label, lineno, name, match.group(0))
                    if finding not in findings:  # one line can carry the same example twice
                        findings.append(finding)
    return findings


def scan_staged(path):
    """The staged content, which is what the commit will contain."""
    done = subprocess.run(
        ["git", "show", ":{}".format(path)], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        return []
    return scan_text(done.stdout, path)


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
    staged = "--staged" in argv
    if staged:
        targets = staged_files()
    else:
        targets = [a for a in argv if not a.startswith("-")]
    if not targets:
        return 0

    findings = []
    for path in targets:
        findings += scan_staged(path) if staged else scan_file(path)

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
