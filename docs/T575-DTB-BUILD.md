# SM-T575 compile-only kernel device-tree target

**Not bootable or validated. Do not flash this DTS or a boot image derived from it.**

`dts/exynos9810-gtactive3lte.dts` is the first source tree for the SM-T575,
derived by including the **fully patched** upstream SM-T570
`exynos9810-gtactive3wifi.dts`. It inherits the T570 board descriptions **without validating their safety on LTE**.

## What changes for the LTE prototype

- Adds the LTE-specific `model` and `samsung,gtactive3lte` compatible.
- **Identity-only**: this is a compilation baseline that inherits T570 hardware
  definitions, which have **not** been validated on the LTE board and must
  **not** be used for a boot test.
- The T575 hardware inventory identifies **TAS2562** as the active speaker
  amp, not the RT5510 populated on a tested T570 revision. Correct
  audio bindings are deferred until the packaged kernel's actual DTS is
  inspected.
- The live T575 Android device tree uses **PCIe0** for the enabled controller.
  Preserve this observation for the future wireless integration; inherited
  PCIe wiring is not automatically safe for T575.
- The LTE modem reserved-memory interface is recorded but has not been
  ported. No LTE driver has been enabled.

This preliminary target only tests the kernel source/DTB toolchain. It does
not establish T575 hardware compatibility or implement LTE support.

## Build-only instructions (Linux with complete upstream source tree)

First assemble the SM-T570 kernel tree from the exact
`patches/linux/BASE` commit with the **consolidated** upstream patch
`pmos/aports/device/testing/linux-postmarketos-exynos9810/gtactive3wifi.patch`
used by the upstream APKBUILD. The historical numbered `patches/linux/*.patch`
are not a clean sequential replay: the CI run failed at patch 0029. The
consolidated patch is the supported input for this compile experiment. This repository fork itself does
not contain the full Linux kernel source.

Then run from the fork repository directory:

```sh
scripts/build-t575-dtb.sh /absolute/path/to/patched/linux
```

The script copies a single new DTS and adds its DTB to the patched
kernel's Exynos Makefile (only in that local source checkout), then
invokes `make ARCH=arm64 exynos/exynos9810-gtactive3lte.dtb`.
This is a **compile-only** action: it neither creates an Android BOOT image
nor flashes or changes the tablet.

The script checks that upstream SM-T570 DTS is present and relevant
labels/nodes exist. It needs a working kernel host toolchain. A successful
DTC output **does not mean the kernel can boot on T575**; further checks
of reserved RAM, modem carveouts, IOMMU, power, and audio are required.

## Next hardware validation

Compare the live T575 DTB (never commit it publicly) against the assembled
patched SM-T570 DTS for reserved RAM and all power rails, GPIOs and
peripheral node `reg` addresses. Independently confirm the actual TAS2562
mainline driver/bindings; don't guess. Keep the inherited installer and
automated release workflow for SM-T570 only until the LTE boot chain is
separately verified.

## Automatic build on GitHub Actions (recommended)

This fork also has a **separate compile-only** workflow:
[.github/workflows/t575-dtb-compile.yml](../.github/workflows/t575-dtb-compile.yml).
It is scoped to `port/sm-t575-bringup` and source changes. It downloads the
pinned kernel base from `patches/linux/BASE`, applies the packaged consolidated
kernel patch, runs the arm64 `defconfig` DTB target and uploads **only the
DTB** for inspection. It does not build/flash Android BOOT or produce a
Duranium image.

To see progress, open your fork's **Actions** tab and look for
`t575-dtb-compile`. New forks can have Actions disabled: enable them from
the GitHub Actions page if GitHub offers the prompt. The workflow must be
allowed to run on the branch. A successful green job means **DTB compiles**
only, not that it is boot-safe. If it fails, retain the logs and fix the
patch/DTB build failures before trying any device boot.

This workflow has *not been verified as successful* yet. Its source download
depends on GitHub archive availability. No output is presently cleared for
flashing to the SM-T575.
