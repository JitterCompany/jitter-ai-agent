# Jitter hardware rules

Loaded by the `jitter-hw` plugin. Enable it in hardware repos.

## Repos and submodules

- Never commit or push from inside a project's submodule, `KicadComponents` included. Ask the user first, then work in that library's own source tree, on its own branch.
- Public JitterCompany repos never name a customer or a project code.
- Strip references to the source project from files and commit messages when moving a design between repos.
- Documentation about modules, antennas and RF belongs in the hardware repo, not the firmware repo.

## CI and releases

- A new hardware project sets up CI on [JitterCompany/pcb_release](https://github.com/JitterCompany/pcb_release): the submodule, the `ci-hardware` and `ci-hardware-release` workflows, `release.toml` and `pinmap.config.toml` per board. The `pcb-ci-setup` skill does this.

## Tooling

- Use `kicad-cli` instead of parsing KiCad files by hand. It exports netlists, BOMs, gerbers, PDFs and 3D models, and it stays correct across file-format changes.
- For anything `kicad-cli` does not cover, write a script (Python) and keep it in the repo. Do not hand-parse s-expressions inline in a one-off shell command.
- Check whether the project already has tooling for the job, such as `hardware/tools/pcb.sh`, before writing a new script.

## Pinmaps

- `[reserved]` lists the peripherals the firmware needs internally. It is not a way to park a spare GPIO.

## Power integrity and EMC

Push back on outdated textbook advice, with a reason:

- No split ground planes. One solid reference plane, partition by placement.
- No mixed-value decoupling stacks (100nF plus 10nF plus 1nF on one pin). Use fewer, larger caps with low ESL.
- No ferrite in a supply rail by default. It rings with the bulk cap unless it is damped on purpose.

## Simulation

- Never `apt install ngspice` on a machine with KiCad from the PPA. The stock package pulls `libngspice0`, which owns the same `libngspice.so.0` as `libngspice-kicad`, so apt removes the KiCad build and the built-in simulator stops working. Use an isolated unpacked copy instead.
- ngspice types every element by the first letter of its refdes. A resistor named `L_R2_1` simulates as an inductor and ERC will not catch it. Read the generated netlist before trusting a result.
