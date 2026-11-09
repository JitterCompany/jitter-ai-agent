---
name: circuit-advice
description: Jitter positions on grounding, ground splits, decoupling, supply filtering, ferrites and EMC. Use when advising on, reviewing or troubleshooting a circuit or schematic, a noisy rail or a failed EMC test.
---

# Advising on a circuit

Read the "Power integrity and EMC" section of `rules/hardware.md` in this plugin and apply it. The short form:

- One solid reference plane, partition by placement. No split ground planes.
- Fewer, larger caps with low ESL. No 100nF plus 10nF plus 1nF stacks on one pin.
- No ferrite in a supply rail by default, because it rings with the bulk cap unless it is damped on purpose.

Say why, not just what, and name the mechanism: return-current path, ESL and the antiresonance between two capacitors, the LC formed by a ferrite and the bulk cap. The point is that the person can check the reasoning, and can disagree with it.

Two habits that matter more than the positions themselves:

- Distinguish what you have verified from what you suspect (W7). A plausible mechanism stated as fact wastes a bench session.
- Ask for the measurement when one would settle it. A scope shot of the rail at the load beats an argument about decoupling.

For the KiCad and lab rules, including the ngspice trap, read the rest of `rules/hardware.md`.
