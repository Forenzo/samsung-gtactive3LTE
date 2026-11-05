# Stage 25 follow-up: non-raw BOOT DTB segment

The owner ran Stage 25 on the private, previously SHA-256 verified SM-T575
BOOT and DTBO backups. The first version stopped at the BOOT DTB location
(offset 33,748,992, length 189,700) because the first four bytes were
**not** the normal flattened-device-tree magic `d00dfeed`.

This does **not** invalidate the backup: Stage 22 already verified that
this BOOT image exactly matches the working tablet's partition, and
Stage 24 verified the Android boot image container and its bounds.
The DTB field in an Android v2 BOOT header does not by itself ensure
that its payload is a single raw FDT; vendor-specific packing is possible.

The Stage 25 checker has now been revised to report only the first 16
bytes as hex, scan within the BOOT DTB segment for plausible FDT magic,
verify any candidate FDT headers and continue validating selected DTBO
overlay #5 even if the BOOT segment's internal packaging is unresolved.

Run again on the Mac:

```bash
python3 scripts/t575-stage25-dt-structure.py
```

If no valid embedded FDT is found, the script reports **PARTIAL** and
exits with status 2. Do not call that a passing result, and do not infer
corruption merely from this outcome. The next step would be identifying
the stock Samsung DTB container format offline.

All operations remain local and read-only. No firmware, backup images,
identifying DT properties or raw device data are uploaded to GitHub.
The first Linux boot and restoration gates remain **BLOCKED**.
