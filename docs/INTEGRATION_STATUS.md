# Integration status

Last checked: 2026-11-05

## User-confirmed device validation

- [x] Core A (HyperHLE-Reborn v1.3.6) passes on one physical iPad running iOS 15.
- [ ] Core B (official touchHLE v0.3.0) physical-device runtime validation remains pending.

## Verified from upstream source and CI

- [x] HyperHLE-Reborn tag v1.3.6 exists.
- [x] Official touchHLE tag v0.3.0 exists and is the only secondary-core source used by CI.
- [x] Core A builds and packages successfully.
- [x] Core B iOS adapter compiles against official touchHLE v0.3.0 (Run #33).
- [x] Core B exports touchhle_ios_run_game and touchhle_ios_request_exit.
- [x] Core B links against the host's shared SDL2 and declares iOS 15.0 as its minimum deployment target.
- [x] Dual-core TrollStore IPA packaging completed successfully (Run #33).
- [x] Host core picker and per-game selection use the installed dylibs; the secondary entry is relabelled touchHLE v0.3.0.
- [ ] The follow-up CI run must confirm the final labelled IPA contains both expected core dylibs.

## Remaining device validation

- [ ] Confirm JIT entitlements and behavior on the target iPad running iOS 15.
- [ ] Launch a known-compatible game using touchHLE v0.3.0.
- [ ] Validate touch/controller input, orientation, graphics and audio.
- [ ] Validate suspend/resume, clean exit, repeated launch and switching between cores.
- [ ] Rerun the Core A regression checklist on the final dual-core IPA.
- [ ] Record exact iPad model, iOS build and test games.

## Release gate

A CI-built IPA is a build candidate, not yet a validated release. Mark the dual-core project complete only after Core B runs on the target iPad and the Core A regression checklist still passes.
