---
name: clear-docs
description: Write or rewrite technical documentation in a clear, simplified style, about 70% of the way to ASD-STE100 Simplified Technical English. Use for ADRs, READMEs, interface specs, test and bring-up procedures, and issue or PR descriptions, and when the user asks to make a document clearer, simpler, more readable for non-native readers, or "more STE".
---

# Clear technical documentation

ASD-STE100 is the controlled English of aerospace maintenance manuals. Full STE is too strict
for engineering docs: it bans most words outside its dictionary. Take its patterns, not its
word list. The goal is text that a colleague with English as a second language reads once
and understands, and that a translation tool cannot get wrong.

The `P` rules in `rules/prose.md` apply as well. This skill adds to them.

## Rules

**Sentences**

- One instruction or one fact per sentence. Split at "and", "which", "so that" when each
  part can stand alone.
- About 20 words or fewer for a description, 15 or fewer for an instruction. A longer
  sentence is fine when a split makes it less clear.
- Active voice. Say who does it: "The host cuts the power", not "Power is cut".
- Instructions in the imperative: "Wait 3 s", not "It is recommended to wait 3 s".
- Give the reason as its own sentence, after the fact: "Keep VCC off for 2 s. Reason: the
  bulk capacitors keep the module on for about 1 s."

**Words**

- One term for one thing, everywhere in the document. Do not switch between "cut the power",
  "remove the supply" and "power down" for the same action. Define a term once if it is not
  obvious.
- One meaning per word. "Off" is a state. Do not also use it as "away".
- Prefer the simple word: use, start, stop, make sure, about, more than, less than. Avoid
  utilise, commence, ensure that, approximately, in excess of.
- Spell out what "this", "it" and "that" point to when the sentence before has more than one
  candidate.
- No "e.g." or "i.e." in running text: "for example" or a list. No Latin, no idioms, no
  phrasal verbs that a translation tool can misread ("beats", "falls short", "kick in").
- Numbers with units and ranges: "3.58 to 3.90 V", "65 s or less". State the condition a
  value holds for.

**Structure**

- Lists for steps and for parallel points. Number the steps when the order matters.
- A table when two or more items share the same attributes.
- Each item in a list has the same grammatical form.
- Headings that say what the section holds: "What the driver does now", "Problems".
- Warnings and limits stand alone, before the step they apply to.

## Where to relax (the other 30%)

- Technical terms, part numbers, signal names, units and standard abbreviations stay as
  they are. Do not explain `VBAT`, `eFuse` or `URC` to an engineer.
- Keep a compound sentence when the two halves only make sense together, such as a
  condition and its result.
- Prose is fine for the context or the reasoning of an ADR, as long as each sentence follows
  the sentence rules.
- Do not chase a word count. Clarity wins over the limit.

## Document types

- **ADR:** context (facts and constraints, no opinions), decision (what we do, in the
  imperative or present tense), consequences (positive, negative, neutral as lists),
  alternatives (each with pros and cons). Mark what is measured and what is simulated or
  estimated.
- **Issue:** what the source or spec says, what the code does now (with file:line), the
  problems as a numbered list. For each problem: what happens, why it is wrong, what to do
  or what to check.
- **PR description:** what changed, why, how it was tested, what is open. No narrative of
  how the work went.
- **README:** what it is, how to use it, limits. Link to the ADR for the reasoning instead
  of repeating it.
- **Procedure:** prerequisites, numbered steps with one action each, the expected result
  after a step that can fail.

## Examples

Bad:

> It is suggested that the supply should not be removed until the module has completed its
> shutdown, since otherwise flash corruption may occur, and if the URC is never received a
> forced cut after 65 s is acceptable.

Good:

> 1. Wait for `POWERED DOWN`. Then wait 3 s and cut the power.
> 2. If `POWERED DOWN` does not come in 65 s, cut the power.
>
> Do not cut the power while the module runs. This can corrupt its flash.

Bad:

> A card without 2G at 2.0 A also runs on a host that falls somewhat short.

Good:

> A card without 2G draws 2.0 A or less. Thus it also runs on a host that cannot supply the
> full 2.7 A.

## Check

1. Run `python3 "$JITTER_ROOT/tools/prose_check.py" <files>` for the P rules a script can
   see.
2. Read the text once as the target reader: an engineer with English as a second
   language, who does not know the project. Mark every sentence you had to read twice and
   rewrite it.
3. When you rewrite an existing document, keep every fact and value. Diff the result
   against the original and check that no number, condition or limit changed or went
   missing. A rewrite that inverts a sentence is worse than no rewrite.
