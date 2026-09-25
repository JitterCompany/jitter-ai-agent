---
name: pcb-ci-setup
description: Set up (or extend) the shared Jitter KiCad hardware CI in a repo: the JitterCompany/pcb_release submodule, the ci-hardware / ci-hardware-release workflows, per-board release.toml and pinmap.config.toml, and the measured skip=/todo= board list. Use when asked to "set up the hardware CI", "add the KiCad checks/gates", "add a board to CI", "make the pinmap gate run", or to cut a hw-v* manufacturing release.
---

# Jitter hardware CI (pcb_release)

Five gates over every KiCad board in a repo. All logic lives in
**https://github.com/JitterCompany/pcb_release** (public), called as two reusable GitHub
workflows. A consumer repo states only its board list.

## Read the upstream docs, do not restate them

Paths are inside `hardware/tools/pcb_release/`.

| file | holds |
|---|---|
| `README.md` | gates, workflow inputs, `skip=`/`todo=` syntax, local commands, releasing |
| `docs/install.md` | submodule, both workflow files, version pinning, local requirements |
| `docs/gates.md` | what each gate checks and why, including the 3D finding categories |
| `docs/release-toml.md` | every `release.toml` field with its default, identity checks |
| `docs/deliverables.md` | what a release writes into `production/` and `customer/` |
| `scripts/generate_pinmap.py` | `pinmap.config.toml` schema, in the `load_config` docstring |

Reference installs: built first for **5101-btbenergy-zonneboiler**, also in
2607-telecom-displays, 2507-vpinstruments-transmitter-electronics,
4108-frogwatch-hardware. Copy the newest one's `ci-hardware*.yml` and `pcb.sh`.

## Install, in this order

Steps are in `docs/install.md`. Layout assumed here is `repo/hardware/<board>/`. For a
repo that is entirely hardware, drop the `hardware/` prefix (vpinstruments does). What the
upstream doc does not say:

1. **Always take the submodule**, at `hardware/tools/pcb_release`, never a `tools-ref` pin
   alone. One SHA then governs both the local copy and CI.
2. **`hardware/tools/pcb.sh`** is the local "would CI pass?" wrapper, not part of
   pcb_release. Copy it verbatim from a sibling repo and fix only `WORKFLOW=` (path depth
   to `ci-hardware.yml`) and the `s|^hardware/|../|` rebase. It parses the workflow's
   `project-dirs:` block, so local and CI cannot disagree.
3. **Name the workflows `ci-hardware.yml` and `ci-hardware-release.yml`** when the repo's
   others are `ci-*`. Keep the `paths:` filter matching `**/ci-hardware.yml`.
4. **`release.toml` per board.** Take the values from that project's previous
   `production/README-manufacturing.txt` rather than inventing them, and say in the file
   where they came from. Delete the `release.toml.example` copies a first run drops beside
   each board, they are noise in `git status`.
5. **`pinmap.config.toml`** in each board with an MCU, refdes asked for if not obvious.
   Generate with `pcb.sh pinmap <board>` and **commit the generated `pinmap.toml`**: the
   gate diffs against it, so firmware sees any pin change in review. Boards with no MCU
   get `skip=pinmap`, since without the config the gate *fails*. (`kicad-pinmap` is the
   by-hand version of this.)

`.gitignore` also wants `.kicad-3d/` (sparse fetch of the shared 3D models), `.ibom/`,
`release.toml.example`, `customer/`, `customer*.zip`, `production*.zip`.

**`[reserved]` in a pinmap config means PERIPHERALS, not pins.** Misreading it has
confused several people. `TIM5 = ""` blocks a timer outright, `TIM4 = "ADC_SYNC"` allows
one net on it, and CI flags any pin whose active alternate lands there. To reserve a
*pin*, use a net name plus a firmware constant.

## Procedure for a repo that is not green yet

The normal case, and the fastest route.

1. Give `skip=pinmap` to every board with no MCU, nothing else.
2. Run everything enforced once:
   `NO_COLOR=1 hardware/tools/pcb.sh > /tmp/all.log 2>&1` (16 boards takes some 10 min).
3. Write each board's failures back as `todo=`, re-run, confirm exit 0. CI is green,
   nothing is silently unchecked, every gap is a visible warning.
4. Write `hardware/CI-STATUS.md` from the log: the gate matrix (enforced and green, todo,
   skip) plus one row per board saying what it still owes. Copy the structure from
   2607-telecom-displays or 4108-frogwatch-hardware.

`pcb.sh <gate> <board>` enforces that board's `todo=` gates, which is how you find out one
has gone green. In the log, `SCHEMA (dnp-lint)` belongs to **erc** and `SCHEMA (pos>=bom)`
to **drc**.

## Things that will bite

* **`release.toml` is a prerequisite for two gates, not just releases.** Without it both
  `SCHEMA (pos>=bom)` (part of `drc`) and `drift` fail on every board, so a repo's first
  run is red everywhere for one boring reason.
* **`todo=drift` is correct for a board that has never been released**, not a defect.
* **`3d` failures are usually the GUI-only `:JITTER:model.step` alias.** Fix is mechanical:
  `${JITTER}/model.step`. Those shared models need no `model-dirs:` entry, CI
  sparse-fetches them from KicadComponents.
* **`kicad-cli` must be at least the board's KiCad version**, locally and in the CI
  container image. It cannot open files newer than itself.
* **Don't edit .kicad_sch or .kicad_pcb while KiCad has them open** (`~*.lck` present).
  Leave design fixes to the user, record them in CI-STATUS.md.
* Wiring and cable drawings are not boards. Leave them out of the list entirely.

## Releasing

Follow `README.md`, "Releasing a board". Two Jitter duties it does not state: commit every
`release_spec.toml` out of the `release-specs` artifact, and keep the release workflow's
exemptions identical to ci-hardware.yml, since a release runs the same gates.
