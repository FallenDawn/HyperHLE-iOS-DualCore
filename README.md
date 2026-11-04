# HyperHLE-iOS-DualCore

Dual-core iOS host integration project targeting iOS 15+ and TrollStore, developed on Windows and built on GitHub Actions macOS runners.

## Current integration strategy

- **Core A (default):** HyperHLE-Reborn **v1.3.6**, using its existing Applesauce-derived iOS host and build pipeline.
- **Core B (planned):** official touchHLE **v0.3.0**, integrated through a separately maintained iOS adapter. The upstream v0.3.0 tag is not itself an iOS-ready drop-in core; this adapter is not yet implemented.
- **Host:** retain the upstream iOS host (Swift/UIKit/SDL2) wherever possible; add a core-selection layer only after verifying the host's actual lifecycle and ABI.
- **Build:** Windows for source editing and Git operations; GitHub Actions macOS runner for Xcode/Rust/iOS builds.

This repository currently contains the integration scaffold, source pins, CI entry point, and implementation notes. It does **not** yet contain a completed touchHLE iOS adapter or claim a working dual-core IPA.

## Pinned upstreams

| Component | Revision | Role |
|---|---|---|
| [HyperHLE-Reborn](https://github.com/KlugKlugTG/HyperHLE-Reborn) | `v1.3.6` | Existing iOS host and default core |
| [touchHLE](https://github.com/touchHLE/touchHLE) | `v0.3.0` | Source for the second core |

The build workflow checks out these exact tags. It builds the existing HyperHLE iOS app first; touchHLE adapter integration is tracked separately.

## Build on GitHub

1. Open **Actions**.
2. Run **iOS build (HyperHLE baseline)**, or push a change to `main`.
3. Download the generated IPA and build report from the workflow artifacts.

The baseline build follows the upstream v1.3.6 iOS instructions and is not a dual-core release.

## Project layout

- `.github/workflows/build-ios.yml` — macOS CI pipeline
- `config/upstreams.env` — immutable upstream tag pins
- `docs/ARCHITECTURE.md` — target design and boundaries
- `docs/INTEGRATION_STATUS.md` — verified facts and remaining work
- `integration/CoreABI.h` — proposed host/adapter boundary (not yet implemented by either core)

## Important platform/JIT constraints

The upstream v1.3.6 iOS documentation describes TrollStore/JIT paths for specific iOS versions and device generations. Do not assume every iOS 15+ device has the same JIT behavior. In particular, its permanent-JIT build is documented as unsuitable for A12 and newer devices. See the [upstream iOS documentation](https://github.com/KlugKlugTG/HyperHLE-Reborn/blob/v1.3.6/platform/ios/README.md).

## Legal

No commercial games, decrypted IPAs, Apple firmware, signing certificates, or provisioning profiles are included. Use only software you are legally entitled to use. Review and preserve the licenses of both upstream projects and all bundled dependencies before redistribution.
