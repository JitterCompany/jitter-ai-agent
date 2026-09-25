---
name: jitter-pdf
description: Write an offerte, or any Jitter-branded PDF such as a test report or a customer-facing document, using the Typst system in the JitterCompany/offerte repo. Use when asked for a quote, an offerte or a proposal, and whenever a document needs the Jitter cover, logo, colours or house typography rather than plain markdown.
---

# Jitter documents

Everything lives in `JitterCompany/offerte`, usually cloned at `~/dev/jitter/offerte`. It serves two jobs: it produces the offertes, and it is the only place that holds the brand in a usable form.

Needs `typst` on `PATH`. Check with `typst --version` and say so if it is missing rather than falling back to something else.

## What is in there

| Path | What you need it for |
|---|---|
| `brand.typ` | Colours (`jitter-blue`, `jitter-dark`, `jitter-gray`, `jitter-light`, `jitter-rule`) and the `jitter-logo()` helper |
| `assets/` | The logo SVGs, dark and horizontal |
| `template.typ` | The `jitter-offerte` show rule: A4, the Helvetica stack, heading styles |
| `sections/` | Cover page, pricing, guarantee, over-jitter, terms, and the i18n helpers |
| `data/company.json` | Company details, so no document hardcodes them |
| `build.sh` | `typst compile` with `--root` set to the repo, which is what makes the asset paths resolve |

Read that repo's own `CLAUDE.md` before writing content. It holds the language and content conventions, and they are not repeated here so the two cannot drift apart (R13).

## An offerte

1. Copy `example/` to a folder named after the project number.
2. Put the content in the `.json`. The `.typ` beside it only imports the template and hands it the data.
3. Build with `./build.sh path/to/2604-001.typ`, and read the PDF before handing it over.

## Any other branded document

Import the brand rather than re-inventing it:

```typst
#import "brand.typ": *
#import "sections/cover.typ": cover-page
```

Then compile with the offerte repo as the root, so the logo path resolves:

```sh
typst compile report.typ report.pdf --root ~/dev/jitter/offerte
```

Keep the document's own content in its own repo, next to the work it describes, and pull only the brand from here. A test report belongs with the hardware or firmware it tests.

## Which route for which document

- **Typst, this skill:** anything a customer sees, anything that wants the cover and the logo, anything that will be printed.
- **The `sim-report-pdf` skill:** the compact engineering write-up of a simulation, which already has its own pandoc and WeasyPrint flow and a stylesheet tuned for plots and findings tables.

The prose rules apply with full force here (P1 to P6), because this is the writing a customer reads.
