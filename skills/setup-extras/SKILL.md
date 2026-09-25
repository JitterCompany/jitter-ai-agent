---
name: setup-extras
description: Offer a colleague the optional parts of the Jitter agent setup the first time they use it: the commit-time checks and the shared git hook. Use when the session says this person has not been offered the extras, when someone asks how to finish setting this up, or when a commit-time check turns out not to be installed.
---

# Finish setting someone up

The plugin works with nothing configured. Two extras are worth offering once, and never again.

Ask in one message, listing what each does, and take a no for an answer. Then write the marker either way, so nobody is asked twice.

Write both files with the Write tool rather than a shell redirect. A shell command that touches a dotfile needs its own approval, and in a session that has already said yes to the setup, stopping again to ask for a `>>` is noise. Read an existing file first and add your line to it, never replace it.

- marker: `${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/onboarded`, containing today's date
- checks: `~/.config/jitter-git/checks-path`, one path per line

## 1. The commit-time checks

They catch a local path or personal data in anything about to be committed (C3), and KiCad dropping its own ERC and DRC exclusions (H5). Both see things an edit-time check cannot.

Check what is already there, and only offer what is missing:

```sh
cat ~/.config/jitter-git/checks-path 2>/dev/null
echo "$JITTER_PRECOMMIT_CHECKS"
```

To enable, with their yes, add one line to `~/.config/jitter-git/checks-path`:

```
<the JITTER_ROOT printed at session start>/tools/precommit
```

Keep any lines that are already in there. Use this file, not their shell profile. An IDE or a GUI git client often does not load a profile, and the checks would then be silently off for the person least likely to notice.

Then prove it works rather than assuming it does. In a scratch directory, not one of their repos:

```sh
python3 "$JITTER_ROOT/tools/precommit/path_leak_check.py" --staged
```

## 2. The shared git hook

The checks above only run if the repo actually calls the shared hook from `JitterCompany/git_utils`. Look first:

```sh
git config --get core.hooksPath
ls -l .git/hooks/pre-commit
```

One of those two should point into a `git_utils` clone. If neither does, the hook is not installed and the checks will never run. Offer the global setting, which covers every repo at once:

```sh
git config --global core.hooksPath /path/to/git_utils/scripts
```

If they have no clone of `git_utils`, say where it is (`github.com/JitterCompany/git_utils`, public) and let them clone it where they keep their tools. Do not clone it into a project repo.

A repo can still add its own `.git-pre-commit`, which the shared hook runs after the rest.

## What needs no setup

- The rules, the edit-time checks and the push guard come with the plugin.
- The `jitter-report` Typst package is linked at session start. Confirm with `ls ~/.local/share/typst/packages/local/jitter-report` if a report fails to import it.

## If they say no

Write the marker anyway and move on. Mention that `setup-extras` will do it later if they change their mind. Do not raise it again in the same session.
