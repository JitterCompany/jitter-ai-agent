---
name: sim-report-pdf
description: >-
  Build a compact A4 PDF engineering report from simulation results, KiCad/ngspice
  plot screenshots plus a findings table, via pandoc + WeasyPrint and a bundled
  print stylesheet. Use when asked to write up, document, or "make a PDF report" of
  simulation results (insertion loss, surge, EMC filter, impedance sweeps), or to
  regenerate/extend an existing sim report. Also covers exporting plots from the
  KiCad simulator to feed it.
---

# Simulation report → PDF

Produces a 3–5 page A4 report: verdict table up front, then one section per
simulated case, each a short paragraph plus its plot. Established for the
platform‑1 EMC filter report (`sim_topology/sim_report/` in the VP transmitter
repo), that is the reference example of the output.

## Toolchain

`pandoc` and `weasyprint`, both on `PATH`. Check with `pandoc -v` and
`weasyprint --version`, and install them if they are missing. **WeasyPrint is the
required PDF engine**, the stylesheet uses `@page` and CSS that LaTeX engines
ignore. Do not fall back to `--pdf-engine=pdflatex`; it silently drops the layout.

```bash
cd <report-dir>
pandoc report.md --css report.css --pdf-engine=weasyprint --resource-path=. -o report.pdf
```

Images are resolved relative to `--resource-path`, so keep the `.md`, the `.css`
and the PNGs in one directory. Verify with `pdfinfo report.pdf`, expect
`Producer: WeasyPrint`, `Page size: 595.276 x 841.89 pts (A4)`, and a sane page
count. A 1-page result usually means images failed to resolve.

## Files here

- `report.css`, the A4 print stylesheet. Copy it next to the `.md`. Compact by
  design: 10.5 pt body, 1.6 cm margins, bordered tables at 9.5 pt, amber
  blockquotes for caveats.
- `template.md`, skeleton with the frontmatter and section pattern.

## Writing conventions

These are what make the report readable at a glance; keep them.

- **YAML frontmatter** with `title:` and `date:`, pandoc renders it as the
  heading block, and `title` becomes the PDF metadata title.
- **Lead with the answer.** Above the first `##`, put the circuit under test as a
  bullet list, the pass criterion in bold (e.g. **Target:** ≤ **−40 dB**, 10–100 MHz),
  and a summary table of every case with its verdict column. A reader who stops
  after page 1 should have the conclusion.
- **One `##` per case, `###` per variant** (1, 1a, 1b, 1c, 2 …). Numbering must
  match the summary table's `#` column.
- **Prose before the plot, never after**, two or three sentences saying what
  changed and what it proves. State the number, don't make the reader read it off
  the curve.
- **Image widths are deliberate**: `{width=78-88%}` for schematics, `{width=62%}`
  for a single plot, `{width=48%}` ×2 for a side-by-side pair followed by an
  italic `*Left: … Right: …*` caption. The `{width=}` attribute is pandoc syntax
  and needs no extra extension.
- **`> blockquote` for caveats**, the non-physical resonance, the unrealistic
  operating point. Renders amber, so honest limitations stay visible instead of
  buried.
- `---` between top-level sections; close with an italic one-liner giving the
  shared plot conditions (axes, sweep type, source amplitude).

## Getting the plots

Screenshots from the KiCad simulator window are what the reference report used , 
export each plot at the same window size so the curves are visually comparable.
Name files after what they show, encoding the varied parameter:
`simplified_filter_worst-case_cmid=188n_par_33n.png`. Use the simulator's cursors
to bracket the band that meets the criterion, and refer to the markers in the
prose (\"Markers ① / ② bracket the band below −40 dB\").

For plots generated headlessly instead, run the isolated ngspice build,
**never `apt install ngspice`** (H17): it removes `libngspice-kicad` and breaks
KiCad's built-in simulator. On a machine that has no isolated copy, unpack the
`.deb` into a private tree and point `LD_LIBRARY_PATH`, `SPICE_LIB_DIR` and
`SPICE_EXEC_DIR` at it.
