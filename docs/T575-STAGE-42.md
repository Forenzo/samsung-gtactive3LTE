# Stage 42 — LTE-specific TAS2562, disabled by default

## Owner-confirmed Stage 41

The local repository source scan found no TAS2562 driver references in
`drv/audio`, the device patches or bring-up configuration, but
identified the existing ABOX driver and T570 RT5665/RT5510 machine
driver. The T570 DTS uses ABOX DAI1 for its speaker; the owner's
SM-T575 Android DTBO #5 uses UAIF1 with TAS2562 DAI 0.

A source scan does not enumerate the upstream kernel's native drivers.
Linux has the codec implementation and Kconfig symbol
`CONFIG_SND_SOC_TAS2562` in `sound/soc/codecs/tas2562.c` and Kconfig.
Reference:
https://github.com/torvalds/linux/blob/master/sound/soc/codecs/tas2562.c
and
https://github.com/torvalds/linux/blob/master/sound/soc/codecs/Kconfig

The Wi-Fi machine patch
`patches/linux/0108-ASoC-samsung-Add-Galaxy-Tab-Active3-RT5665-RT5510-ma.patch`
currently **selects** `SND_SOC_MT6660` for its RT5510-era amplifier and
only supplies a `samsung,gtactive3-audio` machine binding. Simply
selecting TAS2562 or enabling the card is insufficient, because the
machine codec linkage, routing/power, clocking, speaker DAPM widgets and
matched kernel driver are not validated.

## Stage 42 source changes

`dts/exynos9810-gtactive3lte.dts` now has a **disabled** child node on
the same Linux HSI2C controller that inherited the Wi-Fi RT5510:

```dts
&{/soc@0/usi@108c00c0/i2c@108c0000} {
    t575_tas2562: amplifier@4c {
        compatible = "ti,tas2562";
        reg = <0x4c>;
        #sound-dai-cells = <1>;
        status = "disabled";
    };
};
```

These fields are independently grounded in the reconstructed
Android DT and UAIF1 -> TAS2562 phandle/DAI tuple. The node is
**not enabled** and no runtime driver may probe it. No speculative
GPIO, power supply, interrupt or clock properties have been added.

The existing T570 RT5510 amplifier, inherited sound card and DECON-F
display takeover **remain disabled**, and all reserved memory
carveouts remain unchanged.

The existing Stage 34 CI safety audit now also fails if this newly
introduced TAS2562 node loses its `disabled` status or its
verified I2C/DAI fields.

## Offline validation

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage34-static-dts-safety-audit.py
python3 scripts/t575-stage34-static-dts-safety-audit.py
```

The repository's existing GitHub Actions workflow should also perform
a compile-only DTB build because this change touches `dts/**`.
Do not infer compile success until the workflow result is observed.

**Before any audio enablement:** verify exact pinned kernel TAS2562
Kconfig/DAI behavior, I2C supplies and enable sequence, machine driver,
ABOX UAIF clocks and audio DAPM widget/routing. Do not use RT5510
speaker routes without validating TAS2562-specific topology.

**RESTORE/BOOT/FLASH GATE: BLOCKED.** No boot image or flashing.
