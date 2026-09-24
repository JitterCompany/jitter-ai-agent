---
name: kicad-pinmap
description: Generate a firmware pin-map (TOML) for an MCU from a KiCad schematic: extract net names per pin via the kicad-cli netlist, annotate with alternate functions / timers / EXTI from the symbol, sanity-check, and emit a grouped human-readable reference like the Jitter pins_vx.toml. Use when asked to map MCU pins to nets/functions, produce a firmware pin reference, or check pin/timer/EXTI assignments in a KiCad design.
---

# KiCad → firmware pin-map

Produce a per-pin net + alternate-function + EXTI reference for an MCU (e.g. U1)
so a firmware engineer can write the HAL pin config, and flag assignment
problems (double-drive, peripheral double-booking, EXTI collisions,
fixed-function pins).

## Where the tool lives, do NOT re-implement or vendor it

The generator is `scripts/generate_pinmap.py` in **`JitterCompany/pcb_release`**
(public). That is the single source of truth. This skill deliberately bundles no
copy: a vendored fork silently drifted from it once and that is exactly the
failure mode to avoid.

- **Project already uses pcb_release** (has `hardware/tools/pcb_release/`, i.e.
  most Jitter hardware repos): drive it through the project's own entry point , 
  `hardware/tools/pcb.sh pinmap` (`pinmap-check` / `pinmap-drift` for CI). Never
  call the script directly there; the wrapper knows the project's paths.
- **Any other project**: clone it and call the script directly.
  `git clone --depth=1 https://github.com/JitterCompany/pcb_release.git`

## GOLDEN RULE, use the netlist, never pin geometry
Pin→net MUST come from the **kicad-cli netlist**. Do NOT match label coordinates
to pin coordinates: KiCad symbol libraries are **Y-up** but the schematic sheet
is **Y-down**, so a naive coordinate transform silently **mirrors the entire
pinout** into something self-consistent but wrong. (This burned a whole session
once, the map looked plausible and passed spot checks until pins on opposite
ends of the symbol were compared.) The netlist is authoritative and traverses
the sheet hierarchy. Only pull *static* per-pin data (name, alternate functions)
from the symbol, that has no geometry dependence. File-parser libraries
(kiutils, kicad-skip) don't solve connectivity either. Only the netlister does.

## Procedure
1. **Run it.** Both netlists are auto-exported, so normally just:
   `hardware/tools/pcb.sh pinmap`     (or `generate_pinmap.py ROOT.kicad_sch --config pinmap.config.toml`)
   Override with `--net` / `--sheet-net` only when debugging.
   (kicad-cli may emit a harmless `/tmp/.kicad-wk-helpers` symlink warning, ignore it.)
2. **Read the SANITY WARNINGS block** at the top of the output and reconcile each
   against the schematic before trusting the map.
3. **Commit the generated file.** It is the CLEAN map, warnings go to CI only,
   never into the file, so drift tracks the real pin→net→func mapping.

## Config, `<project>/pinmap.config.toml`
Everything project-specific lives here; the script itself stays generic. It is
deliberately **NOT** part of `release.toml`: a pin map is a schematic-stage
artifact, usually settled and consumed by firmware long before layout, let alone
a manufacturing release. No config file ⇒ the pinmap commands are a clean no-op.

```toml
ref = "U1"                  # MCU designator
out = "../pinmap.toml"      # generated artifact, relative to this file
ignore = []                 # warning substrings downgraded error->notice (suppression list: keep SHORT)

[reserved]                  # peripherals the FIRMWARE owns internally
TIM5 = ""                   # "" -> no pin may use it (e.g. RTIC monotonic)
TIM4 = "ADC_SYNC"           # only that net may use it (its own I/O pin)

[groups]                    # TOML section grouping; FIRST MATCH WINS, order matters
SWDIO = "debug"             # exact net name (case-insensitive)
"UART_SWD_*" = "debug"      # fnmatch glob, glob keys MUST be quoted in TOML
```
Default grouping is the net name's first `_`-token. `[groups]` only overrides
signals whose subsystem the name alone doesn't convey.

## Sanity checks it runs (and you should eyeball)
- **Fixed-function pins**: SWDIO/SWCLK must be PA13/PA14; LSE on PC14/PC15
  (OSC32). A crystal on any other pin can't oscillate.
- **Double-drive**: a net on >1 MCU pin (excluding power). Keyed on the FULL
  sheet-qualified identity, so nets merely *sharing* a local label (three
  different `RESET`s on three sheets) stay distinct instead of looking triple-driven.
- **Peripheral double-booking**: the same active function on 2+ pins, a signal
  routes to exactly one pin.
- **Reserved peripherals**: a pin whose ACTIVE function lands on a `[reserved]`
  entry, unless that entry names the sole allowed net. Reserved channels are
  marked `!` in each pin's annotation so the engineer sees which AF options are
  off-limits.
- **`_A` analog**: warns if an `_A`-tagged pin has no ADC channel.
- **Name collision** after intent-suffix stripping (two nets that would emit the
  same firmware key).

## EXTI convention (the smart way to make the implicit explicit)
STM32 EXTI line N is shared by pin N of **every** port, so only one port's
pin-N can be an interrupt source. Make it explicit and machine-checkable by
**suffixing a net `_IRQ`** (or `_INT`/`_EXTI`) wherever an interrupt is intended.
The generator computes each pin's EXTI line (= pin index), flags any two `_IRQ`
signals on the same line, and warns on `_IRQ` labels that resolve to no pin.
Suffixes are stripped from the emitted key (`ABC_IRQ` → `abc`).
Also: EXTI 0–15 are GPIO-only; peripheral EXTI sources (PVD/RTC/COMP/wakeups)
live on separate lines ≥16, so they never contend with a pin for a line.

### GOTCHA: intent CANNOT come from the ROOT net name, hence TWO netlists
A net spanning **hierarchical sheets** gets ONE canonical name in the root
netlist, chosen from the winning label. So a `_IRQ`/`_A` suffix on the MCU sheet
can VANISH (the net shows as `RI`, not `CELLULAR_UART_RI_IRQ`); worst case the
winning name (`ABCD_1`) shares NO text with the sheet label, so root-net-name
matching is fundamentally broken. **Solution: also export the ref's sub-sheet
STANDALONE.** In isolation each net is named by its LOCAL label, so `_IRQ`/`_A`
suffixes survive, mapped to the ref's pins WITH pin numbers, KiCad's own
connectivity, no geometry. The generator uses ROOT (authoritative pin→net) +
SHEET (local labels = intent), and auto-exports both.

## CI (two separate jobs, deliberately)
Provided by the reusable workflow in pcb_release
(`.github/workflows/kicad-checks.yml`), opted into with `pinmap: true`, which
makes the pin map REQUIRED: a missing `pinmap.config.toml` fails the job rather
than passing green having checked nothing.
- **pinmap-check** (`pcb.sh pinmap-check`), validation: EXTI / double-booking /
  reserved / analog errors. Emits GitHub `::error::` annotations. `ignore` in the
  config downgrades justified ones to notices.
- **pinmap-drift** (`pcb.sh pinmap-drift`), regenerates and `git diff`s the
  committed TOML; any change fails. This is a *breaking-change signal*, kept
  SEPARATE from validation so the two can't mask each other.

Both jobs need `submodules: recursive`, the generator lives in the submodule.
The container image must be **>=** the board's KiCad version (kicad-cli cannot
open files newer than itself).

## Adapting
The TOML is a human reference (not machine-parsed downstream), so extend it
freely, add peripheral/AF blocks, notes, revision deltas, etc., matching the
target project's existing `pins_vx.toml`. Per-project tuning belongs in
`pinmap.config.toml`, not in the script.
