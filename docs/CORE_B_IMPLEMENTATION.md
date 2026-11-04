# Core B implementation notes

## Selected secondary core

The project now targets exactly two selectable cores:

- **Core A:** HyperHLE-Reborn v1.3.6 (libhyperhle_core.dylib).
- **Core B:** official touchHLE v0.3.0 (libtouchhle_core.dylib).

The old touchHLE 0.2.3 picker label is replaced at build time with **touchHLE v0.3.0**. The app's core picker discovers installed cores by checking the corresponding dylib in the app's Frameworks directory. The dual-core IPA verification step requires both expected dylibs to be present.

## Core B implementation

- integration/touchhle-ios-entry/: Cargo entry crate producing libtouchhle_core.dylib.
- scripts/patch-touchhle-ios.py: applies the iOS-only changes to a clean official v0.3.0 checkout.
- integration/touchhle-ios-entry/include/touchhle_core.h: C declarations for adapter exports.
- .github/workflows/build-ios.yml: builds Core A, then official Core B, verifies the dylib and packages a dual-core IPA.

The patch adds:
1. A dynamic-sdl Cargo feature so Core B uses the host application's shared SDL2.
2. An iOS C-facing lifecycle API, metadata API and cooperative exit request.
3. A cooperative exit check in the emulator execution loop.
4. iOS bundle resource lookup, a Documents-based writable data directory and a per-core default-options filename.
5. A Dynarmic source-directory override so the iOS JIT-patched source can be compiled.

## CI verification

Run #33 successfully completed the Core B build, verified the adapter exports, shared SDL2 linkage and iOS 15 minimum deployment target, and packaged the dual-core TrollStore IPA. The next CI run also verifies the two expected core dylibs are embedded and applies the v0.3.0 picker label.

The build warning touchHLE_version@0.2.3 emitted by the HyperHLE-Reborn build refers to the upstream HyperHLE source package metadata; it is not a third selectable core and does not mean that the Core B dylib was built from touchHLE 0.2.3. Core B's source checkout is pinned to official tag v0.3.0.

## Adapter exports

- touchhle_ios_run_game
- touchhle_ios_request_exit
- touchhle_ios_game_metadata_create and matching accessors/free function
- touchhle_ios_run
- touchhle_ios_current_fps

The C declarations are in integration/touchhle-ios-entry/include/touchhle_core.h.

## Remaining device validation

CI build success is not a substitute for testing on the target iPad. The following remain unverified:

- Core B JIT availability and actual game launch on iOS 15.
- Game touch/controller input, graphics and audio.
- Orientation, suspend/resume and clean return to the library.
- Switching between Core A and Core B, including repeated launches.
- FPS reporting from the renderer; the current query returns the adapter's atomic value.
- Regression testing of Core A after the final dual-core packaging changes.

Do not call the dual-core build a fully working release until the Core B device test matrix passes.
