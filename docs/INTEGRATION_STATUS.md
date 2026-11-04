# Integration status

Last checked: 2026-11-04

## User-confirmed device validation

- [x] Core A (HyperHLE-Reborn v1.3.6) passes on one physical iPad running iOS 15. Exact iPad model, game list, and detailed test checklist are not yet recorded.

## Verified from upstream source

- [x] HyperHLE-Reborn tag `v1.3.6` exists.
- [x] Its `platform/ios/README.md` documents an Applesauce-derived iOS host, a Rust dynamic core, shared SDL2, and iOS-specific SDL/Dynarmic patches.
- [x] That README describes a second-core mechanism via `TOUCHHLE_CORE_REPO`, using a touchHLE checkout that has an iOS entry crate (the example is a fork branch, not the official v0.3.0 tag).
- [x] Official touchHLE tag `v0.3.0` exists.
- [x] Its Cargo manifest declares `cdylib` and `rlib` library crate types.
- [x] Official touchHLE v0.3.0 README lists desktop/Android support; iOS is not listed as officially supported.

## Not yet implemented or verified

- [x] Core A baseline build completed successfully (user-confirmed).
- [x] Core A physical-device launch/runtime validation on one iPad running iOS 15 (user-confirmed).
- [ ] Confirm exact Xcode/macOS runner compatibility and all external build dependencies.
- [ ] Implement a dedicated iOS entry crate/adapter for official touchHLE v0.3.0. See [CORE_B_PORT_AUDIT.md](CORE_B_PORT_AUDIT.md) for the audited integration boundary and reference port.
- [ ] Prove touchHLE can coexist with the host's SDL2/UIKit ownership model without duplicate SDL runtime/UIApplicationDelegate.
- [ ] Implement host-side core picker and per-game core selection.
- [ ] Validate file import, game launch, touch/controller input, orientation, audio, graphics, app lifecycle and persistence for both cores.
- [ ] Validate JIT entitlements and behavior on representative iOS 15 TrollStore devices (including A11 and A12+ distinctions).
- [ ] Produce and test a dual-core IPA on physical hardware.

## Release gate

A dual-core release must not be labelled complete until the Core B adapter compiles, the host loads and unloads both cores cleanly, and a documented test matrix passes. A successful Core A baseline IPA is not evidence of dual-core support.
