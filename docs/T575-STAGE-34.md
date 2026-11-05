# Stage 34 — T575 DTS static safety alignment

## Stage 33: owner-confirmed PASS

After correcting Magisk `su -c` quoting, the owner read four live
root-protected runtime device-tree `status` properties. All agreed
with the independently reconstructed BOOT+DTBO #5 FDT:

| Node | Offline merge | Live Android |
| --- | --- | --- |
| DSIM1 | okay | okay |
| sound | okay | okay |
| TAS2562 amplifier at 0x4c | ok | ok |
| RT5510 amplifier at 0x34 | disabled | disabled |

This is confirmed evidence for the **stock Android configuration**,
not proof that all four drivers are usable by mainline Linux.

## Current Linux DTS comparison

`dts/exynos9810-gtactive3lte.dts` already:
- overrides the inherited T570 audio amplifier at 0x34 to disabled;
- keeps the inherited board sound card disabled pending TAS2562/ASoC
  controller/supply/IRQ/DAI mapping validation;
- disables the unverified inherited DECON-F takeover;
- preserves LTE modem/log RAM and S-Boot framebuffer carveouts;
- caps the T575 touchscreen SPI to the earlier measured 7 MHz.

These precautions should remain in place even though Android has a
working TAS2562 audio device and explicitly enabled DSIM1. The stock
Android nodes and the mainline/postmarketOS driver implementations
are not interchangeable.

## Stage 34 static check

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage34-static-dts-safety-audit.py
python3 scripts/t575-stage34-static-dts-safety-audit.py
```

This checks the current public LTE DTS source for conservative overrides
and carved-out memory. It neither touches private backups nor contacts
the tablet. A PASS is **not** compile-test success or a Linux boot gate.
Do not enable inherited T570 display or sound merely because stock
Android describes those peripherals as `okay`.

Next useful work is driver binding/topology research for TAS2562,
panel/DSIM routing and S-Boot display handover, together with a proven
non-wiping T575 restoration path. The latter is still a prerequisite
for any experimental boot.

**RESTORE/BOOT/FLASH GATE: BLOCKED.**
