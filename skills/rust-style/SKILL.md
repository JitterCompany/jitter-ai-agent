---
name: rust-style
description: The Jitter Rust style guide with bad-to-good examples - comments, C-isms, macros, module layout, interfaces. Load it before writing or refactoring Rust, even a small change.
---

# Jitter Rust style

Read `rules/rust-style.md` under the plugin path printed at session start as `JITTER_ROOT=`, substituting that path yourself because the Read tool does not expand shell variables now, then apply it to the code at hand.

The short version is already in context from `rules/core.md`. Load the full file when you need the reasoning, the examples, or a rule you are unsure about.

After writing a significant amount of code, check your own work:

```sh
JITTER_ROOT=$(cat "${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root")
python3 "$JITTER_ROOT/tools/comment_lint.py" --changed
```

Fix what it reports before handing the work back. R3 (a long comment run) is advisory and has no right number: pass `--max-run 2` when you wrote a lot of prose and want to be strict with yourself, leave the default otherwise, and raise it when every hit turns out to be worth keeping.

The plugin writes its own path to `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root` at session start, which is what the `JITTER_ROOT=` line above reads. The same path is printed in the session header.
