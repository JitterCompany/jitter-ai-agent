---
name: kicad-pinmap
description: Generate a firmware pin map (TOML) for an MCU from a KiCad schematic, with alternate functions, timers and EXTI. Use to map MCU pins to nets or check pin and timer assignments.
---

# KiCad to firmware pin-map

Produce a per-pin net, alternate-function and EXTI reference for an MCU (e.g. U1) so a
firmware engineer can write the HAL pin config, and flag assignment problems (double
drive, peripheral double-booking, EXTI collisions, fixed-function pins).

## Where the tool lives, do NOT re-implement or vendor it

The generator is `scripts/generate_pinmap.py` in **`JitterCompany/pcb_release`** (public).
That is the single source of truth. This skill deliberately bundles no copy: a vendored
fork silently drifted from it once and that is exactly the failure mode to avoid.

- **Project already uses pcb_release** (has `hardware/tools/pcb_release/`, i.e. most
  Jitter hardware repos): drive it through the project's own entry point,
  `hardware/tools/pcb.sh pinmap` (`pinmap-check` / `pinmap-drift` for CI). Never call the
  script directly there, the wrapper knows the project's paths.
- **Any other project**: clone it and call the script directly.
  `git clone --depth=1 https://github.com/JitterCompany/pcb_release.git`

Read these rather than restating them:

| file | holds |
|---|---|
| `scripts/generate_pinmap.py`, `load_config` docstring | the `pinmap.config.toml` schema |
| `scripts/generate_pinmap.py` header, `--help` | CLI flags, the two netlists, the modes |
| `docs/gates.md`, `pinmap` section | what the CI gate checks, why check and drift are separate jobs |
| `README.md`, "Running it in CI" | the board list, `skip=pinmap` for a board with no MCU |

## GOLDEN RULE, use the netlist, never pin geometry

Pin to net MUST come from the **kicad-cli netlist**. Do NOT match label coordinates to pin
coordinates. Symbol libraries are **Y-up** while the schematic sheet is **Y-down**, so a
naive transform silently **mirrors the entire pinout** into something self consistent but
wrong. This burned a whole session once, and it passed spot checks until pins on opposite
ends of the symbol were compared. Only pull *static* per-pin data (name, alternate
functions) from the symbol, that has no geometry dependence. File-parser libraries
(kiutils, kicad-skip) do not solve connectivity either. Only the netlister does.

**Intent CANNOT come from the ROOT net name, hence TWO netlists.** A net spanning
hierarchical sheets gets one canonical name, so an `_IRQ` or `_A` suffix on the MCU sheet
can VANISH (the net shows as `RI`, not `CELLULAR_UART_RI_IRQ`). The standalone sheet
netlist keeps the local labels, which is why the generator exports both.

## Procedure

1. **Run it.** Both netlists are auto-exported, so normally just `pcb.sh pinmap`, or
   `generate_pinmap.py ROOT.kicad_sch --config pinmap.config.toml` outside a Jitter repo.
   (kicad-cli may emit a harmless `/tmp/.kicad-wk-helpers` symlink warning, ignore it.)
2. **Read the SANITY WARNINGS block** at the top of the output and reconcile each against
   the schematic before trusting the map.
3. **Commit the generated file.** It is the CLEAN map. Warnings go to CI only, never into
   the file, so drift tracks the real pin to net to function mapping.

## Config, `<project>/pinmap.config.toml`

Schema is in the script's `load_config` docstring. The judgement calls:

- It is deliberately **NOT** part of `release.toml`. A pin map is a schematic-stage
  artifact, consumed by firmware long before any manufacturing release.
- No config file means a clean local no-op, while the CI gate fails, on purpose.
- `ignore` is a suppression list of warning substrings. Keep it SHORT and justified.
- `[reserved]` is for PERIPHERALS the firmware owns internally, never a way to reserve a
  *pin*. `TIM5 = ""` blocks a timer outright (an RTIC monotonic), `TIM4 = "ADC_SYNC"`
  allows one net on it.
- `[groups]` only needs entries for signals whose subsystem the net name does not convey.
  Default grouping is the net name's first `_`-token.

## Sanity checks to eyeball

`docs/gates.md` lists what the checker enforces. The ones worth knowing by heart:

- **Fixed-function pins**: SWDIO/SWCLK must be PA13/PA14, LSE on PC14/PC15 (OSC32). A
  crystal on any other pin cannot oscillate.
- **Double drive** is keyed on the FULL sheet-qualified net identity, so three different
  local `RESET` labels on three sheets stay distinct instead of looking triple-driven.
- **Reserved peripherals** are marked `!` in each pin's annotation, so the engineer sees
  which AF options are off limits.
- **EXTI convention.** Declare an intended interrupt by **suffixing the net `_IRQ`** (or
  `_INT`/`_EXTI`), which is what makes the shared-line collision checkable. The suffix is
  stripped from the emitted key, and an `_IRQ` label that resolves to no pin warns. Lines
  0-15 are GPIO-only, peripheral sources (PVD, RTC, COMP, wakeups) sit on 16 and up, so
  they never contend with a pin.

## Adapting

The TOML is a human reference, not machine-parsed downstream, so extend it freely with
peripheral or AF blocks, notes and revision deltas, matching the target project's existing
`pins_vx.toml`. Per-project tuning belongs in `pinmap.config.toml`, not in the script.
