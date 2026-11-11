---
name: clear-docs
description: Write or rewrite technical documentation in a clear style, about 70% of the way to ASD-STE100 Simplified Technical English. Use for ADRs, READMEs, specs, procedures, and issue or PR descriptions, and when asked to make a document clearer or simpler.
---

# Clear technical documentation

ASD-STE100 is the controlled English of aircraft maintenance manuals. Use its patterns, not its
word list. The target reader is an engineer with English as a second language. This reader
must understand each sentence the first time. The `P` rules in `rules/prose.md` also apply.

## Rules

- One fact or one instruction per sentence. About 20 words or fewer.
- Active voice. Say who does the action: "The host cuts the power".
- Instructions in the imperative: "Wait 3 s".
- Give the reason in a separate sentence: "Reason: ...".
- One term for one thing in the full document. One meaning for each word.
- Simple words: use, start, make sure, about. Not utilise, commence, ensure that, approximately.
- No "e.g.", "i.e.", idioms or phrasal verbs that a translation tool can misread.
- If "this", "it" or "that" can refer to two things, use the noun.
- Numbers with units, ranges and conditions: "3.58 to 3.90 V at 25 °C", "65 s or less".
- Numbered steps when the order is important. Lists for parallel points. A table when items
  have the same attributes.

Relax the rules for:

- Technical terms, part numbers and signal names. Keep them as they are.
- Two halves of a sentence that need each other, for example a condition and its result.
- Word counts. A clear long sentence is better than two unclear short ones.

## Structure by document type

| Type | Sections |
|---|---|
| ADR | context (facts only), decision, consequences (positive, negative, neutral), alternatives (pros, cons). Say what is measured and what is simulated or estimated. |
| Issue | what the source or spec says, what the code does now (file:line), numbered problems. For each problem: what occurs, why it is wrong, what to do. |
| PR | what changed, why, how it was tested, what is open. |
| README | what it is, how to use it, limits. Link to the ADR for the reasons. |
| Procedure | prerequisites, numbered steps with one action each, the expected result after a step that can fail. |

## Example

Bad:

> It is suggested that the supply should not be removed until the module has completed its
> shutdown, since otherwise flash corruption may occur, and if the URC is never received a
> forced cut after 65 s is acceptable.

Good:

> 1. Wait for `POWERED DOWN`. Then wait 3 s and cut the power.
> 2. If `POWERED DOWN` does not come in 65 s, cut the power.
>
> Do not cut the power while the module runs. This can corrupt its flash.

## Check

1. Run `python3 "$JITTER_ROOT/tools/prose_check.py" <files>`.
2. Read the text as the target reader. Rewrite each sentence that you must read two times.
3. After a rewrite, compare it with the original. Make sure that no value, condition or limit
   changed or is missing. A rewrite that changes the meaning is worse than no rewrite.
