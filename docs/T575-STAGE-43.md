# Stage 43 — isolated TAS2562 configuration and pinned kernel source checks

## Stage 42 owner-confirmed PASS

The user pulled the disabled TAS2562 codec node and reran the
source-safety audit. All nine checks passed, including the explicit
disabled status of the new `amplifier@4c` node, disabled RT5510,
disabled T570 sound-card node and DECON takeover, carveouts and
touchscreen cap.

Stage 41 also found no TAS2562 driver references in the local
development patches/config, although the upstream Linux codec
driver exists under `sound/soc/codecs/tas2562.c`, with Kconfig
symbol `SND_SOC_TAS2562`. Do not equate a search of the local patch
directory with a complete search of the pinned Linux source.

## Changes in Stage 43

- Added `configs/gtactive3lte-tas2562-compileonly.config`: isolated
  **compile-only** fragment setting `CONFIG_SND_SOC_TAS2562=m`.
  Does not edit or replace the Wi-Fi `gtactive3-bringup.config`,
  activate the codec, or turn on audio drivers.
- Added `scripts/t575-stage43-audio-compile-config.py`: static
  validation of the isolated fragment, existing T570 configuration,
  and safe disabled LTE DTS nodes.
- Updated the existing compile-only CI workflow to inspect the **exact
  patched pinned Linux kernel** for TAS2562's Kconfig symbol, Makefile
  object and compatible string before building the existing LTE DTB.
  Trigger paths cover the LTE audio fragment and audit script.

## Run without a kernel checkout

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage43-audio-compile-config.py
python3 scripts/t575-stage43-audio-compile-config.py
```

If you already have a patched kernel checkout compatible with this
branch, use `--kernel /absolute/path/to/kernel` to check it locally.
Do not download or modify a kernel just for this test: the CI
workflow already has an exact source checkout and applies the
packaged upstream patch.

This is **source/config compatibility verification, not compiling
the actual TAS2562 module** and not runtime driver support.
The new fragment is deliberately **not applied** to any build.
The CI job still builds the existing **diagnostic DTB only** and
does not generate a Linux boot image or firmware.

## Remaining work

Before any audio enablement, validate the exact pinned driver
DAI and DAPM semantics, codec power/reset/control mechanism,
UAIF1 bit clock and pinmux, and a T575-specific machine/audio card
description. Even an actual module compile does not imply this
hardware is safe to probe.

Upstream binding reference:
https://kernel.googlesource.com/pub/scm/linux/kernel/git/stable/linux-stable-rc.git/+/refs/tags/v5.15.150/Documentation/devicetree/bindings/sound/tas2562.yaml

The codec binding accepts `#sound-dai-cells = <1>` for compatibility
but recommends `<0>` for new designs; preserve the vendor-proven
DAI index zero until the Linux sound-card translation is validated.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
