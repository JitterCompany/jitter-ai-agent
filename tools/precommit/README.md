# Checks meant for commit time

The agent's own commits run these through `guard_commit.py`, with no setup. For commits people make, the git_utils hook runs the folders listed in `~/.config/jitter-git/checks-path`. List this folder, not `tools/`, which also holds the self-tests. Use a copy that stays current: the `setup-extras` skill picks one.

Only these checks belong here, because they catch what an edit hook cannot see:

- `path_leak_check.py` (C3): a local path or personal data in anything about to be committed, including files a generator wrote.
- `kicad_project_check.py` (H5): KiCad dropping its own ERC and DRC exclusions when it rewrote a project file.
- `kicad_foreign_check.py` (C1): another project's name hidden in a schematic or footprint, carried over by a copied symbol, a pasted sheet or a design block. KiCad never shows it.

The comment and prose checks are deliberately absent. They already run on every edit, and a second pass at commit time would only nag about code someone else wrote.
