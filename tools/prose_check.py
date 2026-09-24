#!/usr/bin/env python3
"""Check written text against the P rules that a script can see.

    python3 tools/prose_check.py docs/*.md
    python3 tools/prose_check.py --tracked        # every tracked .md in this repo
    python3 tools/prose_check.py --hook           # the Claude Code hook JSON on stdin

P1 no em dashes, which is definitional and blocks an edit. P2 no sentence that chains clauses
with a semicolon, which is a judgement call: measured over 2842 markdown files it was right
about one time in four, so it only shows up in a sweep where a human is reading.

Exit 0 clean, 1 findings, 2 findings in hook mode so the agent fixes them in the same turn.
In hook mode only the lines the edit wrote are judged. The rest of prose.md needs a human.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".typ", ".rst"}

ALLOW_MARKER = "prose-check: allow"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
BACKTICK_FENCE = re.compile(r"^\s*(`{3,})")
# In reStructuredText ~~~~ underlines a heading, so only markdown treats it as a fence.
TILDE_FENCE_SUFFIXES = {".md", ".markdown"}
TABLE_ROW = re.compile(r"^\s*\|")
HTML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")
INLINE_CODE = re.compile(r"`[^`]*`")
EM_DASH = re.compile(r"—")
# An en dash between numbers is a range (0–15, 10–100 MHz), which is fine.
EN_DASH_PROSE = re.compile(r"(?<![\d\s])–|–(?!\d)")
SEMICOLON_CHAIN = re.compile(r"[^;\n`]{40,};\s+[a-z]")  # a long clause, then another one


def scan(path):
    findings = []
    fence_pattern = (
        FENCE if Path(path).suffix.lower() in TILDE_FENCE_SUFFIXES else BACKTICK_FENCE
    )
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    fence = None
    for lineno, line in enumerate(lines, start=1):
        marker = fence_pattern.match(line)
        if marker:
            opening = marker.group(1)
            if fence is None:
                fence = opening
            elif opening[0] == fence[0] and len(opening) >= len(fence):
                fence = None
            continue
        in_code = fence is not None
        if in_code or line.startswith("    ") or line.startswith("\t"):
            continue  # fenced or indented code is code
        if ALLOW_MARKER in line:
            continue
        line = INLINE_CODE.sub(" ", line)
        if EM_DASH.search(line) or EN_DASH_PROSE.search(line):
            findings.append(
                (lineno, "P1: em or en dash in prose. Use a comma, a full stop or brackets. "
                         "A numeric range such as 10-100 MHz is fine.")
            )
        if (
            SEMICOLON_CHAIN.search(line)
            and not TABLE_ROW.match(line)
            and not HTML_TAG.search(line)
            and not semicolon_in_brackets(line)
        ):
            findings.append(
                (lineno, "P2: clauses chained with a semicolon. Two sentences read better.")
            )
    return findings


def semicolon_in_brackets(line):
    """A semicolon inside brackets is an aside, not two sentences welded together."""
    depth = 0
    for ch in line:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == ";" and depth:
            return True
    return False


def report(path, findings):
    return ["{}:{}: {}".format(path, lineno, message) for lineno, message in findings]


def tracked():
    patterns = ["*" + suffix for suffix in sorted(TEXT_SUFFIXES)]
    done = subprocess.run(["git", "ls-files", *patterns], capture_output=True, text=True, check=False)
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
        # P1 only: P2 is a judgement call and is left for a sweep.
        findings = [f for f in scan(path) if f[0] in touched and f[1].startswith("P1")]
        if not findings:
            return 0
        sys.stderr.write(
            "Writing style, on the lines this edit wrote:\n"
            + "\n".join(report(path, findings))
            + "\nRewrite them. If a dash belongs there, such as a quote from someone else, "
            "put `prose-check: allow` on the line.\n"
        )
        return 2

    paths = tracked() if "--tracked" in argv else [a for a in argv if not a.startswith("-")]
    lines = []
    for path in paths:
        lines += report(path, scan(path))
    if not lines:
        return 0
    sys.stderr.write("\n".join(lines) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
