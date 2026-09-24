---
description: Run the Jitter checks on this repo (comments, leaked paths, KiCad exclusions) and report what needs fixing
---

Run the checks that apply to this repo, from the plugin root:

```sh
python3 "$JITTER_ROOT/tools/comment_lint.py" $(git ls-files '*.rs')
python3 "$JITTER_ROOT/tools/path_leak_check.py" $(git ls-files)
python3 "$JITTER_ROOT/tools/kicad_project_check.py"
python3 "$JITTER_ROOT/tools/layout_check.py"
```

Skip the ones with nothing to scan. The KiCad check only makes sense in a repo with `*.kicad_pro`.

Then report, briefly:

- the count per check, and the files with the most hits
- which hits are worth fixing now and which look like false positives, with your reasoning
- for a false positive, whether the fix is a threshold, a pattern, a `// jitter-lint: allow <rule> <reason>` marker, or a `.jitter-lint-ignore` entry for a vendored tree
- note that R3 findings are advisory, so a long run that says why is not a problem

Do not fix anything yet unless $ARGUMENTS says to. If it does, fix and show the diff.

`$JITTER_ROOT` is printed at session start by the plugin's own hook, as `JITTER_ROOT=<path>`. Use that path. If it is not in context, find it with:

```sh
find ~/.claude/plugins -maxdepth 7 -name comment_lint.py -path '*tools*' 2>/dev/null | head -1
```
