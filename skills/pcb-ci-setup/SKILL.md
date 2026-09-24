---
name: pcb-ci-setup
description: Set up (or extend) the shared Jitter KiCad hardware CI in a repo: the JitterCompany/pcb_release submodule, the ci-hardware / ci-hardware-release workflows, per-board release.toml and pinmap.config.toml, and the measured skip=/todo= board list. Use when asked to "set up the hardware CI", "add the KiCad checks/gates", "add a board to CI", "make the pinmap gate run", or to cut a hw-v* manufacturing release.
---

# Jitter hardware CI (pcb_release)

Five gates over every KiCad board in a repo: `erc`, `drc`, `3d`, `drift`, `pinmap`.
All logic lives in **https://github.com/JitterCompany/pcb_release** (public), called as
two reusable GitHub workflows. A consumer repo states only its board list.

Built first for **5101-btbenergy-zonneboiler**. Also installed in 2607-telecom-displays,
2507-vpinstruments-transmitter-electronics, 4108-frogwatch-hardware. Copy the newest of
those as the reference, check its `.github/workflows/ci-hardware*.yml` and
`hardware/tools/pcb.sh`.

## Install (≈5 steps)

Repo layout assumed below is `repo/hardware/<board>/`; for a repo that is entirely
hardware, drop the `hardware/` prefix everywhere (vpinstruments does).

1. **Submodule** (gives a local copy *and* pins the CI version through its SHA):

       git submodule add https://github.com/JitterCompany/pcb_release.git hardware/tools/pcb_release

2. **`hardware/tools/pcb.sh`**, local "would CI pass?" wrapper. Copy it verbatim from a
   sibling repo and only fix `WORKFLOW=` (path depth to `.github/workflows/ci-hardware.yml`)
   and the `s|^hardware/|../|` rebase. It parses the workflow's `project-dirs:` block and
   pipes it into the same `pcb-checks.sh` CI runs, so the two cannot disagree.

3. **`.github/workflows/ci-hardware.yml`**, calls
   `JitterCompany/pcb_release/.github/workflows/kicad-checks.yml@master` with
   `tools: hardware/tools/pcb_release` and `project-dirs: |`.
   **`ci-hardware-release.yml`**, same `with:` block against `kicad-release.yml@master`,
   triggered by `workflow_dispatch` + tags `hw-v*`. Name them `ci-hardware*.yml` when the
   repo's other workflows are `ci-*`; keep the `paths:` filter matching `**/ci-hardware.yml`.

4. **`release.toml` per board**, beside its `.kicad_pro`. Declares fab *intent* only
   (finish, mask/silk colour, via treatment, stackup strictness, RoHS/UL94). Take the
   values from that project's previous `production/README-manufacturing.txt` rather than
   inventing them, and say in the file where they came from. A first run drops an
   annotated `release.toml.example` beside every board that lacks one, **delete those
   templates afterwards**, they are noise in `git status`.

5. **`pinmap.config.toml`** in each board that has an MCU: `ref = "U5"` (the MCU refdes , 
   ask if not obvious), `out = "pinmap.toml"`, `ignore = []`, plus optional `[reserved]`
   and `[groups]` (section names in the generated map). **`[reserved]` is only for
   PERIPHERALS the firmware owns internally**, `TIM5 = ""` for a monotonic, `TIM4 =
   "ADC_SYNC"` to allow one net, so CI flags any pin whose active alternate lands on
   one. It is never a way to reserve a *pin*. That intent belongs in a net name plus a
   firmware constant. Misreading it has confused several people.
   Generate with `hardware/tools/pcb.sh pinmap <board>` and **commit the generated
   `pinmap.toml`**, the gate diffs against it, so firmware sees any pin change in review.
   Boards with no MCU get `skip=pinmap`; without the config the gate *fails* rather than
   silently passing. (The older `kicad-pinmap` skill is the by-hand version of this.)

Also add to `.gitignore`: `.kicad-3d/` (sparse fetch of the shared 3D models),
`.ibom/`, `release.toml.example`, `customer/`, `customer*.zip`, `production*.zip`.

## The board list is the whole configuration

```yaml
project-dirs: |
  hardware/debug-tools/debug-base                  todo=erc,drc,3d,drift
  hardware/sma-adapter             skip=pinmap     todo=drc,drift
```

Every gate is enforced for every board unless that board says otherwise:
`skip=` = structurally impossible here (no MCU → no pin map), silent.
`todo=` = applies, not green yet: warns every run, does not fail.
A typo in a gate name is a hard error. `--only <board>` (i.e. `pcb.sh <gate> <board>`)
enforces that board's `todo=` gates, which is how you find out one has gone green.

## Procedure for a repo that is not green yet

This is the normal case and the fastest route:

1. List every board with `skip=pinmap` where there is no MCU, nothing else.
2. Run the whole thing once with everything enforced:
   `NO_COLOR=1 hardware/tools/pcb.sh > /tmp/all.log 2>&1` (a 16-board repo ≈ 10 min).
3. Write each board's failures back as `todo=`, re-run, confirm exit 0.
   Now CI is green, nothing is silently unchecked, and every gap is visible as a warning.
4. Write `hardware/CI-STATUS.md`: the gate matrix (✅ enforced/green, ⚠️ todo,, skip),
   plus one row per board saying what it still owes, from the log. Copy the structure
   from 2607-telecom-displays or 4108-frogwatch-hardware.

Map stage names to gates when reading the log: `SCHEMA (dnp-lint)` belongs to **erc**,
`SCHEMA (pos>=bom)` belongs to **drc**.

## Things that will bite

* **`release.toml` is a prerequisite for two gates, not just releases.** Without it both
  `SCHEMA (pos>=bom)` (part of `drc`) and `drift` fail on every board. So a repo's first
  run shows `drc` + `drift` failing everywhere for one boring reason.
* **`drift` cannot pass until a board has been released once.** It diffs against
  `release_spec.toml`, which only a release build writes; commit that artifact afterwards.
  Until then `todo=drift` is correct and not a defect.
* **`3d` failures are usually the GUI-only `:JITTER:model.step` alias.** kicad-cli cannot
  resolve it, so the part silently vanishes from the STEP. Fix is mechanical:
  `${JITTER}/model.step`. `no_model` findings are real parts (often test points) with no
  3D model at all.
* **`${JITTER}` needs no `model-dirs:` entry**, CI sparse-fetches those models from
  KicadComponents by itself. `model-dirs: NAME=path` is only for a repo's *own* 3D library
  (vpinstruments' `VP_3DMODEL_DIR`), and must be set on *both* workflows.
* **Don't edit .kicad_sch/.kicad_pcb while KiCad has them open** (`~*.lck` present), leave
  design fixes to the user and record them in CI-STATUS.md instead.
* Wiring/cable drawings are not boards; leave them out of the list entirely.
* Local runs need `kicad-cli` ≥ the board's KiCad version and Python 3. CI needs neither
  (KiCad container). `PCB_VERBOSE=1` shows what a passing stage hides.

## Releasing

`git tag hw-v1.0 && git push origin hw-v1.0`, or run the workflow manually. Artifacts per
board: `production__*` (fab), `customer__*` (STEP/PDF/renders/iBOM), `release-spec__*`.
Commit the `release_spec.toml`. Exemptions in the release workflow must mirror
ci-hardware.yml, since a release runs the same gates.

Docs: `tools/pcb_release/README.md`, `docs/install.md`, `docs/gates.md`,
`docs/release-toml.md`, `CONTRIBUTING.md` (for changing the shared repo itself).
