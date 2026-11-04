# Core B iOS port audit

Audit date: 2026-11-04

## Device validation baseline

The project owner reports that Core A (HyperHLE-Reborn v1.3.6) has passed a physical-device test on one iPad running iOS 15. This is recorded as a user-confirmed result; the exact iPad model, tested game versions, and test checklist have not yet been recorded.

Core A is therefore the regression baseline. Core B work must not change Core A's known-good runtime path.

## What the existing HyperHLE iOS host already provides

The v1.3.6 platform/ios/scripts/build-host.sh builds the host's own core first. If TOUCHHLE_CORE_REPO is non-empty, it invokes build-rust.sh a second time for that checkout.

The v1.3.6 build-rust.sh expects the second checkout to provide:

- platform/ios/rust-entry/Cargo.toml
- an iOS Rust target buildable as aarch64-apple-ios
- a core dylib name derived from that entry crate's [lib].name
- a dynamic-sdl Cargo feature, so the core links to the host's shared SDL2 rather than loading a private SDL runtime

The host's documented design loads the core dylibs dynamically and provides a core picker. The SDL/UIKit process entry point remains owned by the host. This is the correct integration boundary; do not add a second SDL runtime or UIApplicationDelegate.

## Official touchHLE v0.3.0 audit

Pinned source: https://github.com/touchHLE/touchHLE/tree/v0.3.0

Verified from the official tag:

- The root Cargo package is version 0.3.0.
- The library crate types are cdylib and rlib.
- The default feature set includes static/bundled SDL2.
- The root package does not contain the iOS entry crate path expected by HyperHLE's iOS build script.
- The official README lists x64 Windows, x64 macOS and AArch64 Android as officially supported; iOS is not listed.
- The public Rust entry point is the command-line-style touchHLE::main(args). A cdylib artifact alone does not provide the iOS host's expected adapter ABI or lifecycle controls.

Consequently, simply setting TOUCHHLE_CORE_REPO to an unmodified v0.3.0 checkout will fail the iOS entry-crate check. The crate-type declaration is not evidence of iOS readiness.

## Existing iOS port reference — useful, but not the target revision

HyperHLE v1.3.6 points to the ios-core-dylib branch in the repository now named Applesauce:
https://github.com/johnny901901901/Applesauce/tree/ios-core-dylib

That branch is a valuable implementation reference. Its Cargo manifest has:

- a workspace member at platform/ios/rust-entry
- a dynamic-sdl feature that avoids a private static SDL2 copy
- an iOS entry crate named touchhle_core

Its iOS entry crate exports C functions for running the core, requesting exit, querying FPS, inspecting game metadata, and launching a selected game with options.

Important revision warning: the audited branch's root Cargo package reports version 0.2.3, not 0.3.0. It must not be silently substituted for the project's pinned official v0.3.0 target. The associated Applesauce iOS README also says its own current device test was on iOS 27 beta and that iOS 15/16 were untested by that maintainer. The project's own iPad/iOS 15 test remains the relevant device gate.

## Porting plan for official v0.3.0

1. Create a maintained Core B source tree or patch series based on the exact official v0.3.0 tag. Keep the upstream source revision and every iOS-specific patch separately identifiable.
2. Port the existing iOS entry crate concept to v0.3.0: C ABI exports for metadata inspection and game launch; a cooperative exit request and clean return to the host; FPS reporting only if the host UI consumes it; explicit error/log forwarding.
3. Port only the minimum iOS-specific core changes needed for host integration. Preserve upstream desktop/Android behavior.
4. Enable the host's shared SDL2 feature and verify that the core resolves SDL symbols against the app's one shared SDL2 image. Do not statically bundle another SDL2.
5. Build Core B for aarch64-apple-ios with deployment target 15.0 and the same toolchain/patch assumptions as the host.
6. Verify exported symbols, install names, minimum OS load commands, linked frameworks and absence of a second SDL runtime in CI.
7. Package a dual-core TrollStore IPA while retaining the existing Core A dylib unchanged.
8. On the one iPad/iOS 15 device, test Core B launch/exit, touch, orientation, graphics, audio, app background/foreground, game import and persistence. Then run the Core A regression checklist again.

## Current decision

Use the existing ios-core-dylib port as a code reference, not as the pinned Core B source. Keep official touchHLE v0.3.0 as the target and implement a separately auditable iOS adapter/patch set. Do not claim dual-core support until the physical-device tests pass.
