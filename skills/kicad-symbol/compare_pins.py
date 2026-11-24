#!/usr/bin/env python3
"""Compare the pin positions of two KiCad symbols, to check that a new one drops in.

    python3 compare_pins.py OLD.kicad_sym OLD_NAME NEW.kicad_sym NEW_NAME

Pins are matched by pin number. Prints every pin that moved, was added or was removed.
Exits 1 when a signal pin moved. A moved GND pin is listed but allowed. Stock python3.
"""

import re
import sys

PIN = re.compile(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\).*?\(name "([^"]*)".*?'
                 r'\(number "([^"]*)"', re.S)


def symbol_pins(path, name):
    text = open(path, encoding="utf-8").read()
    start = text.find('(symbol "{}"'.format(name))
    if start < 0:
        sys.exit("{}: no symbol {}".format(path, name))
    depth, end = 0, start
    for end in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[end], 0)
        if depth == 0:
            break
    return {m.group(4): ((float(m.group(1)), float(m.group(2))), m.group(3))
            for m in PIN.finditer(text[start:end])}


def main(old_path, old_name, new_path, new_name):
    old, new = symbol_pins(old_path, old_name), symbol_pins(new_path, new_name)
    moved = 0
    for number in sorted(old.keys() | new.keys(), key=lambda n: (len(n), n)):
        if number not in new:
            print("removed", number, old[number][1])
        elif number not in old:
            print("added  ", number, new[number][1])
        elif old[number][0] != new[number][0]:
            moved += new[number][1] != "GND"
            print("moved  ", number, old[number][1], old[number][0], "->", new[number][1], new[number][0])
    print("{} pins in old, {} in new, {} signal pins moved".format(len(old), len(new), moved))
    return 1 if moved else 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
