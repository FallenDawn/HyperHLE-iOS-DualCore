# HyperHLE-iOS-DualCore

Dual-core iOS host integration project targeting iOS 15+ and TrollStore, developed on Windows and built on GitHub Actions macOS runners.

## Current integration strategy

- **Core A (default):** HyperHLE-Reborn **v1.3.6**.
- **Core B (secondary):** official touchHLE **v0.3.0** only. The legacy touchHLE 0.2.3 option is not part of the intended dual-core build.
- **Host:** HyperHLE-Reborn's iOS host (Swift/UIKit/SDL2), with the secondary core identified in the picker as **touchHLE v0.3.0**.
- **Build:** Windows for source editing and Git operations; GitHub Actions macOS runner for Xcode/Rust/iOS builds.

The CI run [#33](https://github.com/FallenDawn/HyperHLE-iOS-DualCore/actions/runs/41899614590) successfully built Core A and the official touchHLE v0.3.0 adapter, checked Core B's exported symbols, shared SDL2 linkage and iOS 15 deployment target, and packaged a dual-core TrollStore IPA. A subsequent build applies the explicit v0.3.0 picker label and verifies that both expected dylibs are embedded in the IPA.

**Important:** CI build and packaging success do not prove that Core B can launch games on the target iPad. Core B still requires physical-device testing for JIT, game launch, input, graphics, audio, lifecycle and core switching. Core A's iPad/iOS 15 test remains the regression baseline.

## Pinned upstreams

| Component | Revision | Role |
|---|---|---|
| [HyperHLE-Reborn](https://github.com/KlugKlugTG/HyperHLE-Reborn) | v1.3.6 | Existing iOS host and default core |
| [touchHLE](https://github.com/touchHLE/touchHLE) | v0.3.0 | Only secondary core |

The workflow checks out these exact tags, preserves a Core A baseline artifact, then builds and packages the dual-core candidate. The baseline IPA is retained only as a regression fallback; it is not an additional selectable core in the dual-core candidate.

## Build on GitHub

1. Open **Actions**.
2. Run **iOS build (HyperHLE + touchHLE dual-core)**, or push a change to main.
3. Download the HyperHLE-iOS-v1.3.6-dualcore-candidate artifact.
4. Install the HyperHLE-iOS-trollstore.ipa with TrollStore and enable JIT as required by the device.

The CI verifies that the dual-core IPA contains libhyperhle_core.dylib and libtouchhle_core.dylib. Do not treat it as a validated release until Core B passes physical-device tests.

## Project layout

- .github/workflows/build-ios.yml — macOS CI pipeline
- config/upstreams.env — immutable upstream tag pins
- docs/ARCHITECTURE.md — target design and boundaries
- docs/INTEGRATION_STATUS.md — verified facts and remaining work
- integration/touchhle-ios-entry/ — Core B Rust C-ABI adapter
- integration/touchhle-ios-entry/include/touchhle_core.h — Core B exported C ABI
- scripts/patch-touchhle-ios.py — applies the iOS patch to official v0.3.0 at build time
- scripts/patch-hyperhle-core-label.py — labels the picker entry as touchHLE v0.3.0
- scripts/verify-dualcore-ipa.sh — checks that both intended core dylibs are packaged
- docs/CORE_B_IMPLEMENTATION.md — adapter, JIT and validation notes

## Important platform/JIT constraints

The upstream v1.3.6 iOS documentation describes TrollStore/JIT paths for specific iOS versions and device generations. Do not assume every iOS 15+ device has the same JIT behavior. In particular, its permanent-JIT build is documented as unsuitable for A12 and newer devices. Use the standard TrollStore IPA unless the device-specific documentation explicitly supports another mode.

## Legal

No commercial games, decrypted IPAs, Apple firmware, signing certificates, or provisioning profiles are included. Use only software you are legally entitled to use. Review and preserve the licenses of both upstream projects and all bundled dependencies before redistribution.
