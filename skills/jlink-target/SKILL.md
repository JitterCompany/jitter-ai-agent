---
name: jlink-target
description: Attach to, flash, reset and read RTT logs from a Cortex-M board over a SEGGER J-Link, on Jitter boards that have no NRST on the debug header. Streams attach status to the user, diagnoses VTref, and knows the debugger side effects (a connect halts the core for ms). Use when asked to flash a board, get a boot log, check why a J-Link won't connect, or when a timing bug only shows up while a debugger is attached.
---

# J-Link on Jitter boards

Jitter debug headers carry SWDIO/SWCLK only. **NRST is never wired**, so "connect under reset" always fails and J-Link's fallbacks just waste seconds. Everything below works around that.

The tool is `jlink_tool.py` next to this file (Python stdlib, calls `JLinkExe`). Set `JLINK_DEVICE` (e.g. `STM32L4R7ZI`) or pass `--device`.

| command | does |
|---|---|
| `attach` | retries until SWD attach works, a status line every ~10 s with a VTref diagnosis |
| `flash file.elf` / `flash file.bin@0x08000000` | attach, halt, load, reset via AIRCR |
| `reset` | software reset via AIRCR (no NRST needed) |
| `rtt-dump --cb 0x2009FF00` | copies all RAM in one session and prints the RTT log ring, oldest first |
| `boot-log --cb ... --wait 40` | reset, stay off SWD for N s, then `rtt-dump` |

Global options: `--keep-debug` (STM32: set `DBGMCU_CR` so SWD works in sleep/stop), `--timeout`, `--speed`, `--status-every`.

## Keep the user informed

Attaching to a sleeping board can take minutes. Run `attach`/`flash` under the **Monitor** tool so each status line reaches the user directly, e.g. `t=24s tries~6 VTref=3.35 V (ok) last: Could not connect`. Ask them to power-cycle when the log says the target is asleep for good.

VTref tells you what to ask for:

| VTref | meaning |
|---|---|
| ~0 V | no target power, or the cable is off |
| 0.5 to 2.7 V | connector not seated, or supply sagging |
| ~3.3 V but no attach | target is asleep with debug-in-sleep off, keep retrying or power-cycle |

## Side effects to know before you trust a measurement

- **Every connect halts the core.** With the ST device profile, SEGGER's `InitTarget` script stops the CPU twice, ~0.6 ms and ~7 ms (measured: DWT CYCCNT stops, the timer does not). A 1 kHz sensor loses 7 samples, a 10 ms I2C timeout can fire. Reconnecting every second, as a naive polling script does, injects that fault over and over.
- A failure that is **exactly the same size every run** (e.g. always 28 COUNT steps) points at the tooling first. Re-test with the probe untouched: `boot-log` stays off SWD during boot.
- For live logs keep **one** session open (RTT Viewer, `JLinkGDBServer`), do not reconnect per read.
- `JLinkRTTLogger` searches for the RTT control block only once, at connect. Started right after a reset it finds the bootloader, not the app, and prints "not found". Start it after the app runs, or use `rtt-dump`.
- The RTT log buffer is small (often 2 KB) and a full buffer drops new lines. Read it soon after boot, or make it bigger in a debug build.

## Reachability and lockout

- A board that sleeps with `DBGMCU_CR` debug bits clear only answers in short awake windows. A power-on reset clears those bits. `--keep-debug` sets them, but a later session may put the old value back, so it is not guaranteed to stick.
- **Do not flash a standalone image with sleep enabled for experiments.** Nothing sets the debug bits, and you get "Failed to power up DAP" from then on. Recover by running `flash` in a loop while the user power-cycles the board, so the attach lands in the boot window.
- For debugging, build with sleep disabled (Frogwatch: feature `disable-sleep`) if you need the board reachable at all times.

## Deliberate halts as fault injection

Since a halt is the known side effect, you can use it on purpose: halt for N ms (`h`, wait, `g` in one JLinkExe session) while the firmware does I2C, SPI or sensor reads. Any timeout that trips at a few ms of stall is too tight for a real system with interrupt load.
