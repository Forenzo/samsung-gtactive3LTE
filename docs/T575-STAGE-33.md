# Stage 33 — read-only Magisk-assisted runtime DT status verification

## Stage 32 owner-confirmed results

The running SM-T575 kernel exposes the Android device tree. Unprivileged
ADB reported `STATUS_ABSENT` (node exists, no explicit status property)
for DSIM0, both DECON nodes, the HX83102E panel and power node, and
two modem reserved-memory nodes. It reported `STATUS_DENIED` for
DSIM1, sound, TAS2562 and RT5510. Denied access is **not** evidence
that those nodes are missing or their hardware is disabled.

## Stage 33

The owner previously confirmed that Magisk root works. The new
`scripts/t575-stage33-root-live-dt-status.py` checks exactly one
authorized `SM-T575` and root availability, then reads **only**
`status` for the four denied nodes using fixed paths. Values
are reduced to a short safe vocabulary.

```sh
cd ~/samsung-gtactive3LTE
python3 -m py_compile scripts/t575-stage33-root-live-dt-status.py
python3 scripts/t575-stage33-root-live-dt-status.py
```

Root access is strictly read-only: no files or permissions changed,
no SELinux alteration, no reboot, flash, partition access, MMIO
or device-unique properties. The owner may need to approve the Magisk
superuser prompt if one appears.

Expected offline reference from Stage 30: DSIM1 `okay`, sound
`okay`, TAS2562 `ok`, RT5510 `disabled`. The comparison is only
meaningful if the live kernel exposes the same node paths.

Actual non-wiping Download-mode recovery and safe Linux display
handover remain unverified: **RESTORE/BOOT/FLASH GATE BLOCKED**.
