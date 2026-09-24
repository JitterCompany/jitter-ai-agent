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
    problems = []
    defined = {}
    files = sorted(set(HOME.values()))

    found = {path: ids_in(path, problems) for path in files}

    for path in files:
        owned = {prefix for prefix, home in HOME.items() if home == path}
        for key, lineno in found[path].items():
            prefix = key[0]
            if prefix in owned:
                if key in defined:
                    print("{}:{}: {}{} already defined in {}".format(path, lineno, *key, defined[key]))
                    problems.append(key)
                defined[key] = path
            elif HOME.get(prefix) is None:
                print("{}:{}: unknown prefix {}".format(path, lineno, prefix))
                problems.append(key)
            elif path != "rules/core.md":
                # Only the digest repeats a rule owned by another file.
                print(
                    "{}:{}: {}{} belongs in {}".format(path, lineno, prefix, key[1], HOME[prefix])
                )
                problems.append(key)

    for key, lineno in found["rules/core.md"].items():
        home = HOME.get(key[0])
        if home and home != "rules/core.md" and key not in defined:
            print("rules/core.md:{}: {}{} is not defined in {}".format(lineno, key[0], key[1], home))
            problems.append(key)

    if problems:
        print("\n{} problem(s). Ids are handed out in the home file, see rules/core.md.".format(len(problems)))
        return 1

    counts = {}
    for prefix, _ in defined:
        counts[prefix] = counts.get(prefix, 0) + 1
    print("ids consistent: " + ", ".join("{}={}".format(k, counts[k]) for k in sorted(counts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
