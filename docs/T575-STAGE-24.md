# Stage 24 — Offline BOOT and DTBO structure audit

## Stage 23 result

The owner's Mac (Darwin arm64) has `adb` and `heimdall` v2.2.2.
Both private copies, BOOT (61,865,984 bytes) and DTBO (8,388,608
bytes), passed previously recorded SHA-256 checks. Stage 22 also
confirmed exact byte matches to the currently running tablet.

## Stage 24 scope

The added `scripts/t575-stage24-boot-dtbo-structure.py` is offline
and read-only. It parses the *saved* BOOT v2 header and its aligned
segment sizes, and the Android DTBO table header/entry bounds and
embedded flattened device-tree magic values.

Run on the Mac:

```bash
python3 scripts/t575-stage24-boot-dtbo-structure.py
```

It defaults to `~/Downloads/SM-T575-Recovery`. It does not open
ADB, modify backup files, parse or expose device-unique identifiers,
extract proprietary firmware, or generate a flash image.

A successful structural check supports the backups' internal
consistency but is **not** a recovery demonstration. Remain blocked
until a verified non-wiping SM-T575 Download-mode restore workflow,
matching original firmware, bootloader state and S-Boot framebuffer
handover have been established. The T570 installer is still prohibited.
