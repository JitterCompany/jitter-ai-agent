---
name: knowledge
description: Look things up in, and add to, the shared Jitter knowledge base (JitterCompany/jitter-knowledge) - parts and their errata, debug tools, protocols, RF, procedures, lessons learned, and per-customer setups. Use before guessing a chip quirk, a tool workaround, a protocol detail or how a customer's setup works, when starting on a customer's project, and when the user says "add this to the knowledge base", "remember this for everyone" about a fact, or "what do we know about X".
---

# The shared knowledge base

A private repo of markdown files with YAML frontmatter, in the Open Knowledge Format. The session header gives the clone as `JITTER_KNOWLEDGE=<path>`. If it says the knowledge base is not set up, or the line is missing, do section 3 of the `setup-extras` skill first.

The conventions live in the repo's own `README.md`, under "Writing an entry". Read that before writing an entry. This skill does not repeat them.

## Knowledge, skill or rule?

- A fact about the world goes here: "the STM32L4 I2C misses a STOP after a NACK", "this customer's test jig needs 12 V".
- A procedure people carry out goes here too, as `type: Procedure`: salary administration, a board bring-up.
- A procedure an agent carries out is a skill, and a constraint on how we work is a rule. Both go through the `agent-rules` skill.
- A fact about one repo goes in that repo's `CLAUDE.md`.

The full table is in the jitter-ai-agent README, under "Skill, knowledge or rule?".

## 1. Look something up

1. Grep first, by part number, tool name, customer slug or error message:
   `grep -ril "stm32l4" "$JITTER_KNOWLEDGE/knowledge"`
2. Browse when you do not know the word: `knowledge/index.md`, then the folder's `index.md`, then the concept. Read only what you need.
3. On a customer's project, read `knowledge/customers/<slug>/index.md` once at the start.
4. Weigh what you find:
   - **Reviewed**: a `verified` entry by a `human:` is at least as new as `generated.at`. Treat it as fact and cite the file.
   - **Unreviewed**: treat it as a hypothesis and say so when you use it.
   - Past `stale_after`, or `status: deprecated`: say so, and check against the current datasheet or tool.
5. Nothing found is an answer too. Say so, then work it out the usual way.

## 2. Add or update an entry

Write only when asked. When a session turns up a non-obvious fact that cost real time, such as an erratum, a workaround or a measured limit, offer once at the end: "Add this to the knowledge base?"

1. **Search for an existing concept** (section 1). Update it rather than adding a near-copy.
2. **Prepare the clone.** It must be clean and on `master`. If it is not, ask rather than stash or switch someone's work. Then:
   ```sh
   git -C "$JITTER_KNOWLEDGE" pull --ff-only
   git -C "$JITTER_KNOWLEDGE" switch --no-track -c knowledge/<slug>
   ```
3. **Write the entry** as the README says. Set `generated.by` to `claude-code/<your model id>` and `generated.at` to today. Never write `verified`, because CI stamps it with the reviewers when the PR merges. Put the evidence in `sources`: a datasheet URL, `logboek:<log name>`, or a repo path.
4. **Say what is measured and what is a guess** in the body. Link a datasheet, never paste it. No NDA text, credentials or contact details.
5. **Check:**
   ```sh
   cd "$JITTER_KNOWLEDGE" && python3 scripts/build_index.py && python3 scripts/check.py
   ```
6. **Commit** the concept and the index files it changed, by name. Push the branch and open a PR, which brings up an approval prompt (W2). Give the user the link. Someone else reviewing it is what makes it trusted.

## 3. Distill the logboek

The logboek is the journal on the office NAS, reachable only from the office network. Its location is `LOG_DIR` in the `jit` tool's `config.cfg`. When asked to turn logs into knowledge:

1. Pick a theme, such as a tag or a part, and read those logs. They are in Dutch and English, with `title`, `date`, `author`, `project` and `tags` frontmatter.
2. Write one concept per fact that still holds. Leave out the diary: dates, dead ends, "update 13:00".
3. Cite each log as `logboek:<file name without .md>` and copy `project` across.
4. Put the whole theme in one PR, so one reviewer sees it together.

## 4. Export an entry to PDF

`scripts/pdf.sh knowledge/<folder>/<entry>.md [out.pdf]` in the clone renders one entry with the Jitter cover and header, screenshots included. It needs `typst` and the `offerte` repo cloned next to `jitter-knowledge`. The `jitter-pdf` skill has the traps.
