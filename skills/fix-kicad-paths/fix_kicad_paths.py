#!/usr/bin/env python3
"""Rewrite absolute /home/* paths in KiCad files to portable ${KIPRJMOD} paths.

KiCad likes to bake absolute host paths into files (most commonly the
``Sim.Library`` property of spice models, but also worksheet/library refs).
Those paths break on any other machine and trip pre-commit blacklists that
reject host-specific strings like ``/home/<user>``.

This is a *fix* script, not a checker: it edits files in place. The intended
workflow is to run it, then ``git add`` the result to review the diff, after
which the (non-editing) pre-commit hook should pass.

For every double-quoted string that is an absolute path beginning with ``/``,
we resolve the file it points at by finding the longest trailing path segment
that actually exists inside the repo. That makes it robust even when the file
was authored on a different machine with a different path prefix. The path is
then rewritten as ``${KIPRJMOD}/<relative-path>`` where ``${KIPRJMOD}`` is
KiCad's built-in variable for the directory of the project/schematic file.

Usage:
    fix_kicad_paths.py [PATH ...]        # files and/or directories
    fix_kicad_paths.py                   # default: scan the repo from cwd
    fix_kicad_paths.py --check           # report only, exit 1 if changes needed
    fix_kicad_paths.py --prefix /home    # only touch paths under this prefix
                                         #   (default; repeatable, "/" = all)
"""

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# KiCad text files that may contain baked-in absolute paths.
KICAD_GLOBS = (
    "*.kicad_sch",
    "*.kicad_pro",
    "*.kicad_pcb",
    "*.kicad_sym",
    "*.kicad_wks",
    "*.kicad_dru",
)

# Quoted absolute paths, e.g.  "Sim.Library" "/home/<user>/.../foo.mod"
QUOTED_ABS_PATH = re.compile(r'"(/[^"\r\n]*)"')


def repo_root(start: Path) -> Path:
    """Return the git top-level for *start*, or *start* itself if not a repo."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        )
        return Path(out.decode().strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return start.resolve()


def resolve_in_repo(abs_path: str, root: Path):
    """Map an absolute path to an existing file inside *root* (a realpath).

    Returns the *canonical* (symlink-resolved) absolute Path of the target, or
    None if it can't be located inside the repo.

    1. If the path exists on this machine (possibly through a symlink such as
       $HOME/dev/PROJECT -> /home/<user>/.../PROJECT), canonicalize it and accept
       it when it lands inside the repo. This is the common case here.
    2. Otherwise fall back to suffix-matching: try progressively shorter
       trailing segments of *abs_path* under *root*. This handles files that
       were authored on another machine with a different path prefix.
    """
    p = Path(abs_path)
    if p.exists():
        real = p.resolve()
        try:
            real.relative_to(root)
            return real
        except ValueError:
            pass  # exists but genuinely outside the repo; try suffix match

    parts = [seg for seg in p.parts if seg not in ("/", "\\")]
    for i in range(len(parts)):
        candidate = root.joinpath(*parts[i:])
        if candidate.exists():
            return candidate.resolve()
    return None


def portable_path(target: Path, kicad_file: Path) -> str:
    """Build a ${KIPRJMOD}-relative path from *kicad_file*'s dir to *target*.

    Both ends are canonicalized (realpath) first. os.path.relpath is purely
    lexical, so mixing a symlinked file dir ($HOME/...) with a real target
    (/home/<user>/...) would otherwise produce a path that escapes the project
    (../../../s/...). Inside the repo the real and symlinked trees are
    identical, so the realpath-based relative path is also correct from KiCad's
    symlink-based ${KIPRJMOD}.
    """
    base = kicad_file.resolve().parent
    rel = os.path.relpath(target.resolve(), base)
    rel = rel.replace(os.sep, "/")  # KiCad uses forward slashes everywhere
    return "${KIPRJMOD}/" + rel


def iter_targets(paths, root: Path):
    """Yield KiCad files from the given file/dir *paths* (recursing dirs)."""
    seen = set()
    for p in paths:
        p = Path(p)
        files = []
        if p.is_dir():
            for pattern in KICAD_GLOBS:
                files.extend(p.rglob(pattern))
        elif p.is_file():
            files.append(p)
        else:
            print(f"warning: {p} does not exist, skipping", file=sys.stderr)
        for f in files:
            # Skip KiCad's own backup/history dirs.
            if any(part in (".history", "backup", "backups") for part in f.parts):
                continue
            rp = f.resolve()
            if rp not in seen:
                seen.add(rp)
                yield f


def fix_file(kicad_file: Path, root: Path, prefixes, check: bool):
    """Rewrite absolute paths in one file. Returns (n_fixed, n_unresolved)."""
    text = kicad_file.read_text(encoding="utf-8")
    fixed = 0
    unresolved = 0

    def replace(match: re.Match) -> str:
        nonlocal fixed, unresolved
        abs_path = match.group(1)
        # Leave KiCad variables and non-target prefixes untouched.
        if abs_path.startswith("${"):
            return match.group(0)
        if not any(abs_path.startswith(pref) for pref in prefixes):
            return match.group(0)
        target = resolve_in_repo(abs_path, root)
        if target is None:
            print(
                f"  ! could not resolve inside repo: {abs_path}", file=sys.stderr
            )
            unresolved += 1
            return match.group(0)
        replacement = portable_path(target, kicad_file)
        fixed += 1
        print(f"  {abs_path}\n    -> {replacement}")
        return f'"{replacement}"'

    new_text = QUOTED_ABS_PATH.sub(replace, text)

    if fixed and not check:
        atomic_write(kicad_file, new_text)
    return fixed, unresolved


def atomic_write(path: Path, text: str) -> None:
    """Replace *path* atomically, preserving its mode.

    Writes a temp file in the same directory and renames over the target. This
    only needs write permission on the *directory*, not the existing file, so
    it works in shared group-writable checkouts where the file is owned by
    another user.
    """
    orig_mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, orig_mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="files or dirs (default: repo)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report only, do not edit; exit 1 if fixes are needed",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help="only rewrite absolute paths under this prefix "
        "(default /home; repeatable; use / to match all)",
    )
    args = parser.parse_args()

    prefixes = tuple(args.prefix) if args.prefix else ("/home",)

    start = Path(args.paths[0]) if args.paths else Path.cwd()
    start = start if start.is_dir() else start.parent
    root = repo_root(start)

    targets = list(iter_targets(args.paths or [root], root))
    if not targets:
        print("No KiCad files found.")
        return 0

    total_fixed = 0
    total_unresolved = 0
    changed_files = []
    for f in targets:
        fixed, unresolved = fix_file(f, root, prefixes, args.check)
        if fixed:
            print(f"{f}: {fixed} path(s)")
            changed_files.append(f)
        total_fixed += fixed
        total_unresolved += unresolved

    verb = "would fix" if args.check else "fixed"
    print(
        f"\n{verb} {total_fixed} path(s) in {len(changed_files)} file(s)"
        + (f", {total_unresolved} unresolved" if total_unresolved else "")
    )

    if total_unresolved:
        print(
            "Unresolved paths point outside the repo; move the target in-repo "
            "or fix by hand.",
            file=sys.stderr,
        )
        return 2
    if args.check and total_fixed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
