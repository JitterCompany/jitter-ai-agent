#!/bin/sh
# Run a headless Claude Code session that cannot touch the real user's plugin state.
#   tools/agent_sandbox.sh [claude args...]      e.g. tools/agent_sandbox.sh -p "What now?" --plugin-dir .
# Markers, the knowledge base path, the checks path and global git config go to a throwaway
# directory, so a scripted "yes, set it up" in a test writes nothing a person relies on.
# Login stays in ~/.claude, so no new sign-in is needed.
set -eu

SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/agent-sandbox.XXXXXX")
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/cache" "$SANDBOX/config" "$SANDBOX/data"
touch "$SANDBOX/gitconfig"

XDG_CACHE_HOME="$SANDBOX/cache" XDG_CONFIG_HOME="$SANDBOX/config" XDG_DATA_HOME="$SANDBOX/data" \
GIT_CONFIG_GLOBAL="$SANDBOX/gitconfig" \
  claude "$@"
