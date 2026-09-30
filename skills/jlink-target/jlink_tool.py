#!/usr/bin/env python3
"""J-Link helper for Cortex-M targets without NRST on the debug header.

Subcommands:
  attach    loop until SWD attach works, print a status line every ~10 s (VTref diagnosis)
  flash     attach loop, halt, (optionally) keep debug alive in low-power modes, load, reset
  reset     software reset through AIRCR (works without NRST)
  rtt-dump  print the RTT up-buffer 0 ring from target RAM (oldest first)
  boot-log  reset, stay off SWD for N s, then rtt-dump

Every status line is flushed on its own, so the output can be streamed to a user
(Claude Code: run it under the Monitor tool).
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

AIRCR_RESET = "w4 0xE000ED0C 0x05FA0004"
CPUID = 0xE000ED00
# STM32 DBGMCU_CR: DBG_SLEEP | DBG_STOP | DBG_STANDBY (bits 0..2, stm32ral dbgmcu_v2)
STM32_DBGMCU_CR = "w4 0xE0042004 0x7"


STATUS_FILE = None


def say(msg):
    print(msg, flush=True)
    if STATUS_FILE:
        with open(STATUS_FILE, "a") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def jlink(device, speed, cmds):
    # ExitOnError: a failed connect must end the session fast, the caller retries
    script = [f"device {device}", "SelectInterface swd", f"speed {speed}", "ExitOnError 1"]
    script += cmds + ["q"]
    with tempfile.NamedTemporaryFile("w", suffix=".jlink", delete=False) as f:
        f.write("\n".join(script) + "\n")
        path = f.name
    try:
        return subprocess.run(
            ["JLinkExe", "-NoGui", "1", "-CommanderScript", path],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
    finally:
        os.unlink(path)


def vtref(out):
    m = re.findall(r"VTref=([0-9.]+)V", out)
    return float(m[-1]) if m else None


def vtref_hint(v):
    if v is None:
        return "no VTref reading (probe not found?)"
    if v < 0.5:
        return "no target power, or VTref pin not connected"
    if v < 2.7:
        return "low: connector not seated, or target supply is sagging"
    return "power ok"


def last_error(out):
    v = vtref(out)
    if v is not None and v >= 2.7 and re.search(r"Could not connect|Failed to power up DAP|Could not read CPUID|Attach to CPU failed", out):
        return "SWD answers but the core does not: target asleep with debug-in-sleep off (power-cycle, or wait for a wakeup)"
    if re.search(r"Could not find|No J-Link|not connected to the host", out, re.I):
        return "J-Link probe not found on USB"
    errs = [l.strip() for l in out.splitlines() if re.search(r"Could not|[Ff]ailed|Error occurred", l)]
    return errs[-1][:80] if errs else ""


def attach(args, then=None, success=None):
    """Retry until `then` commands ran after a successful connect.

    `success(out)` decides whether the run counts; default: CPUID was read.
    """
    cmds = ["connect"] + (then or [f"mem32 {CPUID:#x} 1"])
    success = success or (lambda out: re.search(rf"^{CPUID:08X} = ", out, re.M))
    start = time.monotonic()
    last_report = start
    interval = args.status_every
    last_diag = None
    same = 0
    tries = 0
    out = ""
    while time.monotonic() - start < args.timeout:
        out = jlink(args.device, args.speed, cmds)
        tries += 1
        v = vtref(out)
        if success(out):
            say(f"ATTACHED after ~{tries} tries ({time.monotonic() - start:.0f} s), VTref={v} V")
            return out
        diag = (vtref_hint(v), last_error(out))
        if diag != last_diag or time.monotonic() - last_report >= interval:
            # Unchanged status: report 4 times at the base rate, then back off (max 5 min)
            same = same + 1 if diag == last_diag else 0
            interval = args.status_every if same < 4 else min(interval * 2, 300)
            last_diag = diag
            last_report = time.monotonic()
            say(f"t={time.monotonic() - start:.0f}s tries~{tries} VTref={v} V ({diag[0]}) last: {diag[1]}")
    v = vtref(out)
    say(f"GAVE UP after ~{tries} tries, VTref={v} V ({vtref_hint(v)}), last: {last_error(out)}")
    sys.exit(1)


def cmd_attach(args):
    attach(args)


def cmd_flash(args):
    image = args.image
    if "@" in image:
        path, addr = image.split("@", 1)
        load = f"loadbin {os.path.abspath(path)}, {addr}"
    else:
        load = f"loadfile {os.path.abspath(image)}"
    then = ["h"] + ([STM32_DBGMCU_CR] if args.keep_debug else []) + [load, AIRCR_RESET]
    out = attach(args, then, success=lambda o: re.search(r"Flash download: Total|Contents already match", o))
    for line in out.splitlines():
        if "Flash download: Total" in line or "already match" in line:
            say(line.strip())


def cmd_reset(args):
    keep = [STM32_DBGMCU_CR] if args.keep_debug else []
    attach(args, keep + [AIRCR_RESET], success=lambda o: "Script processing completed" in o and "Could not connect" not in o)


def cmd_rtt_dump(args):
    # One session only: a sleeping target may give a single attach window, so grab all RAM
    # at once and decode the RTT control block offline.
    cb = int(args.cb, 0)
    ram_base, ram_size = (int(x, 0) for x in args.ram.split(":"))
    halt = ["h"] if args.halt else []
    resume = ["g"] if args.halt else []
    with tempfile.TemporaryDirectory() as d:
        dump = os.path.join(d, "ram.bin")
        attach(
            args,
            halt + [f"savebin {dump}, {ram_base:#x}, {ram_size:#x}"] + resume,
            success=lambda o: os.path.exists(dump) and os.path.getsize(dump) == ram_size,
        )
        ram = open(dump, "rb").read()
    off = cb - ram_base
    if ram[off : off + 10] != b"SEGGER RTT":
        sys.exit(f"no RTT control block at {cb:#x}")
    # first up-buffer descriptor: name, buffer, size, WrOff, RdOff, flags
    _, buf, size, wr, rd, _ = (int.from_bytes(ram[off + 0x18 + 4 * i : off + 0x1C + 4 * i], "little") for i in range(6))
    data = ram[buf - ram_base : buf - ram_base + size]
    print(f"# buf={buf:#x} size={size} wr={wr} rd={rd}", file=sys.stderr)
    sys.stdout.write((data[wr:] + data[:wr]).replace(b"\0", b"").decode("utf-8", "replace"))


def cmd_boot_log(args):
    cmd_reset(args)
    say(f"reset done, staying off SWD for {args.wait} s")
    time.sleep(args.wait)
    cmd_rtt_dump(args)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--device", default=os.environ.get("JLINK_DEVICE"), help="J-Link device name (or $JLINK_DEVICE)")
    p.add_argument("--speed", default="1000", help="SWD kHz")
    p.add_argument("--timeout", type=float, default=600, help="give up after this many seconds")
    p.add_argument("--keep-debug", action="store_true", help="STM32: set DBGMCU_CR on flash/reset so SWD keeps working in sleep/stop")
    p.add_argument("--status-every", type=float, default=10, help="seconds between status lines")
    p.add_argument(
        "--status-file",
        default=os.environ.get("JLINK_STATUS_FILE", "/tmp/jlink-target-status.log"),
        help="also append timestamped status lines here, for `tail -f` by a human",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("attach").set_defaults(fn=cmd_attach)
    f = sub.add_parser("flash")
    f.add_argument("image", help="file.elf, or file.bin@0xADDR")
    f.set_defaults(fn=cmd_flash)
    sub.add_parser("reset").set_defaults(fn=cmd_reset)
    for name, fn in (("rtt-dump", cmd_rtt_dump), ("boot-log", cmd_boot_log)):
        s = sub.add_parser(name)
        s.add_argument("--cb", required=True, help="RTT control block address, e.g. 0x2009FF00")
        s.add_argument("--halt", action="store_true", help="halt while reading (adds a stall)")
        s.add_argument("--ram", default="0x20000000:0xA0000", help="RAM base:size to read (default STM32L4R 640K)")
        if name == "boot-log":
            s.add_argument("--wait", type=float, default=40, help="seconds off SWD after reset")
        s.set_defaults(fn=fn)
    args = p.parse_args()
    global STATUS_FILE
    STATUS_FILE = args.status_file or None
    if not args.device:
        p.error("set --device or $JLINK_DEVICE (e.g. STM32L4R7ZI)")
    args.fn(args)


if __name__ == "__main__":
    main()
