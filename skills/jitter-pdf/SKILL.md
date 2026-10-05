---
name: jitter-pdf
description: Make any PDF with Typst and the Jitter brand - offertes, quotes, proposals, guides, and markdown or knowledge entries exported to PDF. Prefer it over pandoc or WeasyPrint unless asked.
---

# Jitter documents

Everything lives in `JitterCompany/offerte`, usually cloned at `~/dev/jitter/offerte` or `~/dev/self/offerte`. Look under `~/dev` before cloning it. It serves two jobs: it produces the offertes, and it is the only place that holds the brand in a usable form.

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

## Markdown to PDF

Render the markdown inside Typst with the `@preview/cmarker` package, so the `.md` stays the only copy of the content and the brand comes from `offerte`:

```typst
#import "@preview/cmarker:0.1.8"
#cmarker.render(read("guide.md"), scope: (image: (path, alt: none) => image(path, alt: alt, width: 70%)))
```

Strip YAML frontmatter before rendering, it is not markdown. For a knowledge entry this is done already: `scripts/pdf.sh <entry.md>` in `jitter-knowledge`.

## Traps

- "access denied" on a file you can read: the snap build of Typst is sandboxed (no `/tmp`, no files owned by another user). Build inside the repo, or use the static binary from the typst GitHub releases.
- `--root` must contain every file the document reads. Resolve symlinks with `realpath` first, or a path through a symlinked folder lands outside the root.
- Helvetica is missing on most Linux machines. Add `"Liberation Sans"` as the last font in the stack, it has the same metrics.

## Which route for which document

Prefer Typst. Use pandoc or WeasyPrint only when the user asks for it or the context calls for it, for example a quick unbranded conversion in a repo that already builds that way.

- **This skill:** offertes, any one-off branded document, and markdown exported to PDF.
- **The `engineering-report` skill:** a bring-up, test, measurement or simulation report. It uses the `jitter-report` package, which carries the same brand plus the report furniture (cover, header, footer, verdict pills, results tables).

The prose rules apply with full force here (P1 to P6), because this is the writing a customer reads.
