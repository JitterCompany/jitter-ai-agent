#!/usr/bin/env python3
"""Check written text against the P rules that a script can see.

    python3 tools/prose_check.py docs/*.md
    python3 tools/prose_check.py --tracked        # every tracked .md in this repo

P1 no em dashes. P2 no sentence that chains clauses with a semicolon. Exit 0 clean, 1 findings.
The rest of prose.md needs a human or an agent, this only catches the mechanical two.
"""

import re
import subprocess
import sys
from pathlib import Path

EM_DASH = re.compile(r"—")
# An en dash between numbers is a range (0–15, 10–100 MHz), which is fine.
EN_DASH_PROSE = re.compile(r"(?<![\d\s])–|–(?!\d)")
SEMICOLON_CHAIN = re.compile(r"\w{25,};\s+\w")  # a long clause, then another one


def scan(path):
    findings = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    in_code = False
    for lineno, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if EM_DASH.search(line) or EN_DASH_PROSE.search(line):
            findings.append("{}:{}: P1: em dash. Use a comma, a full stop or brackets.".format(path, lineno))
        if SEMICOLON_CHAIN.search(line):
            findings.append("{}:{}: P2: clauses chained with a semicolon. Two sentences read better.".format(path, lineno))
    return findings


def tracked():
    done = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True, check=False)
    return [line for line in done.stdout.splitlines() if line]


def main(argv):
    paths = tracked() if "--tracked" in argv else [a for a in argv if not a.startswith("-")]
    findings = []
    for path in paths:
        findings += scan(path)
    if not findings:
        return 0
    sys.stderr.write("\n".join(findings) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
