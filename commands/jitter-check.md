---
description: Run the Jitter checks on this repo (comments, leaked paths, KiCad exclusions) and report what needs fixing
---

Run the checks that apply to this repo, from the plugin root:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/tools/comment_lint.py" $(git ls-files '*.rs')
python3 "${CLAUDE_PLUGIN_ROOT}/tools/path_leak_check.py" $(git ls-files)
python3 "${CLAUDE_PLUGIN_ROOT}/tools/kicad_project_check.py"
```

Skip the ones with nothing to scan. The KiCad check only makes sense in a repo with `*.kicad_pro`.

Then report, briefly:

- the count per check, and the files with the most hits
- which hits are worth fixing now and which look like false positives, with your reasoning
- for a false positive, whether the fix is a threshold, a pattern, or a `.jitter-lint-ignore` entry for a vendored tree

Do not fix anything yet unless $ARGUMENTS says to. If it does, fix and show the diff.
