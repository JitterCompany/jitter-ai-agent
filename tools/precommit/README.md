# Checks meant for commit time

Point the shared git hook at this directory, not at `tools/`, which also holds the self-tests:

```sh
export JITTER_PRECOMMIT_CHECKS="$HOME/dev/jitter/common/jitter-ai-agent/tools/precommit"
```

Only two checks belong here, because they catch what an edit hook cannot see:

- `path_leak_check.py` (C3): a local path or personal data in anything about to be committed, including files a generator wrote.
- `kicad_project_check.py` (H5): KiCad dropping its own ERC and DRC exclusions when it rewrote a project file.

The comment and prose checks are deliberately absent. They already run on every edit, and a second pass at commit time would only nag about code someone else wrote.
