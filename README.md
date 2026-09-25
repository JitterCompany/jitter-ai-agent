# jitter-ai-agent

Jitter's shared conventions for AI coding agents, plus the tooling that enforces them. One place, versioned, improved by PR, loaded automatically in everyone's sessions.

Written because AI-assisted Rust drifts in two directions: C-style code, and comment blocks that grow through a long session until they restate the code.

## Layout

| Path | What |
|---|---|
| `rules/core.md` | The short rule set, injected at every session start and after every compaction |
| `rules/rust-style.md` | Full Rust guide with bad-to-good examples, home of the `R` ids |
| `rules/prose.md` | Writing style, applies to comments, docs and commit messages too, `P` ids |
| `rules/hardware.md` | KiCad, PCB, lab, `H` ids. Loads by itself in a repo with KiCad files |
| `tools/comment_lint.py` | Comment-bloat check for Rust, standalone or as an edit hook |
| `tools/path_leak_check.py` | Blocks `/home/<user>`, personal email addresses and tokens from leaving the machine |
| `tools/kicad_project_check.py` | Catches ERC/DRC exclusions that KiCad drops when it rewrites a `.kicad_pro` |
| `tools/prose_check.py` | The P rules a script can see: em dashes, semicolon-chained sentences |
| `tools/layout_check.py` | R7, the `mod.rs` files |
| `tools/guard_push.py` | Enforces W2: the agent cannot push or open a PR without approval |
| `tools/run_tests.py`, `tools/check_rule_ids.py` | Self-tests for the checks, and the id consistency check. Both run in CI |
| `templates/` | Clippy workspace lints and rustfmt, the only files a project repo commits |
| `typst/jitter-report/` | The house style for engineering reports, as a local Typst package |
| `hooks/`, `skills/`, `agents/`, `commands/` | Claude Code delivery: session hooks, skills, the review agent, `/jitter-check` |

`rules/` and `tools/` need nothing but a text editor and python3. The plugin only delivers them. If you use another agent, point its instruction file at `rules/core.md`.

## Rule ids

Each rules file owns a prefix and hands out its own numbers: `R` rust-style, `P` prose, `H` hardware, `W` working and `C` company and `M` meta in core.md. `core.md` repeats the short form of the always-on rules under the same id, so R1 in the digest and R1 in the guide are one rule. Numbers are never reused, and `tools/check_rule_ids.py` fails CI if an id is duplicated or dangling.

Ids exist so a rule can be cited when it is challenged, and named when someone wants an exception. Claude does not narrate them (M2).

## Install it, once per person

```sh
/plugin marketplace add JitterCompany/jitter-ai-agent
/plugin install jitter@jitter
```

That is the whole setup. The rules then load in every repo you open, and nothing needs to be committed anywhere.

Documents are Typst. To write reports, install the house style once:

```sh
mkdir -p ~/.local/share/typst/packages/local/jitter-report
ln -sfn "$PWD/typst/jitter-report/0.1.0" ~/.local/share/typst/packages/local/jitter-report/0.1.0
```

Update after someone lands a change:

```sh
/plugin marketplace update jitter
```

**Nothing goes in a project repo that points at this one.** Several of our repos are public or shared with a client, and a committed `.claude/settings.json` naming a private marketplace would both disclose it and prompt outside readers to install something they cannot reach. What a project repo may commit is ordinary tooling that stands on its own: the clippy `[workspace.lints]` block and `rustfmt.toml`.

## Pre-commit checks

We already have a global hook, [JitterCompany/git_utils](https://github.com/JitterCompany/git_utils), symlinked into each repo as `.git/hooks/pre-commit`. The checks here plug into that rather than replacing it, so a repo gains nothing new to commit:

```sh
# in your shell profile, pointing at your clone of this repo
export JITTER_PRECOMMIT_CHECKS="$HOME/dev/jitter/common/jitter-ai-agent/tools/precommit"
```

`tools/precommit/` holds exactly the two checks that belong at commit time, `path_leak_check.py` (C3) and `kicad_project_check.py` (H5). Both catch what the session hooks cannot see: a file produced by a generator rather than an edit, and KiCad clearing its own ERC and DRC exclusions. Point at that directory rather than `tools/`, which also holds the self-tests.

Support for `$JITTER_PRECOMMIT_CHECKS` is a change to git_utils itself, on the `precommit-checks` branch.

The `adopt-rules` skill does the per-repo part: clippy lints and rustfmt.

## Run the checks by hand

```sh
python3 tools/comment_lint.py --changed                # your own work, before handing it back
python3 tools/comment_lint.py --changed --max-run 2    # stricter when you wrote a lot of prose
python3 tools/comment_lint.py $(git ls-files '*.rs')
python3 tools/path_leak_check.py --staged              # what the pre-commit hook runs
python3 tools/kicad_project_check.py                   # in a KiCad repo, before committing
python3 tools/prose_check.py --tracked                 # docs, READMEs, decision records
python3 tools/layout_check.py                          # mod.rs files (R7)
python3 tools/guard_push.py                            # reads a hook payload, see the file
python3 tools/run_tests.py                             # after changing a threshold or a pattern
```

In a session, `/jitter-check` runs the applicable ones and sorts the hits from the false positives.

Everything runs on Linux and macOS with a stock python3, exits 0 when clean, and prints `file:line: rule: problem`.

## When a check is wrong

Two escape hatches, both deliberate and both visible in the diff:

- `// jitter-lint: allow R3 <reason>` anywhere inside the comment it refers to.
- `path-leak-check: allow` on a line that must carry an example path.
- `prose-check: allow` on a line whose dash belongs there, such as a quotation.

A repo with vendored or generated Rust gets a `.jitter-lint-ignore` at its root, one glob per line.

## Two levels, on purpose

The edit hook blocks only on rules that measured near 100% precision on real code: banners, step narration, change history, a new `/* */` block, and an em dash in prose (P1).

Two checks are sweep-only, because measurement said so. A long comment run (R3) was worth keeping in all 30 cases on sensor-link. Sentences chained with a semicolon (P2) were right about one time in four across 2842 markdown files, and a check that is wrong three times in four gets the whole hook deleted, taking the push guard with it.

The push guard is a reminder, not a security control. An agent determined to get around it can, for example by writing a script. It exists to catch the agent that forgets.

The one thing the agent is stopped from doing outright is pushing (W2), because that is the only rule here whose violation cannot be undone.

## What the self-tests are, and are not

`tools/run_tests.py` pins the contract: thresholds (a run of 4 is silent, 5 speaks), pattern widths (four fill characters are a banner), every row of the push guard's table, and every separator that starts a command. Deliberate mutations of those values fail the suite, which is checked by mutating the tools and re-running it.

It is still a check on the tools, not on your repo. A real change to a tool wants a measurement over a real repo as well, which is what every number in this README came from. Green tests mean the tools kept their promises, not that the promises are the right ones.

## Change a rule

1. Branch, edit the file under `rules/`, one rule per PR. Give it the next free number in that file.
2. `rules/core.md` is loaded in every session, so it stays short. Adding a line there usually means removing one, or leaving the rule in its home file only.
3. Prefer a check over a sentence. A clippy lint or a pattern in `comment_lint.py` lands in the agent's context exactly when it matters, and never gets summarized away. Tune it against a real repo first, `run_tests.py` covers the regressions.
4. Say why in the PR. A rule without a reason gets argued about again in six months.

In a session, just say "new company-wide rule" or "remember this across all projects". The `agent-rules` skill writes it, branches, and asks before pushing. The same skill handles the other direction: when a rule caused something unwanted, it records the exception at the level you pick (once, this project, you, everybody).

## Scope

Company-wide conventions live here. Project facts (architecture, build commands, hardware quirks) stay in that repo's own `CLAUDE.md`. Personal preferences and machine specifics stay personal.
