---
name: rust-style
description: The Jitter Rust style guide, with bad-to-good examples for comments, C-isms, macros, module layout and interface design. Use when writing or refactoring Rust in a Jitter repo, when a rewrite is about to touch many files, when comments or doc blocks are growing, or when the user asks what the house style says.
---

# Jitter Rust style

Read `${CLAUDE_PLUGIN_ROOT}/../../../rules/rust-style.md` now, then apply it to the code at hand.

The short version is already in context from `rules/core.md`. Load the full file when you need the reasoning, the examples, or a rule you are unsure about.

After a batch of edits, check your own work:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/../../../tools/comment_lint.py" path/to/changed.rs
```

Fix what it reports before handing the work back. A one-off sweep including the comment ratio per function is `--ratio`, which is noisier by design.
