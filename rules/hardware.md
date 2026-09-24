# Jitter hardware rules

Home of the `H` rules. Loaded automatically in a repo that contains KiCad files, on top of `core.md`.

## Repos and submodules

Already in `core.md`, they apply here as written: W6 submodules (`KicadComponents` is the usual one), C1 no customer or project code in a public repo and no source-project references when moving a design, C4 hardware documentation belongs in the hardware repo. H1 to H4 were those same rules under a second id and are retired.

## KiCad rewrites files on open

Opening a project is enough for KiCad to rewrite `.kicad_pro`, and it drops things while doing it. ERC and DRC exclusions are the usual casualty: a list of 13 reviewed exclusions comes back empty, and the next CI run is suddenly full of violations that were signed off months ago.

- **H5** Check `git status` and `git diff` on `*.kicad_pro` before committing, even when the intent was only to look at a schematic.
- **H6** Run `python3 "$JITTER_ROOT/tools/kicad_project_check.py"`. It compares the working copy against git and reports cleared exclusions, dropped severity overrides, emptied text variables and changed net classes.
- **H7** Restore what was cleared with `git checkout -- <file>`, or re-apply the exclusions in KiCad, before committing anything else in that repo.
- **H8** Never bulk-accept a `.kicad_pro` diff. Read it, it is JSON and it is short.

## CI and releases

- **H9** A new hardware project sets up CI on [JitterCompany/pcb_release](https://github.com/JitterCompany/pcb_release): the submodule, the `ci-hardware` and `ci-hardware-release` workflows, `release.toml` and `pinmap.config.toml` per board. The `pcb-ci-setup` skill does this.

## Tooling

- **H10** Use `kicad-cli` instead of parsing KiCad files by hand. It exports netlists, BOMs, gerbers, PDFs and 3D models, and it stays correct across file-format changes.
- **H11** For anything `kicad-cli` does not cover, write a script (Python) and keep it in the repo. Do not hand-parse s-expressions inline in a one-off shell command.
- **H12** Check whether the project already has tooling for the job, such as `hardware/tools/pcb.sh`, before writing a new script.

## Pinmaps

- **H13** `[reserved]` lists the peripherals the firmware needs internally. It is not a way to park a spare GPIO.

## Power integrity and EMC

Push back on outdated textbook advice, with a reason:

- **H14** No split ground planes. One solid reference plane, partition by placement.
- **H15** No mixed-value decoupling stacks (100nF plus 10nF plus 1nF on one pin). Use fewer, larger caps with low ESL.
- **H16** No ferrite in a supply rail by default. It rings with the bulk cap unless it is damped on purpose.

## Simulation

- **H17** Never `apt install ngspice` on a machine with KiCad from the PPA. The stock package pulls `libngspice0`, which owns the same `libngspice.so.0` as `libngspice-kicad`, so apt removes the KiCad build and the built-in simulator stops working. Use an isolated unpacked copy instead.
- **H18** ngspice types every element by the first letter of its refdes. A resistor named `L_R2_1` simulates as an inductor and ERC will not catch it. Read the generated netlist before trusting a result.
