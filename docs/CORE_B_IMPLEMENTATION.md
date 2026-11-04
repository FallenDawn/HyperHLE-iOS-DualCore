# Core B implementation notes

## Current implementation

The repository now contains an initial iOS adapter for the pinned official touchHLE v0.3.0 source:

- `integration/touchhle-ios-entry/`: Cargo entry crate producing `libtouchhle_core.dylib`.
- `scripts/patch-touchhle-ios.py`: applies the iOS-only changes to a clean v0.3.0 checkout.
- `integration/touchhle-ios-entry/include/touchhle_core.h`: C declarations for the adapter exports.
- `.github/workflows/build-ios.yml`: builds and preserves a Core A baseline IPA, then attempts a dual-core build and packages a separate candidate.

The patch adds:
1. A `dynamic-sdl` Cargo feature so Core B uses the host application's shared SDL2 rather than statically embedding a second SDL runtime.
2. An iOS C-facing lifecycle API in the touchHLE library: request/clear exit, FPS query placeholder, and game bundle metadata inspection.
3. A cooperative exit check in the emulator execution loop. The host can request Core B to return from the run loop rather than terminating the entire process.
4. iOS bundle resource lookup, a Documents-based writable data directory, and a per-core default-options filename selected by `TOUCHHLE_DEFAULT_OPTIONS_FILE`.
5. An environment override for the Dynarmic source directory so the iOS JIT-patched source can be compiled.

## Adapter exports

The adapter exports:
- `touchhle_ios_run_game`
- `touchhle_ios_request_exit`
- `touchhle_ios_game_metadata_create` and matching accessors/free function
- `touchhle_ios_run`
- `touchhle_ios_current_fps`

The C declarations are in `integration/touchhle-ios-entry/include/touchhle_core.h`.

## JIT patch handling

Core B uses the iOS JIT patch already maintained by the pinned HyperHLE-Reborn v1.3.6 source. CI attempts to apply it to touchHLE v0.3.0's own Dynarmic submodule in a separate build directory, and the touchHLE Dynarmic wrapper is patched to accept that directory through `TOUCHHLE_DYNARMIC_DIR`.

This is intentionally a build-time compatibility check. The two projects use separately maintained Dynarmic forks; patch applicability and runtime JIT behavior must be confirmed by CI and then by the target iPad. If the patch does not apply cleanly, do not force it or substitute HyperHLE's Dynarmic without a compatibility audit.

## Current limitations / unverified items

- The adapter and patcher have been committed, but no successful dual-core CI build has yet been confirmed.
- The host's actual Core B picker/launch path still needs verification against these exports.
- The FPS query currently returns the library's atomic value; FPS reporting from the renderer has not yet been wired.
- iOS 15 runtime behavior, game input, graphics, audio, suspend/resume, and clean core switching remain unverified.
- Core A's reported iPad/iOS 15 validation remains the regression baseline and should not be altered by Core B changes.
