#!/usr/bin/env python3
"""Find annotation that KiCad carried over from another project.

Copying a symbol, pasting a sheet or placing a design block keeps the source project's
annotation inside every symbol: an `(instances (project "other-board" ...))` block. KiCad
never shows it, so a customer's board name can end up in a public repo unnoticed (C1).
Library footprints pick up `Sheetfile` and `Sheetname` the same way.

    python3 kicad_foreign_check.py                  # every .kicad_sch/.kicad_mod in the repo
    python3 kicad_foreign_check.py a.kicad_sch      # these files
    python3 kicad_foreign_check.py --staged         # what the commit will contain
    python3 kicad_foreign_check.py --fix [files]    # strip them from the working copy

A schematic's own project is the nearest .kicad_pro up the tree, so nothing is hardcoded. A
design block in a library has none, so every project in it is foreign.
Exit 0 clean, 1 findings. Linux and macOS, stock python3.
"""

import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "target", "node_modules", ".history"}
PROJECT = re.compile(r'[ \t]*\(project "([^"]*)"')
SHEET_PROPERTY = re.compile(r'[ \t]*\(property "(Sheetfile|Sheetname)" "([^"]*)"')
EMPTY_INSTANCES = re.compile(r'[ \t]*\(instances\s*\)\n?')


def block_end(text, start):
    """Index just past the s-expression that opens at or after `start`, plus its newline."""
    depth = 0
    i = text.index("(", start)
    in_string = False
    while True:
        c = text[i]
        if in_string:
            if c == "\\":
                i += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    i += 1
    return i + 1 if text[i:i + 1] == "\n" else i


def foreign_blocks(text, path, own):
    """(start, end, description) of every block that does not belong in this file."""
    found = []
    if path.endswith(".kicad_sch"):
        for m in PROJECT.finditer(text):
            if m.group(1) not in own:
                found.append((m.start(), block_end(text, m.start()), "project " + m.group(1)))
    elif path.endswith(".kicad_mod"):
        for m in SHEET_PROPERTY.finditer(text):
            found.append((m.start(), block_end(text, m.start()), "{} {}".format(*m.groups())))
    return found


def strip(text, blocks):
    for start, end, _ in sorted(blocks, reverse=True):
        text = text[:start] + text[end:]
    return EMPTY_INSTANCES.sub("", text)


def report(text, path, blocks):
    counts = {}
    for start, _, what in blocks:
        line = text.count("\n", 0, start) + 1
        counts.setdefault(what, []).append(line)
    return ["{}:{}: {} ({}x)".format(path, lines[0], what, len(lines))
            for what, lines in counts.items()]


def git_lines(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return [line for line in out.stdout.splitlines() if line]


def wanted(name):
    return name.endswith((".kicad_sch", ".kicad_mod")) and not SKIP_DIRS & set(Path(name).parts)


def own_projects(path, staged):
    """The nearest .kicad_pro up the tree, plus the file's own name for a root sheet."""
    own = {Path(path).stem, ""}
    for folder in Path(path).parents:
        if staged:
            names = [n for n in git_lines("ls-files", "--", str(folder / "*.kicad_pro"))
                     if Path(n).parent == folder]
        else:
            names = list(folder.glob("*.kicad_pro"))
        if names:
            return own | {Path(n).stem for n in names}
    return own


def read(path, staged):
    if staged:
        done = subprocess.run(["git", "show", ":" + path], capture_output=True, check=False)
        return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def main(argv):
    staged = "--staged" in argv
    fix = "--fix" in argv
    files = [a for a in argv if not a.startswith("-")]
    if staged:
        files = [f for f in git_lines("diff", "--cached", "--name-only", "--diff-filter=ACMR")
                 if wanted(f)]
    elif not files:
        tracked = git_lines("ls-files")
        files = [f for f in tracked if wanted(f)] if tracked else [
            str(p) for p in Path(".").rglob("*") if wanted(str(p))]

    findings = []
    fixed = []
    for path in files:
        # --fix rewrites the working copy, so it must start from the working copy.
        text = read(path, staged and not fix)
        blocks = foreign_blocks(text, path, own_projects(path, staged and not fix))
        if not blocks:
            continue
        if fix:
            lock = Path(path).with_name("~" + Path(path).name + ".lck")
            if lock.exists():
                findings.append("{}: open in KiCad, close it first".format(path))
                continue
            Path(path).write_text(strip(text, blocks), encoding="utf-8")
            fixed.append("{}: removed {} block(s)".format(path, len(blocks)))
        else:
            findings += report(text, path, blocks)

    if fixed:
        print("\n".join(fixed))
    if not findings:
        return 0
    sys.stderr.write(
        "C1: KiCad annotation from another project, invisible in KiCad but public once pushed:\n"
        + "\n".join(findings)
        + "\nStrip it with: python3 kicad_foreign_check.py --fix <files>\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
