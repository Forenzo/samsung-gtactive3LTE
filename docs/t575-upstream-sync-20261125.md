# SM-T575 selective upstream sync — 2026-11-25

Source staging only. No tablet installation, flashing, publication or C2 enablement performed.

Base: `ca8e2265ae7e3fd8d95a33000c6acef96a86e289` (November 24 headphone preservation snapshot). Shared upstream ancestor: `8f4314c5eb73f898abe9dd3cab0ae8b14d1eed71` (November 11). Upstream reference: `71cfecded34baf6a66b250fba55090254ba5565f`. The development snapshot is missing 53 upstream commits; fork main is missing 69. This branch is not a full merge.

## Staged

- Common r52 input boost, IRQ balancing and fake-device regression test (upstream `3e298afa6b32d117e0ce82f0ec072ea1fe334176`).
- r54 TuneD power-saver profile only, preserving existing UCM and other package contents (`fee10a80160db935b400f85f6b67e95a37ab1296`).
- r55 extension loop-device automount suppression (`082f9b2360d86b1849508ed928086b9a3d88f5fb`). Local common pkgrel 55 is a selective backport, not identical to upstream r55.
- Duranium build patches 0046 (Nura registry) and 0047 (temporary apk 3.0.9 pin; x86_64 builder only unless disabled or another verified checksum is supplied).

## Pending review

- Corrected r29 MAX77705 charger support and FS_VERITY config. Preserve LTE-only GPU override and all audio/modem patches. Never live-unload the installed charger module. Upstream r27/r28 charge limit did not actually stop charging.
- Battery care integration only with corrected driver; r61 saver cpuset and fast charging separately (upstream hardware verification pending). Latest Cairn ports tree r32/r62 includes RTC changes; do not blindly replace Nura/Duranium packages with Cairn ones.
- USB debug security, build/CI and installer changes require individual review against LTE boot, native installer and network/console safeguards. Do not import upstream private network literals or replace LTE update routing.
- C2 stays disabled; MIF/INT DVFS and deeper suspend remain unresolved. No global clock/power-domain gate changes until validated.

## Regression gates

1. Review complete upstream diff and overlapping files; preserve LTE-specific audio, modem, bootchain, installer, firmware and custom patches. Reconcile other LTE branches before any merge.
2. Validate package checksums, shell syntax, run `bash tests/input-boost/run.sh`, build common package and test image without publishing.
3. Verify known-good recovery path, RT5665 playback, protected headphone service, TAS2562 lock, Wi-Fi, USB, UFS, display, LTE device identity and modem non-regression; measure battery current and IRQ distribution. No automatic activation of experimental audio or deep idle.

No build or hardware validation has been performed on the sync branch yet.

## Second review pass

- Added the input-boost regression test to the existing check workflow without replacing LTE CI adjustments.
- Backported initrd-deadline sleep fallback and USB-prep marker handling from upstream `71cfecded34baf6a66b250fba55090254ba5565f`. Updated both source checksums; local common pkgrel 56 (selective, not upstream-equivalent). Boot/USB validation remains required.
- Installer `stock.sh` is already identical to upstream; upstream `04d5d1f99631d22805e80a6d7a79a3c6f173dc54` cherry-picked our model validation.
- Installer local-image cleanup needs cache-collision review before adoption; keep LTE install gate. Updater inactive-slot protection is useful but must match our partition labels. Paired USB SSH, unauthenticated-console gating, socket/firewall and host-tool changes are a coordinated migration; preserve the known recovery path until tested. Do not import hardcoded endpoint literals.
- Kernel r29 reference `47ddb580a8e6cc261dc82d8cc600f96836c06609`: config delta is FS_VERITY=y (built-in signatures off); the consolidated patch remains unavailable through connector contents API. Review its actual inner diff in local Git, retain `t575-gpu-first-desktop.patch` in APKBUILD, and rebuild/test rather than replace the live charger. RTC r32/r62 ports source not retrieved. Review other fork branches independently before merging; the headphone snapshot does not necessarily include every separate privacy or GPU experiment.
