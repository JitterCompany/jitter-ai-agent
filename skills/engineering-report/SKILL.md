---
name: engineering-report
description: Write a Jitter engineering report as a PDF with Typst: board bring-up, a test or measurement report, a simulation report, an EMC or insertion-loss write-up. Use when asked to document results, write up measurements or a simulation, produce a test report, or turn bench or scope data into something a customer reads.
---

# Engineering reports

House style lives in the `jitter-report` Typst package that ships with this plugin, so a report does not carry its own copy of the brand. Install it once per machine:

```sh
JITTER_ROOT=$(cat "${XDG_CACHE_HOME:-$HOME/.cache}/jitter-ai-agent/root")
mkdir -p ~/.local/share/typst/packages/local/jitter-report
ln -sfn "$JITTER_ROOT/typst/jitter-report/0.1.0" ~/.local/share/typst/packages/local/jitter-report/0.1.0
```

## The skeleton

```typst
#import "@local/jitter-report:0.1.0": *

#show: report.with(
  kind: "TEST REPORT",
  title: "EMC filter bench measurement",
  subtitle: "platform1-485-filter",
  doc-id: "2517-HW-TR-002",
  rev: "1.0",
  date: "24 September 2026",
  meta: (
    ("To", "Customer B.V."),
    ("Product", "the filter PCB, production files of 31 August 2026"),
    ("Test objects", "Board 2 as assembled, Board 1 with series parts replaced by 0 ohm"),
    ("Test period", "23 and 24 September 2026"),
    ("Performed by", "S. de Wit"),
    ("Base document", "Report 1: insertion-loss simulation, 21 July 2026"),
  ),
)
```

`From`, `Date` and `Version` are added for you. The package also gives you `note`, `restable`, `plot`, `tp`, `pill` and the verdicts `PASS`, `FAIL`, `ATTENTION`, `OPEN`, `NO-ACTION`, plus `VOLDOET`, `AANDACHT` and `GEEN-ACTIE` for a Dutch report.

`doc-id` is `<project>-HW-TR-<nnn>`, numbered per project, and the number goes up for each report on the same subject. A follow-up names its predecessor under `Base document`, because a reader needs to know which report this one argues against.

## The shape both existing reports use

1. **Result in brief**, a `note` before the first heading. Five or six bullets, each one a conclusion rather than a description. This is the only part most readers finish.
2. **Setup**, with the numbers that make the result reproducible: source and load impedance, supply, instrument, what was and was not connected.
3. **Results**, one section per line or per test, each with its plots and a `restable` of the measured values.
4. **Findings and actions**, a `restable` with a verdict pill per row.
5. **Conclusion and next step**, naming the next test rather than trailing off.

## Writing the results

- State the pass criterion in bold before the evidence, for example *Target: S21 below -40 dB from 10 to 100 MHz*, and say where it comes from.
- Every plot gets a caption that says what to look at, not what it is. "Both lines stay below the target across the band" beats "S21 measurement".
- Compare against the simulation or the previous revision when one exists, and quantify the difference. "Measured is about 10 dB better above 10 MHz" is a finding, "results are good" is not.
- Say what the measurement does not cover. A 50 ohm bench sweep without DC is not the application, and the report should say so before the customer does.
- Generate plots with a script next to the report, writing PNGs beside the `.typ`, so a rerun regenerates the figures. Keep the script in the repo.

## Building

```sh
typst compile report.typ                 # images beside the .typ
typst compile --root .. report.typ       # images in a sibling folder such as ../photos
```

Read the PDF before handing it over. Then check the page breaks: a `restable` is `breakable: false` by default in the places where a split table reads badly.

Two traps on our machines:

- Typst from snap cannot read `/tmp` or another user's home. Build inside the repo.
- If Helvetica is missing the fallback chain handles it. The warning is not an error.

## Where it lives, and going public

The report belongs in the repo of the thing it describes, next to the measurements, not in the offerte repo. Only the brand comes from the package.

If a report is going on the website or to anyone outside the project, anonymise it first: customer name, contact, and any board or product name that identifies them (C1). There is an anonymised bring-up report in the website repo that shows how far that has to go.

## Worked examples

- `2507-vpinstruments-transmitter-electronics/platform1_emc_filter/measurements/2026-09_bench/report/`, a bench measurement against a simulation, English.
- `self/jitter_website/tmp/bringup_report_anon/`, a full board bring-up with per-test verdicts, Dutch, anonymised.

Both predate the package and inline the style by hand. Copy their structure, not their preamble.
