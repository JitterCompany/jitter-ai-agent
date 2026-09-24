---
name: fix-kicad-paths
description: >-
  Rewrite hardcoded absolute /home/* paths that KiCad bakes into schematic and
  project files (most often the Sim.Library spice-model property) into portable
  ${KIPRJMOD}-relative paths. Use when a commit is blocked by a pre-commit
  blacklist on host-specific strings like "/home/<user>", or generally before
  committing KiCad files, to strip machine-specific absolute paths. Fixes
  *.kicad_sch, *.kicad_pro, *.kicad_pcb, *.kicad_sym, *.kicad_wks, *.kicad_dru.
---

# Fix hardcoded paths in KiCad files

KiCad writes absolute host paths into files — commonly the `Sim.Library`
property of spice models, but also worksheet and library references. These
break on other machines and trip pre-commit hooks that blacklist host-specific
strings (e.g. `/home/<user>`).

## Workflow (this user's convention)

Pre-commit hooks here **only flag, never edit**. The pattern is: run a fix
script → `git add` to review the diff → the pre-commit hook then passes.
This skill's script is exactly such a fix script.

## Usage

```bash
# Dry run — report what would change, exit 1 if fixes are needed (flag stage):
python3 ~/.claude/skills/fix-kicad-paths/fix_kicad_paths.py --check

# Fix in place across the whole repo (run from anywhere inside it):
python3 ~/.claude/skills/fix-kicad-paths/fix_kicad_paths.py

# Fix specific files or directories:
python3 ~/.claude/skills/fix-kicad-paths/fix_kicad_paths.py path/to/foo.kicad_sch hardware/

# Match more than just /home (default prefix is /home; use / for all abs paths):
python3 ~/.claude/skills/fix-kicad-paths/fix_kicad_paths.py --prefix /
```

Then review and stage: `git add -p` (or `git add <files>`), and commit.

## How it resolves paths

For every quoted absolute path in a KiCad file, the script finds the **longest
trailing path segment that actually exists inside the repo** and rewrites the
reference as `${KIPRJMOD}/<relative-path-from-this-file>`. `${KIPRJMOD}` is
KiCad's built-in variable for the directory of the current project/schematic,
so the result is portable and machine-independent. Suffix-matching means it
works even when the file was authored on a machine with a different path prefix.

Example:
`/home/<user>/.../hardware/simulation/BC847BPN.mod` → `${KIPRJMOD}/../BC847BPN.mod`

If a path can't be resolved inside the repo (target lives outside), it's left
untouched and reported to stderr; the script exits non-zero so you notice.

## Notes / gotchas

- **Atomic writes.** Files are replaced via a temp-file + rename, preserving
  mode. This needs write permission on the *directory*, not the file, so it
  works in shared group-writable checkouts where files are owned by another
  user (e.g. `s:s` files in a group-`dev` dir). Side effect: the file's owner
  becomes the running user — harmless in a shared-group setup, but worth
  knowing.
- **Symlinked checkouts.** Projects are often accessed via a symlink (e.g.
  `$HOME/dev/PROJECT` -> `/home/<user>/.../PROJECT`). The script canonicalizes
  (realpath) the repo root, the target, and each file's directory before
  computing the relative path, so a symlinked path never leaks a broken
  `../../../s/...` result or a spurious "could not resolve".
- **Backup/history dirs** (`.history`, `backup`, `backups`) are skipped.
- **New blacklist strings.** If pre-commit flags a string this script doesn't
  handle, it's not necessarily a path — add it to the blacklist in the
  pre-commit script (`~/git/scripts/pre-commit`, `str_blacklist`) or
  extend this script if it's another hardcoded-path form.
- KiCad accepts both `${KIPRJMOD}/../x` and bare `../x` for `Sim.Library`;
  this script emits the `${KIPRJMOD}` form for clarity, but pre-existing bare
  relative paths are already portable and left alone.
