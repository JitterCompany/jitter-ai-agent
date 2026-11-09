# jitter-ai-agent

The shared rules, skills and hooks. `README.md` explains the layout, the `agent-rules` skill the workflow for a change.

- Before every push, run `python3 tools/ci_local.py`. It runs exactly the steps in `ci.yml`, including the path-leak check on every tracked file, so a home path with dots as the user name fails here too. Write `/home/<user>`.
- Run headless test sessions of the plugin through `tools/agent_sandbox.sh`, never plain `claude -p`. A scripted "yes, set it up" otherwise writes the real user's onboarding marker and config.
- A change to a skill, rule or hook bumps the version in `.claude-plugin/plugin.json` and `marketplace.json`.
