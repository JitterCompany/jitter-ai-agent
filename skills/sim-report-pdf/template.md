---
title: "<Subject>: <What Was Simulated>"
date: "YYYY‑MM‑DD"
---

<Circuit under test:>

- <component / value>
- <component / value>
- <optional variant>

**Target:** ≤ **<criterion>** in the <range>.

> *Note:* <caveat — a non-physical artefact, or why an operating point is
> unrealistic. Renders amber; keep limitations visible.>

| # | Case | <param> | <param> | <verdict column> |
|---|------|:-------:|:-------:|:----------------:|
| 1 | **<worst corner>** | | | **<result>** |
| 1b | + <variant> | | | <result> |
| 2 | <bench / sanity check> | | | <result> |
| 3 | <model-based verification> | | | <result> |

---

## 1. <Case name>

<Two or three sentences: what was swept, and what it proves. State the number.>

![<schematic caption>](<schematic>.png){width=78%}

### 1a. <Variant>

<What changed and why it matters.>

![<caption>](<plot>.png){width=62%}

### 1b. <Variant>

<What changed and why it matters.>

![<caption>](<plot>.png){width=62%}

---

## 2. <Verification case>

<Why this cross-checks case 1.>

![<schematic caption>](<schematic>.png){width=88%}

![<caption A>](<plot-a>.png){width=48%}
![<caption B>](<plot-b>.png){width=48%}

*Left: <A>. Right: <B>.*

---

*All plots: <axes>, <sweep type>, <source amplitude>.*
