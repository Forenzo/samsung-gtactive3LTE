# SM-T575 compile-only kernel device-tree target

**Not bootable or validated. Do not flash this DTS or a boot image derived from it.**

`dts/exynos9810-gtactive3lte.dts` is the first source tree for the SM-T575,
derived by including the **fully patched** upstream SM-T570
`exynos9810-gtactive3wifi.dts`. It inherits shared Exynos9810 drivers,
display, touch and other board descriptions, **none of which have been
validated on LTE**.

## What changes for the LTE prototype

- Adds LTE-specific `model` and `samsung,gtactive3lte` compatible.
- Disables the inherited RT5510 sound-card and amp. The owner's live FDT
  instead enables a **TI TAS2562** at address `0x4c` on a different bus
  numbering scheme; do not invent its mainline bus assignment or DAI graph.
- Disables PCIe0 Wi-Fi and Bluetooth until wiring/firmware is confirmed.
  **Correction:** both T570 upstream Linux patch 0071 and the live T575
  Android FDT use **PCIe0**, not PCIe1, for the active WLAN path. A previous
  progress update compared inconsistent controller descriptions.
- Does **not** pretend to implement the modem: the stock `modem_if`
  reserved memory and `mif_pdata` require a separate mainline analysis.
- Does not change any existing Wi-Fi device-tree source, installer,
  bootchain, firmware, package channels or automatic flashing commands.

## Build-only instructions (Linux with complete upstream source tree)

First assemble the **entire** SM-T570 kernel tree from the exact
`patches/linux/BASE` commit plus all upstream `patches/linux/*.patch`
in order, using upstream's normal tooling. This repository fork itself does
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
pinned kernel base from `patches/linux/BASE`, applies the numbered kernel
patches, runs the native arm64 `defconfig` DTB target and uploads **only the
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
