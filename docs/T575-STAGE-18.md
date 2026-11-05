# SM-T575 Stage 18 — offline backup discovery

Stage 17 was executed on the owner's Mac with no file paths. It correctly
reported BOOT, DTBO, and firmware as NOT PROVIDED; recovery is unverified.

Stage 18 adds `scripts/t575-stage18-find-local-backups.py`, an offline,
read-only locator for existing recovery candidates. It uses file *names and
sizes only*, skipping symlinked files/directories and common build/cache
directories. There is no ADB, network call, partition read, write, firmware
extraction, flashing, or boot attempt.

From the Mac checkout:

```bash
python3 scripts/t575-stage18-find-local-backups.py
```

Default search: `~/Downloads` down to three subdirectories. For additional
known private locations, supply their paths explicitly, e.g.:

```bash
python3 scripts/t575-stage18-find-local-backups.py ~/Documents ~/Desktop
```

Matching the raw BOOT partition size (61,865,984 bytes) or DTBO partition
size (8,388,608 bytes) is a *hint*, not proof of a correct backup.
Samsung AP/BL/CP/CSC firmware archives are not raw partition images.
Any candidate should be checked with Stage 17 using explicit file paths
and reviewed without publishing sensitive firmware or device identifiers.

**Boot safety gate remains BLOCKED** until exact working Android backups
and a tested, device-specific, non-wiping restoration plan exist. Stage 18
does not validate the S-Boot display handover.
