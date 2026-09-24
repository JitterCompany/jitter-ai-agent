# Jitter Rust style

The short version lives in `core.md` and is loaded in every session. This file has the reasoning and the examples. Baseline is the [rust-analyzer style guide](https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/style.md); this file only covers what we hit in practice.

## 1. Comments

The recurring failure is comment bloat: blocks that restate the code, narrate the steps, or record what the code used to do. They rot on the first edit and they push the actual code off the screen.

- A comment answers why, or states a contract the types cannot. Never what.
- At most 4 consecutive `//` lines. A longer explanation belongs in a decision record under `docs/decisions/`, with the code pointing at it.
- No banner or divider lines.
- No step narration.
- No change history. Git has it.
- Doc comments on public items: one summary line, then only the non-obvious parts (units, panics, timing, ownership).
- When editing existing code, trim the surrounding comments rather than adding to them. Keep comments and log statements that were already there unless the code they describe is gone.

Bad:

```rust
// ============================================================
// Modem power-up sequence
// ============================================================
// Step 1: assert the enable pin
// Step 2: wait for the modem to boot
// Step 3: open the UART
// Note: this used to use a 2s delay, but that was not enough
// for the BG95, so it is now 3s.
pub async fn power_up(&mut self) -> Result<(), Error> {
    self.enable.set_high();          // set enable pin high
    Timer::after(Duration::from_millis(3000)).await;  // wait 3s
    self.uart.open()
}
```

Good:

```rust
/// Powers the modem and waits until it accepts AT commands.
pub async fn power_up(&mut self) -> Result<(), Error> {
    self.enable.set_high();
    // BG95 needs 3s from enable to first AT response, 2s is not enough.
    Timer::after(BOOT_DELAY).await;
    self.uart.open()
}
```

## 2. Rust, not C in Rust syntax

| C-ism | Write instead |
|---|---|
| `for i in 0..v.len() { v[i] }` | `for x in &v`, or an iterator chain |
| `-1`, `0xFF`, `u32::MAX` as "not found" | `Option<T>` |
| `bool ok` plus an out-param | `Result<T, E>` and `?` |
| `fn f(out: &mut T)` | return `T` |
| `u8 state` with `#define`d values | an enum plus `match` |
| manual copy loop | `copy_from_slice`, `extend_from_slice` |
| a raw `u32` carrying millivolts | a newtype, `struct MilliVolts(u32)` |
| parsing a struct by hand in both directions | `From` / `TryFrom` |

Bad:

```rust
fn find_slot(&self, id: u8) -> i32 {
    for i in 0..self.slots.len() {
        if self.slots[i].id == id {
            return i as i32;
        }
    }
    -1
}
```

Good:

```rust
fn find_slot(&self, id: u8) -> Option<usize> {
    self.slots.iter().position(|slot| slot.id == id)
}
```

## 3. Macros

Do not introduce a macro to remove repetition. A macro hides the types, breaks rust-analyzer's navigation and makes the diff unreadable. Use a function, a trait, a const array, or a small enum with a `match`. Existing macros in a codebase stay, this rule is about adding new ones.

Also avoid `matches!()` where `if let`, let-else or `match` reads better. `matches!` is fine inside a filter closure, less so as the condition of a long `if`.

## 4. Layout and naming

- A module with submodules is `mything.rs` beside `mything/`. Never `mything/mod.rs`.
- Import types with `use`. Fully-qualified paths in signatures make them unreadable.
- Keep specifics out of generic or shared code. If a shared file has to enumerate cases per device, per board or per customer, move the list to the one module that owns it and let the shared code ask.

## 5. Interfaces

- Prefer an enum plus an optional free-text note over a single free-text field that a tool has to parse. Parsing prose is how config formats rot.
- Derive scope from a semantic property present in the data, never from a hardcoded list of names. A name list goes stale the moment someone adds a part.
- Extend a CLI by adding an optional argument that selects the new path. Do not replace the flag set wholesale, scripts depend on it.
- Before building new infrastructure, look at what established crates do. Do not propose a thin wrapper over one of them as if it were the design.
- A raw `.send().await` on a channel is a smell. Somebody has to handle the full or closed case, so wrap it in the type that owns that policy.

## 6. Firmware specifics

- `no_std`: no `Box`, no `alloc`. `heapless::Vec` and friends instead.
- Drivers and peripheral handles are not `Copy` or `Clone`. Exclusive access is the point.
- Keep primitives consumer-agnostic. Compose the sequence at the call site, not inside the primitive.
