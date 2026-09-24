---
description: Run the Jitter checks on this repo (comments, leaked paths, KiCad exclusions) and report what needs fixing
---

Run the checks that apply to this repo, from the plugin root:

```sh
JITTER_ROOT=$(cat "${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root")
python3 "$JITTER_ROOT/tools/comment_lint.py" $(git ls-files '*.rs')
python3 "$JITTER_ROOT/tools/path_leak_check.py" $(git ls-files)
python3 "$JITTER_ROOT/tools/kicad_project_check.py"
python3 "$JITTER_ROOT/tools/layout_check.py"
python3 "$JITTER_ROOT/tools/prose_check.py" --tracked
```

Skip the ones with nothing to scan. The KiCad check only makes sense in a repo with `*.kicad_pro`.

Then report, briefly:

- the count per check, and the files with the most hits
- which hits are worth fixing now and which look like false positives, with your reasoning
- for a false positive, whether the fix is a threshold, a pattern, a `// jitter-lint: allow <rule> <reason>` marker, or a `.jitter-lint-ignore` entry for a vendored tree
- note that R3 and P2 findings are advisory: a long run that says why, or a semicolon inside brackets, is not a problem

Do not fix anything yet unless $ARGUMENTS says to. If it does, fix and show the diff.

The plugin writes its own path to `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root` at session start, which is what the `JITTER_ROOT=` line above reads. The same path is printed in the session header.
