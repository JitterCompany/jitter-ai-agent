---
name: jlink-target
description: Flash, reset, attach and read RTT logs on a Cortex-M board over a SEGGER J-Link, for boards without NRST. Use for flashing, boot logs, a J-Link that will not connect, or debugger-only timing bugs.
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

Global options: `--keep-debug` (STM32: set `DBGMCU_CR` so SWD works in sleep/stop), `--timeout`, `--speed`, `--status-every`, `--status-file`.

## Keep the user informed

Attaching to a sleeping board can take minutes, so never wait silently.

- Run `attach`/`flash`/`boot-log` under the **Monitor** tool and post a one-line status in the chat per event. If the status says the user must act, ask for it explicitly ("power-cycle the board"), then keep retrying.
- The tool reports immediately when the diagnosis changes. Unchanged lines come at `--status-every`, and after 4 in a row the interval doubles (max 5 min), so a long wait does not flood the chat.
- Every line also goes, timestamped, to `--status-file` (default `/tmp/jlink-target-status.log`, or `$JLINK_STATUS_FILE`). A human can `tail -f` it without asking the agent.

VTref tells you what to ask for:

| VTref | meaning |
|---|---|
| ~0 V | no target power, or the cable is off |
| 0.5 to 2.7 V | connector not seated, or supply sagging |
| ~3.3 V but no attach | target asleep with debug-in-sleep off: power-cycle, the attach lands in the boot window |

## Side effects to know before you trust a measurement

- **Every connect halts the core.** With the ST device profile, SEGGER's `InitTarget` script stops the CPU twice, ~0.6 ms and ~7 ms (measured: DWT CYCCNT stops, the timer does not). A 1 kHz sensor loses 7 samples, a 10 ms I2C timeout can fire. Reconnecting every second, as a naive polling script does, injects that fault over and over.
- A failure that is **exactly the same size every run** (e.g. always 28 COUNT steps) points at the tooling first. Re-test with the probe untouched: `boot-log` stays off SWD during boot.
- For live logs keep **one** session open (RTT Viewer, `JLinkGDBServer`), do not reconnect per read.
- `JLinkRTTLogger` searches for the RTT control block only once, at connect. Started right after a reset it finds the bootloader, not the app, and prints "not found". Start it after the app runs, or use `rtt-dump`.
- The RTT log buffer is small (often 2 KB) and a full buffer drops new lines. Read it soon after boot, or make it bigger in a debug build.

## Reachability and lockout

- A board that sleeps with `DBGMCU_CR` debug bits clear only answers in short awake windows. A power-on reset clears those bits. `--keep-debug` sets them, but a later session may put the old value back, so it is not guaranteed to stick.
- **Do not flash a standalone image with sleep enabled for experiments.** Nothing sets the debug bits, and you get "Failed to power up DAP" from then on. Recover by running `flash` in a loop while the user power-cycles the board, so the attach lands in the boot window.
- For debugging, build with sleep disabled (usually a cargo feature such as `disable-sleep`) if you need the board reachable at all times.

## Deliberate halts as fault injection

Since a halt is the known side effect, you can use it on purpose: halt for N ms (`h`, wait, `g` in one JLinkExe session) while the firmware does I2C, SPI or sensor reads. Any timeout that trips at a few ms of stall is too tight for a real system with interrupt load.
