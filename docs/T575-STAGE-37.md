# Stage 37 — TAS2562 I2C/compatible compatibility check

## Owner-confirmed Stage 36

Private BOOT + selected DTBO #5 merge contains TAS2562 at 0x4c.
Observed property **presence**, not values:

- present: `compatible`, `reg`, `status`, `pinctrl-0`,
  `pinctrl-names`, `#sound-dai-cells`.
- absent at codec node: explicit interrupt properties, `reset-gpios`,
  `shutdown-gpios`, and `vdd/dvdd/pvdd-supply`.
- Android root live status: TAS2562 `ok`; RT5510 `disabled`.

Missing vendor properties do **not** establish that the physical
amplifier lacks a reset GPIO or supply. The vendor driver and its power
management may rely on nonstandard DT properties or other components.

## Stage 37

`scripts/t575-stage37-tas2562-compatible.py` performs a limited
read-only check of the privately reconstructed FDT. It tests:
1. Whether codec's `compatible` includes `ti,tas2562` (a compatible
   supported by upstream Linux ASoC driver).
2. Whether the child's first `reg` cell equals I2C address 0x4c.
3. Whether `#sound-dai-cells` equals 1.
4. Whether the I2C parent exists and has an explicit `status`.
5. Whether a small allowlist of GPIO/interrupt properties exists.

This reports only match verdicts, normalized statuses and safe
presence/absence labels; no full compatible lists, property values,
firmware blobs, raw vendor DT, serials or MAC addresses are published.

```sh
cd ~/samsung-gtactive3LTE
git pull origin port/sm-t575-bringup
python3 -m py_compile scripts/t575-stage37-tas2562-compatible.py
python3 scripts/t575-stage37-tas2562-compatible.py
```

This is offline, uses owner-private backups, generates only temporary
FDT files deleted by the Stage 30 merge helper, and does not modify
the DTS, tablet or firmware.

Upstream reference:
https://github.com/torvalds/linux/blob/master/sound/soc/codecs/tas2562.c

Even a complete compatible/DAI match would not establish the Exynos
ABOX/ASoC machine route, timing, regulators, audio playback, or a safe
Linux boot. The prototype T570 sound machine and RT5510 remain disabled,
and DECON takeover remains disabled.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
