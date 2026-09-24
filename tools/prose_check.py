#!/usr/bin/env python3
"""Check written text against the P rules that a script can see.

    python3 tools/prose_check.py docs/*.md
    python3 tools/prose_check.py --tracked        # every tracked .md in this repo
    python3 tools/prose_check.py --hook           # the Claude Code hook JSON on stdin

P1 no em dashes. P2 no sentence that chains clauses with a semicolon.

Exit 0 clean, 1 findings, 2 findings in hook mode so the agent fixes them in the same turn.
In hook mode only the lines the edit wrote are judged. The rest of prose.md needs a human.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".typ", ".rst"}

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
            findings.append(
                "{}:{}: P1: em or en dash in prose. Use a comma, a full stop or brackets. "
                "A numeric range such as 10-100 MHz is fine.".format(path, lineno)
            )
        if SEMICOLON_CHAIN.search(line):
            findings.append("{}:{}: P2: clauses chained with a semicolon. Two sentences read better.".format(path, lineno))
    return findings


def tracked():
    done = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True, check=False)
    return [line for line in done.stdout.splitlines() if line]


def written_lines(path, tool_input):
    """Line numbers this edit wrote, located by position in the file."""
    chunks = [tool_input.get("new_string"), tool_input.get("content")]
    for edit in tool_input.get("edits") or []:
        chunks.append(edit.get("new_string"))
    chunks = [c for c in chunks if isinstance(c, str) and c.strip()]
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()

    touched = set()
    for chunk in chunks:
        offset = text.find(chunk)
        while offset != -1:
            first = text.count("\n", 0, offset) + 1
            touched.update(range(first, first + chunk.rstrip("\n").count("\n") + 1))
            offset = text.find(chunk, offset + 1)
    return touched


def main(argv):
    if "--hook" in argv:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        tool_input = payload.get("tool_input") or {}
        path = tool_input.get("file_path") or ""
        if Path(path).suffix.lower() not in TEXT_SUFFIXES:
            return 0
        touched = written_lines(path, tool_input)
        findings = [f for f in scan(path) if int(f.split(":")[1]) in touched]
        if not findings:
            return 0
        sys.stderr.write(
            "Writing style, on the lines this edit wrote:\n" + "\n".join(findings) + "\n"
        )
        return 2

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
