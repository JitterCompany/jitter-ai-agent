// Jitter house style for engineering reports.
//
//   #import "@local/jitter-report:0.1.0": *
//   #show: report.with(
//     kind: "TEST REPORT",
//     title: "EMC filter bench measurement",
//     subtitle: "platform1-485-filter",
//     doc-id: "2517-HW-TR-002",
//     rev: "1.0",
//     date: "24 September 2026",
//     meta: (("To", "Customer B.V."), ("Performed by", "S. de Wit")),
//   )
//
// The colours and the logo are the same ones the offerte template uses. They live here so a
// report does not carry its own copy of the brand, which is how the first two reports drifted.

#let jitter-blue = rgb("#0891b2")
#let jitter-dark = rgb("#0f172a")
#let jitter-gray = rgb("#64748b")
#let jitter-light = rgb("#f8fafc")
#let jitter-rule = rgb("#e2e8f0")

#let ok-green = rgb("#15803d")
#let att-amber = rgb("#b45309")

#let jitter-logo(height: 22pt) = image("jitter-logo-dark.svg", height: height)

#let company = (
  name: "Jitter B.V.",
  street: "Schieweg 93",
  postcode: "2627AT",
  city: "Delft",
  country: "The Netherlands",
  phone: "+31 15 455 05 74",
  email: "info@jitter.company",
  web: "jitter.nl",
  kvk: "97502537",
  vat: "NL868080160B01",
)

// ---- verdicts --------------------------------------------------------------

#let pill(txt, col) = box(
  fill: col.lighten(88%),
  stroke: 0.5pt + col.lighten(45%),
  radius: 2.5pt,
  inset: (x: 4pt, y: 1.5pt),
  text(fill: col, weight: "bold", size: 6.5pt, txt),
)

#let PASS = pill("PASS", ok-green)
#let FAIL = pill("FAIL", rgb("#b91c1c"))
#let ATTENTION = pill("ATTENTION", att-amber)
#let OPEN = pill("OPEN", jitter-gray)
#let NO-ACTION = pill("NO ACTION", jitter-gray)

// Dutch equivalents, for a report written in Dutch.
#let VOLDOET = pill("VOLDOET", ok-green)
#let AANDACHT = pill("AANDACHT", att-amber)
#let GEEN-ACTIE = pill("GEEN ACTIE", jitter-gray)

// ---- building blocks -------------------------------------------------------

/// A test point, a net name or any other identifier that is read off the board.
#let tp(body) = text(font: ("Liberation Mono", "DejaVu Sans Mono"), size: 8pt, body)

/// A results table. Pass the column widths, then the header cells, then the rows.
#let restable(cols, breakable: true, ..cells) = block(breakable: breakable)[
  #set text(size: 8.2pt)
  #set par(justify: false, leading: 0.55em)
  #let all = cells.pos()
  #table(
    columns: cols,
    stroke: 0.5pt + jitter-rule,
    inset: (x: 6pt, y: 5pt),
    align: (left + horizon),
    fill: (_, y) => if y == 0 { jitter-light },
    table.header(..all.slice(0, cols.len())),
    ..all.slice(cols.len()),
  )
]

/// A callout. The first one in a report is the summary, titled "Result in brief".
#let note(title, body, col: jitter-blue) = block(
  width: 100%,
  fill: jitter-light,
  stroke: (left: 2.5pt + col),
  inset: (x: 10pt, y: 9pt),
  radius: 1pt,
  breakable: false,
)[
  #text(weight: "bold", size: 9pt, fill: col, title) \
  #v(1pt)
  #set text(size: 9pt)
  #body
]

/// A measurement or simulation plot. Every one needs a caption that says what to look at.
#let plot(file, caption, width: 80%) = figure(image(file, width: width), caption: caption)

// ---- the document ----------------------------------------------------------

#let report(
  kind: "TEST REPORT",
  title: none,
  subtitle: none,
  doc-id: none,
  rev: "1.0",
  date: none,
  meta: (),
  lang: "en",
  body,
) = {
  set document(title: title, author: (company.name,))

  set text(
    // Helvetica first, with a deterministic fallback so a machine without it still
    // renders the same layout instead of picking something arbitrary.
    font: ("Helvetica Neue", "Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"),
    size: 10pt,
    fill: jitter-dark,
    lang: lang,
  )
  set par(justify: true, leading: 0.65em, spacing: 1.15em)
  set heading(numbering: "1.1")

  show heading.where(level: 1): it => block(sticky: true, above: 1.6em, below: 0.7em)[
    #set text(size: 15pt, weight: "bold", fill: jitter-blue)
    #it
  ]
  show heading.where(level: 2): it => block(sticky: true, above: 1.3em, below: 0.5em)[
    #set text(size: 12pt, weight: "bold", fill: jitter-dark)
    #it
  ]
  show heading.where(level: 3): it => block(sticky: true, above: 1.1em, below: 0.4em)[
    #set text(size: 10.5pt, weight: "semibold", fill: jitter-gray)
    #it
  ]

  set list(indent: 0.8em, marker: text(fill: jitter-blue, weight: "bold")[--])
  set enum(indent: 0.8em)
  show link: it => text(fill: jitter-blue, it)
  show figure.caption: it => [
    #set text(size: 8pt, fill: jitter-gray)
    #it
  ]
  show figure: set block(above: 1.2em, below: 1.4em)
  show table.cell.where(y: 0): set text(fill: jitter-dark, weight: "bold", size: 8pt)

  // ---- cover ----
  page(
    paper: "a4",
    margin: (x: 2.5cm, top: 3cm, bottom: 1.5cm),
    header: none,
    footer: none,
    background: place(
      top + left,
      rect(width: 100%, height: 6pt, fill: jitter-blue, stroke: none),
    ),
  )[
    #jitter-logo(height: 32pt)

    #v(1fr)

    #text(size: 13pt, weight: "bold", fill: jitter-blue, tracking: 3pt)[#kind]
    #v(10pt)
    #text(size: 28pt, weight: "bold", fill: jitter-dark, tracking: -0.5pt)[#title]
    #if subtitle != none [
      #v(6pt)
      #text(size: 13pt, fill: jitter-gray)[#subtitle]
    ]
    #if doc-id != none [
      #v(8pt)
      #text(size: 10.5pt, fill: jitter-gray)[\[#doc-id\]]
    ]

    #v(28pt)
    #line(length: 4cm, stroke: 2pt + jitter-blue)
    #v(24pt)

    #set text(size: 10pt)
    #set par(justify: false)
    #grid(
      columns: (4.5cm, auto),
      row-gutter: 9pt,
      ..meta.map(((label, value)) => ([*#label*], [#value])).flatten(),
      [*From*], [#company.name],
      [*Date*], [#date],
      [*Version*], [#rev],
    )

    #v(1fr)

    #set text(size: 8pt, fill: jitter-gray)
    #company.street · #company.postcode #company.city · #company.country \
    #company.phone · #company.email · #link("https://" + company.web)[#company.web] \
    KvK #company.kvk · VAT #company.vat

    #counter(page).update(0)
  ]

  // ---- body pages ----
  set page(
    paper: "a4",
    margin: (top: 2.8cm, bottom: 2.2cm, left: 2.5cm, right: 2.5cm),
    header: {
      set text(size: 8pt, fill: jitter-gray)
      grid(
        columns: (1fr, auto),
        align: (left + horizon, right + horizon),
        jitter-logo(height: 14pt),
        box(fill: jitter-blue, radius: 2pt, inset: (x: 6pt, y: 3pt))[
          #text(fill: white, weight: "bold", size: 8pt)[#context counter(page).display()]
        ],
      )
      v(6pt)
      line(length: 100%, stroke: 0.5pt + jitter-rule)
    },
    footer-descent: 8pt,
    footer: {
      line(length: 100%, stroke: 0.5pt + jitter-rule)
      v(6pt)
      set text(size: 7.5pt, fill: jitter-gray)
      grid(
        columns: (1fr, auto),
        [#company.name · #doc-id rev #rev],
        [#date],
      )
    },
  )

  body
}
