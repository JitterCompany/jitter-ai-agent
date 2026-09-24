#!/usr/bin/env python3
"""Keep the rule ids honest: one home file per prefix, no duplicates, no dangling references.

    python3 tools/check_rule_ids.py

Each prefix is owned by one file, which is where its numbers are handed out. core.md repeats
the short form of the always-on rules, so an id there must already exist in its home file.
Exit 0 when consistent, 1 when not.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = {
    "R": "rules/rust-style.md",
    "P": "rules/prose.md",
    "H": "rules/hardware.md",
    "W": "rules/core.md",
    "C": "rules/core.md",
    "M": "rules/core.md",
}

DEFINITION = re.compile(r"^- \*\*([A-Z])(\d+)(?:-[A-Z]?(\d+))?\*\*")


def ids_in(path, problems=None):
    """Ids introduced by a bullet in this file, as {(prefix, number): line}."""
    found = {}
    text = (ROOT / path).read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = DEFINITION.match(line)
        if not match:
            continue
        prefix, first, last = match.group(1), int(match.group(2)), match.group(3)
        for number in range(first, int(last) + 1 if last else first + 1):
            key = (prefix, number)
            if key in found:
                print("{}:{}: {}{} listed twice in one file".format(path, lineno, prefix, number))
                if problems is not None:
                    problems.append(key)
            found[key] = lineno
    return found


def main():
    duplicates = []
    problems = 0
    defined = {}

    for prefix, path in sorted(set(HOME.items()), key=lambda kv: kv[1]):
        for key, lineno in ids_in(path, duplicates).items():
            if key[0] != prefix and HOME.get(key[0]) == path:
                continue
            if key[0] == prefix:
                if key in defined:
                    print("{}:{}: {}{} already defined in {}".format(path, lineno, *key, defined[key]))
                    problems += 1
                defined[key] = path

    # core.md repeats always-on rules owned by another file. Those must resolve.
    for key, lineno in ids_in("rules/core.md").items():
        home = HOME.get(key[0])
        if home is None:
            print("rules/core.md:{}: unknown prefix {}".format(lineno, key[0]))
            problems += 1
        elif home != "rules/core.md" and key not in defined:
            print("rules/core.md:{}: {}{} is not defined in {}".format(lineno, key[0], key[1], home))
            problems += 1

    problems += len(duplicates)
    if problems:
        print("\n{} problem(s). Ids are handed out in the home file, see rules/core.md.".format(problems))
        return 1

    counts = {}
    for prefix, _ in defined:
        counts[prefix] = counts.get(prefix, 0) + 1
    print("ids consistent: " + ", ".join("{}={}".format(k, counts[k]) for k in sorted(counts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
