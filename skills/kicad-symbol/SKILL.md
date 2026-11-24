---
name: kicad-symbol
description: Design or revise a KiCad schematic symbol: pin layout, alternates, drop-in replacement. Use when creating, changing or replacing a symbol.
---

# Designing a KiCad schematic symbol

A symbol is for the person who draws and reads the schematic. Design it for that use. Do not
copy the shape, orientation or pin order of the footprint: the footprint and the pin numbers
already carry the physical layout.

Baseline: the [KiCad Library Conventions](https://klc.kicad.org/), symbol section. The points
below are the ones that matter most, and our additions.

## Layout

- **Group pins by function.** A bus stays together, in a logical order (SCK, MOSI, MISO, CS).
  Never sort by pin number, unless the part is a generic connector where any pin can be anything.
- **Supplies on top, ground on the bottom.** All GND pins go on the bottom edge.
- **Inputs on the left, outputs on the right.** For a connector: the side that faces the
  rest of the circuit carries the signals.
- **Keep supply pins apart from signal pins,** with a gap of one grid step or more.
- **100 mil (2.54 mm) grid** for every pin end. Pin length 100 mil, or longer for long pin
  numbers. Symbol origin near the centre.
- **Size the body to the names,** so no pin name touches another name or a pin. Check the
  corners, where a bottom pin's name meets the last side pin's name.

## Pins

- **Correct electrical type.** `power_in` for supply inputs, `passive` for connectors and
  passives, `input`/`output`/`bidirectional` for IC signals. ERC depends on it.
- **A multiplexed pin has one name plus alternates.** Name it by its basic role (`IO_7`,
  `PA3`), and add the other functions as pin alternates (`SPI_SCK`, `I2C_SDA`). Not a slashed
  name like `CAN_TX/I2C_SCL/IO_14`. Reason: the designer picks one function per instance,
  and the schematic then shows what the pin does.
- **A few GND or supply pins: show them all.** Up to about 6, each pin is visible on its own
  position. The schematic then shows every pin number.
- **Many: stack them all on one pin.** One pin is visible, the others are hidden at the same
  spot, and the Description lists the numbers ("GND is the even pins 2 to 50"). Do not spread
  them over a few stacks: the visible numbers then look random.
- Never hide a pin that is not stacked.
- **Directions from a stated viewpoint.** If a name has TX or RX, say whose: `UART_HOST_TX`,
  or say in the Description which side the names are from.

## Revising a symbol

- **Keep the pin positions of every existing signal.** Then the new symbol drops in for the
  old one in existing schematics, without rewiring. Moving a few GND pins is acceptable. Moving
  all signal pins by one step is not.
- Run `compare_pins.py` in this folder to check it:

  ```sh
  python3 "$JITTER_ROOT/skills/kicad-symbol/compare_pins.py" OLD.kicad_sym OLD_NAME NEW.kicad_sym NEW_NAME
  ```

  It lists each pin number whose position changed, and pins that were added or removed.

## Fields

`Reference`, `Value` (visible), `Footprint`, `Datasheet`, `Description`, `MPN`,
`ki_keywords` and `ki_fp_filters`. The Datasheet links the spec or datasheet. The Description
says what the symbol is in one or two sentences. No customer or project names (C1).

## Check

1. Export the symbol: `kicad-cli sym export svg -s NAME -o OUT_DIR LIB.kicad_sym`, render it
   and look at it. Check overlaps, the grid and the grouping.
2. For a revision, run `compare_pins.py` against the old symbol.
3. Place it in a test schematic, select an alternate, and run ERC when you can.
