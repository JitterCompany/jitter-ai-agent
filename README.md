# jitter-agent

Jitter's shared conventions for AI coding agents, plus the tooling that enforces them. One place, versioned, improved by PR, loaded automatically in everyone's sessions.

Written because AI-assisted Rust drifts in two directions: C-style code, and comment blocks that grow through a long session until they restate the code.

## Layout

| Path | What |
|---|---|
| `rules/core.md` | The short rule set, injected at every session start and after every compaction |
| `rules/rust-style.md` | Full Rust guide with bad-to-good examples |
| `rules/prose.md` | Writing style, applies to comments, docs and commit messages too |
| `rules/hardware.md` | KiCad, PCB, lab |
| `tools/comment_lint.py` | Comment-bloat check for Rust, standalone or as an edit hook |
| `tools/path_leak_check.py` | Blocks `/home/<user>`, personal email addresses and tokens from leaving the machine |
| `templates/` | Clippy workspace lints, rustfmt, per-repo `.claude/settings.json` |
| `hooks/`, `skills/`, `agents/` | Claude Code delivery: the session hooks, the skills and the review agent |

`rules/` and `tools/` need nothing but a text editor and python3. The plugin only delivers them. If you use another agent, point its instruction file at `rules/core.md`.

## Use it in a repo

Commit `templates/claude-settings.json` as the repo's `.claude/settings.json`. Everyone who opens the repo is prompted to install the marketplace and the plugin. The hardware rules load by themselves in a repo that has KiCad files, so there is nothing extra to enable there.

Personal install, without touching a repo:

```sh
/plugin marketplace add JitterCompany/jitter-agent
/plugin install jitter@jitter
```

Update after someone lands a change:

```sh
/plugin marketplace update jitter
```

The `setup-repo` skill does the rest of the wiring (clippy lints, rustfmt, pre-commit check).

## Run the checks by hand

```sh
python3 tools/comment_lint.py $(git ls-files '*.rs')     # add --ratio for a noisier sweep
python3 tools/path_leak_check.py --staged                 # good as a pre-commit hook
```

Both work on Linux and macOS with a stock python3, exit 0 when clean, and print `file:line: problem`.

A repo with vendored or generated Rust gets a `.jitter-lint-ignore` at its root, one glob per line.

## Change a rule

1. Branch, edit the file under `rules/`, one rule per PR.
2. `rules/core.md` is loaded in every session, so it stays short. Adding a line there usually means removing one.
3. Prefer a check over a sentence. A clippy lint or a line in `comment_lint.py` lands in the agent's context exactly when it matters, and it never gets summarized away.
4. Say why in the PR. A rule without a reason gets argued about again in six months.

During a session you can ask Claude to do this for you: the `style-feedback` skill drafts the rule and the branch, and asks before pushing.

## Scope

Company-wide conventions live here. Project facts (architecture, build commands, hardware quirks) stay in that repo's own `CLAUDE.md`. Personal preferences and machine specifics stay personal.
