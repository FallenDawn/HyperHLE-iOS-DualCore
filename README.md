# HyperHLE-iOS-DualCore

Dual-core iOS host integration project targeting iOS 15+ and TrollStore, developed on Windows and built on GitHub Actions macOS runners.

## Current integration strategy

- **Core A (default):** HyperHLE-Reborn **v1.3.6**, using its existing Applesauce-derived iOS host and build pipeline.
- **Core B (in progress):** official touchHLE **v0.3.0**, integrated through a separately maintained iOS adapter and iOS JIT patch path. Adapter source and build-time patch scripts are committed; dual-core compilation and device runtime are not yet verified.
- **Host:** retain the upstream iOS host (Swift/UIKit/SDL2) wherever possible; add a core-selection layer only after verifying the host's actual lifecycle and ABI.
- **Build:** Windows for source editing and Git operations; GitHub Actions macOS runner for Xcode/Rust/iOS builds.

Core A has been reported as passing a physical-device test on one iPad running iOS 15. Core B adapter source and the CI dual-core build path are now present, but they remain unverified until CI succeeds and Core B runs on that iPad. See [the source audit](docs/CORE_B_PORT_AUDIT.md) and [implementation notes](docs/CORE_B_IMPLEMENTATION.md). No working dual-core IPA is claimed yet.

## Pinned upstreams

| Component | Revision | Role |
|---|---|---|
| [HyperHLE-Reborn](https://github.com/KlugKlugTG/HyperHLE-Reborn) | `v1.3.6` | Existing iOS host and default core |
| [touchHLE](https://github.com/touchHLE/touchHLE) | `v0.3.0` | Source for the second core |

The build workflow checks out these exact tags, builds and preserves a Core A baseline, then applies the iOS adapter and JIT patch to touchHLE v0.3.0 and attempts a dual-core build.

## Build on GitHub

1. Open **Actions**.
2. Run **iOS build (HyperHLE + touchHLE dual-core)**, or push a change to `main`.
3. Download the generated IPA and build report from the workflow artifacts.

The artifact contains the preserved Core A baseline IPA and, if the adapter build succeeds, a dual-core candidate IPA. The candidate is not a release until it passes physical-device validation.

## Project layout

- `.github/workflows/build-ios.yml` — macOS CI pipeline
- `config/upstreams.env` — immutable upstream tag pins
- `docs/ARCHITECTURE.md` — target design and boundaries
- `docs/INTEGRATION_STATUS.md` — verified facts and remaining work
- `integration/touchhle-ios-entry/` — Core B Rust C-ABI adapter
- `integration/touchhle-ios-entry/include/touchhle_core.h` — Core B exported C ABI
- `scripts/patch-touchhle-ios.py` — applies the iOS patch to official v0.3.0 at build time
- `docs/CORE_B_IMPLEMENTATION.md` — adapter, JIT and validation notes
- `integration/CoreABI.h` — separate proposed generic ABI, not yet consumed by the current host

## Important platform/JIT constraints

The upstream v1.3.6 iOS documentation describes TrollStore/JIT paths for specific iOS versions and device generations. Do not assume every iOS 15+ device has the same JIT behavior. In particular, its permanent-JIT build is documented as unsuitable for A12 and newer devices. See the [upstream iOS documentation](https://github.com/KlugKlugTG/HyperHLE-Reborn/blob/v1.3.6/platform/ios/README.md).

## Legal

No commercial games, decrypted IPAs, Apple firmware, signing certificates, or provisioning profiles are included. Use only software you are legally entitled to use. Review and preserve the licenses of both upstream projects and all bundled dependencies before redistribution.
