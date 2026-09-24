# Writing style

Applies to everything: chat replies, code comments, doc comments, READMEs, decision records, commit messages, proposals, customer reports.

## Rules

- No em dashes. Use a comma, a full stop, or brackets.
- No long sentences stitched together with semicolons. Two short sentences beat one long one.
- No formal or marketing register. Write the way you would explain it to a colleague at the next desk.
- Prefer a short bullet list or a small table over a paragraph that enumerates things.
- Cut throat-clearing openers such as "It is worth noting that" or "In order to".
- No filler summaries that repeat what was just said.

We do not hide that we use AI. A `Co-Authored-By` trailer on a commit is fine. The point is that the text reads naturally, not that its origin is concealed.

## Examples

Bad:

> It is worth noting that the sensor driver, which is responsible for both the acquisition
> and the filtering of raw samples, must be initialised before the measurement task starts;
> otherwise the first conversion may return stale data.

Good:

> Init the sensor driver before the measurement task starts. The first conversion returns
> stale data otherwise.

Bad:

> The configuration supports three modes, namely continuous mode, which samples without
> interruption, single-shot mode, which takes one sample per trigger, and idle mode, in
> which the ADC is powered down.

Good:

> Three modes:
> - `Continuous`: samples without interruption.
> - `SingleShot`: one sample per trigger.
> - `Idle`: ADC powered down.
