# Architecture proposal

## Guiding rule

Do not rewrite either emulator core to fit a speculative common interface. Keep each upstream implementation intact and adapt at the host boundary. Core A remains the default until Core B passes build, launch, input, graphics, audio, lifecycle, persistence, and game-compatibility tests.

## Layers

1. **iOS host** — the Applesauce-derived host currently shipped in HyperHLE-Reborn v1.3.6. Preserve its Swift/UIKit/SDL2 ownership model.
2. **Core selection** — a host-owned selection model storing a stable core identifier per game. The picker must not instantiate both cores simultaneously.
3. **Core adapters** — one adapter per core. Each translates host lifecycle, paths, input, logging, and presentation requirements into the native core API.
4. **Shared app services** — game import/library metadata and document storage may be shared only where the existing host already owns those responsibilities. Do not assume save formats or per-game settings are interchangeable.
5. **JIT policy** — core-specific executable-memory requirements and entitlements are checked independently. A common UI toggle does not imply a common JIT implementation.

## Proposed lifecycle boundary

`integration/CoreABI.h` is a discussion contract for the adapter boundary, not an upstream ABI and not a claim that either upstream currently exports these symbols.

The first adapter implementation should expose capability discovery and initialization; load/unload of a legally obtained decrypted app bundle; start, pause, resume, stop and shutdown; host callbacks for logging, input, display invalidation and storage paths; and explicit error reporting and version/capability metadata.

The adapter must document thread affinity and ownership for every callback. SDL's process entry point and UIApplicationDelegate must remain owned by the host; a second SDL instance must not be loaded into the same process.

## Core A

Use HyperHLE-Reborn v1.3.6's existing `platform/ios` implementation as the baseline. Its documentation describes a Rust dynamic core loaded by the iOS host, a shared SDL2 build, and iOS-specific SDL/Dynarmic patches. Avoid copying or modifying those internals until a reproducible baseline build exists.

## Core B

Official touchHLE v0.3.0 is a Rust workspace whose library crate types include `cdylib` and `rlib`, but the official tag's platform support documentation does not identify iOS as a supported build target. A dedicated iOS entry crate, SDL ownership strategy, linker configuration, framework dependencies, and runtime loading contract still need implementation and validation.

Do not point `TOUCHHLE_CORE_REPO` at an unrelated fork or branch and label it official v0.3.0. Any fork-specific iOS work must be recorded as a separate patch/fork with its own pinned commit and license review.

## Build and release policy

- CI baseline job builds only the known upstream HyperHLE iOS host.
- Dual-core packaging remains disabled until Core B adapter tests pass.
- Publish separate unsigned and TrollStore packages only when signing/entitlement packaging has been validated on the selected runner and device matrix.
