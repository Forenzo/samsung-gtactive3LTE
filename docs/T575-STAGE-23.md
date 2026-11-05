# Stage 23 — Mac host restoration readiness (read-only)

Date: 2026-11-05

## Stage 22 passed

Owner-run rooted ADB comparison reported **EXACT BYTE MATCH** for both
saved private `boot-current.img` (61,865,984 bytes) and
`dtbo-current.img` (8,388,608 bytes) against the corresponding live
SM-T575 partitions. These are accurate copies of the *currently installed*
Android state; they are not necessarily original stock firmware.

## Stage 23 offline host preflight

Run from the Mac:

```bash
python3 scripts/t575-stage23-host-recovery-preflight.py
```

This script checks for the installed `adb` and `heimdall` commands,
reports the host OS, and independently hashes the two saved images
against the previously recorded owner-supplied SHA-256 values. It does
not contact the tablet, enumerate USB devices, write files, reboot,
flash, alter verified boot, or access the network.

This step tests prerequisites only, NOT the ability to restore from
Download mode. Heimdall's presence or version does not prove that its
specific T575 transport/driver combination can recover the device.
A real restoration test would be invasive and needs separate approval
and an established recovery plan.

Still unverified: matching original firmware, T575 Download-mode restore
workflow, bootloader state, full boot-image dependencies, and S-Boot
DECON/simpledrm handover. **No Linux boot is authorized.**
