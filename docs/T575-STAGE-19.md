# SM-T575 LTE — Stage 19: offline BOOT candidate header inspection

Stage 18 scanned the owner's Mac Downloads folder and discovered two
candidate files, `boot.img` and `magisk-sept11.img`. Each was
100,663,296 bytes (96 MiB), which **does not match** the SM-T575 BOOT
partition size measured at Stage 16: 61,865,984 bytes (59 MiB).
They may belong to another device or be differently formatted; neither
is considered a validated backup.

Stage 19 adds `scripts/t575-stage19-boot-header.py` to read only the
first 4096 bytes of each candidate. It identifies Android boot magic,
header kernel/ramdisk sizes, and legacy boot header version/page size
when applicable. The working SM-T575 firmware previously showed Android
boot header version 2, 2048-byte pages. Do not assume matching header
fields demonstrate correct provenance or recoverability.

Run with explicit local paths:

```bash
python3 scripts/t575-stage19-boot-header.py \
  ~/Downloads/boot.img ~/Downloads/magisk-sept11.img
```

No Android device or ADB connection is involved; no image files are
changed, extracted, uploaded or flashed. The output does not establish
that a candidate is the presently installed Magisk-patched T575 BOOT.
Any image-size mismatch remains a significant unresolved finding.

**BOOT TEST GATE: BLOCKED.** An exact current backup and a tested,
device-specific non-wiping restoration procedure are still required.
