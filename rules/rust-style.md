# Jitter Rust style

Home of the `R` rules. `core.md` carries the short form of R1 to R11, the rest live here only.

- **R10** Baseline: the [rust-analyzer style guide](https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/style.md). This file covers what we hit in practice on top of it.

## 1. Comments

The recurring failure is comment bloat: blocks that restate the code, narrate the steps, or record what the code used to do. They rot on the first edit and push the actual code off the screen.

- **R2** A comment answers why, or states a contract the types cannot. Never what. No banners, no step narration, no change history, git has that.
- **R3** At most 4 consecutive `//` lines in what you write. When editing existing code, do not grow the comments around it. Comments you did not write stay (R5), and the edit hook only judges the lines your edit added.
- **R4** A longer explanation belongs in a decision record under `docs/decisions/`, with the code pointing at it.
- **R5** Keep the comments and the `debug!` / `info!` / `warn!` / `error!` / `trace!` statements that were already there, unless the code they describe is gone.
- **R17** Comments are `//` and `///`. No `/* */` blocks: they are where banner headers and step narration come back, and rustfmt leaves them alone. `comment_lint.py` flags them.
- **R12** Doc comments on public items: one summary line, then only the non-obvious parts (units, panics, timing, ownership).

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

- **R1** Write Rust, not C in Rust syntax:

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

- **R6** Do not add a macro to remove repetition. It hides the types, breaks rust-analyzer's navigation and makes the diff unreadable. Use a function, a trait, a const array, or a small enum with a `match`. Macros already in a codebase stay, this is about adding new ones. Also avoid `matches!()` where `if let`, let-else or `match` reads better. Inside a filter closure it is fine.

## 4. Layout and naming

- **R7** A module with submodules is `mything.rs` beside `mything/`. Never `mything/mod.rs`. Import types with `use`, fully-qualified paths in signatures make them unreadable.
- **R13** Keep specifics out of generic or shared code. If a shared file enumerates cases per device, per board or per customer, move the list to the module that owns it and let the shared code ask.

## 5. Interfaces

- **R8** Prefer an enum plus an optional free-text note over a single free-text field a tool has to parse. Parsing prose is how config formats rot. Derive scope from a semantic property in the data, never from a hardcoded list of names, which goes stale the moment someone adds a part.
- **R9** Extend a CLI by adding an optional argument that selects the new path. Do not replace the flag set, scripts depend on it. Before building new infrastructure, look at what established crates do, and do not present a thin wrapper over one as the design.
- **R14** A raw `.send().await` on a channel is a smell. Someone has to handle the full or closed case, so wrap it in the type that owns that policy.

## 6. Firmware

- **R11** `no_std`: no `Box`, no `alloc`. `heapless::Vec` and friends instead.
- **R15** Drivers and peripheral handles are not `Copy` or `Clone`. Exclusive access is the point.
- **R16** Keep primitives consumer-agnostic. Compose the sequence at the call site, not inside the primitive.

## Not in core.md

R12 to R17 are not in the session digest. They live here because they are background or situational. Load this file when writing Rust, the `rust-style` skill does that.
