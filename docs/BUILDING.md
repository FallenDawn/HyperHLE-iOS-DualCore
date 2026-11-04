# Build notes

## Local development

The intended local environment is Windows with Git. Edit source and workflow files locally, commit, and push to GitHub. The iOS build itself runs on a GitHub-hosted macOS runner because Xcode/iOS SDK tooling is required.

## CI baseline

The workflow verifies both pinned tags; checks out HyperHLE-Reborn v1.3.6 including submodules; installs CMake, Ninja and ldid; installs the Rust iOS target; follows the upstream iOS build scripts to produce and verify the unsigned baseline IPA; and audits the official touchHLE v0.3.0 source separately.

The workflow may expose missing dependencies or runner incompatibilities on its first run. Treat the first successful CI run as the baseline qualification, not as proof of the second core.

## TrollStore packaging

TrollStore packaging is intentionally not part of the default CI workflow yet. It must be added only after validating the required entitlements, ldid behavior, device/OS compatibility, and the distinction between ordinary and permanent-JIT builds. Never upload personal signing certificates or provisioning profiles as repository secrets unless a separately reviewed signing design requires them.
