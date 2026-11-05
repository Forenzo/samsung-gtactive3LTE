# Stage 35 — enforce evidence-backed LTE safety checks in GitHub CI

## Result from Stage 34 (owner-confirmed)

All eight static checks passed for `dts/exynos9810-gtactive3lte.dts`:
board identity, explicit disabling of inherited RT5510/sound/DECON
takeover, preservation of LTE modem/log and S-Boot framebuffer memory
carveouts, and the T575 touchscreen 7 MHz SPI limit.

The vendor runtime comparison separately confirmed:
- DSIM1 `okay`.
- Sound `okay`.
- TAS2562 at 0x4c `ok`.
- RT5510 at 0x34 `disabled`.

Vendor Android status is **not** proof of Linux driver support. The
conservative prototype intentionally keeps sound and the inherited
T570 display takeover disabled.

## Stage 35 change

The existing `.github/workflows/t575-dtb-compile.yml` now runs the
Stage 34 source-safety audit **before** configuring and building the
compile-only LTE DTB. Changes to this safety script also trigger the
CI workflow on the LTE branch.

This helps prevent an accidental removal of the protective disabled
overrides or memory reservations from silently passing the DTB build
pipeline. The check itself is static and is not a complete semantic
device-tree parser; existing compiled-DTB audits continue independently.

To run the new CI prerequisite manually:

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage34-static-dts-safety-audit.py
python3 scripts/t575-stage34-static-dts-safety-audit.py
```

The workflow builds **only a diagnostic DTB** and uploads that DTB as
a short-lived CI artifact. It does not create a boot image, flash a
device, publish the private backups or attempt restoration.

CI success remains unconfirmed until the GitHub Actions run is
observed. A passing CI result would mean compile-only static checks
pass, **not** that Linux boots successfully.

Remaining blockers: validated non-wiping T575 Download-mode recovery,
stock firmware provenance, safe display handover, and compatible Linux
panel/audio/modem drivers. **BOOT/FLASH GATE: BLOCKED.**
