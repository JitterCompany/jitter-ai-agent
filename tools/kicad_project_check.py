#!/usr/bin/env python3
"""Catch what KiCad silently drops from a .kicad_pro when it rewrites the file.

Opening a project is enough for KiCad to rewrite it, and reviewed ERC/DRC exclusions
regularly come back empty. This compares the working copy against a git revision.

    python3 kicad_project_check.py                 # every *.kicad_pro in the repo, vs HEAD
    python3 kicad_project_check.py hardware/x.kicad_pro
    python3 kicad_project_check.py --rev origin/master

Exit 0 when nothing was lost, 1 when something was. Linux and macOS, stock python3.
"""

import json
import subprocess
import sys
from pathlib import Path

# Lists and dicts whose shrinking means review work was thrown away.
WATCHED = [
    ("erc", "erc_exclusions"),
    ("erc", "rule_severities"),
    ("board", "design_settings", "drc_exclusions"),
    ("board", "design_settings", "rule_severities"),
    ("net_settings", "classes"),
    ("text_variables",),
]


def dig(data, path):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def git(args, cwd="."):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout


def tracked_projects(rev):
    code, out = git(["ls-files", "*.kicad_pro"])
    if code != 0:
        sys.stderr.write("not a git repository\n")
        sys.exit(2)
    return [line for line in out.splitlines() if line]


def old_version(path, rev):
    root = git(["rev-parse", "--show-toplevel"])[1].strip()
    rel = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    code, out = git(["show", "{}:{}".format(rev, rel)])
    if code != 0:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def size(value):
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def compare(path, rev):
    findings = []
    old = old_version(path, rev)
    if old is None:
        return findings  # new file, or not in that revision
    try:
        new = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [("{}: cannot read working copy: {}".format(path, exc))]

    for keys in WATCHED:
        before, after = size(dig(old, keys)), size(dig(new, keys))
        if not before:
            continue  # absent or already empty, nothing to lose
        if after is None:
            findings.append(
                "{}: {} is gone, was {} entries in {}".format(path, "/".join(keys), before, rev)
            )
        elif after < before:
            findings.append(
                "{}: {} dropped from {} to {} entries since {}".format(
                    path, "/".join(keys), before, after, rev
                )
            )
    return findings


def main(argv):
    rev = "HEAD"
    if "--rev" in argv:
        index = argv.index("--rev") + 1
        if index >= len(argv):
            sys.stderr.write("--rev needs a revision, for example --rev origin/master\n")
            return 2
        rev = argv[index]
    paths = [a for a in argv if not a.startswith("-") and a != rev]
    paths = [p for p in paths if p.endswith(".kicad_pro")] or tracked_projects(rev)

    findings = []
    for path in paths:
        findings += compare(path, rev)

    if not findings:
        return 0

    sys.stderr.write(
        "H5: KiCad dropped project settings when it rewrote the file:\n"
        + "\n".join(findings)
        + "\nH7: restore with `git checkout -- <file>` or re-apply the exclusions in KiCad "
        "before committing anything else.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
