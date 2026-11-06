# Stage 44 — compile the ARM64 TAS2562 codec object (CI only)

## Stage 43 owner-confirmed

The user confirmed all six Stage 43 source safety checks pass.
This means the codec config fragment is isolated from the original
T570 bring-up config and the T575 RT5510, sound-card and TAS2562 DTS
nodes remain disabled.

The optional `--kernel` check was **not run locally**. No actual
TAS2562 kernel object had been compiled yet.

## Stage 44 implementation

The workflow now installs an ARM64 cross-compiler
(`gcc-aarch64-linux-gnu`) and runs:

```sh
bash scripts/t575-stage44-compile-tas2562.sh "$PWD/kernel" "$PWD/t575-audio-build"
```

This runs against the **same pinned, patched kernel source checkout**
already used for compile-only DTS CI. The script:
1. Creates a separate Linux `O=` output directory, keeping its
   generated configuration and objects away from the source checkout.
2. Uses ARM64 `defconfig`, enables `CONFIG_SND_SOC_TAS2562=m`
   along with core sound and I2C prerequisites, then resolves Kconfig
   through `olddefconfig`.
3. Refuses to continue unless the requested TAS2562 symbol survives
   Kconfig resolution.
4. Compiles specifically `sound/soc/codecs/tas2562.o` via the ARM64
   cross-compiler and checks that the resulting object is AArch64.

This is an **object compile**, not the final `.ko` module build,
not a kernel image, and not a runtime test. The workflow does not
upload the codec object as a distribution artifact. The prior DTB
build/check steps are unchanged, and the existing Stage 34 safety
audit still enforces all disabled audio/display safety gates.

### CI and optional local use

The GitHub Actions workflow on `port/sm-t575-bringup` should run
when this script or the workflow is changed:

https://github.com/Forenzo/samsung-gtactive3LTE/actions

Only if you already have a **patched** kernel source checkout and an
ARM64 cross-compiler installed can you run:

```sh
bash scripts/t575-stage44-compile-tas2562.sh /absolute/path/to/kernel /absolute/path/to/separate-output
```

No need to do this locally just to verify Stage 44: GitHub Actions
runs the same check. **Do not claim compile success before the workflow
finishes** and the TAS2562 stage shows green.

### Still not established

A Linux ASoC machine path that registers T575's UAIF1/TAS2562 DAI 0
route, correct power/clock/reset handling, speaker DAPM routing and
successful hardware playback. Never enable DTS audio based solely on
successful object compilation.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
