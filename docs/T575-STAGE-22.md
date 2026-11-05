# Stage 22 — verify saved BOOT/DTBO exactly match working Android

The owner's local private copies now match the SM-T575 partition geometry
and basic image signatures. Observed BOOT header: version 2, 2048-byte
pages, kernel length 32,194,592 bytes, ramdisk 1,549,209 bytes, DTB
189,700 bytes. Local image SHA-256 hashes were recorded privately.
These findings validate format, not provenance or restoration.

`scripts/t575-stage22-live-backup-compare.py` performs the next check:
it hashes the existing private local files and independently streams the
live BOOT and DTBO partitions from rooted Android via ADB, comparing
full-length SHA-256 without writing another image or printing raw bytes.
It requires exactly one authorized SM-T575 and checks both partition
byte counts and the stream exit code. Mismatch is a failure.

From the Mac checkout:

```bash
python3 scripts/t575-stage22-live-backup-compare.py
```

Defaults to `~/Downloads/SM-T575-Recovery` and expects
`boot-current.img` (61,865,984 bytes) and `dtbo-current.img`
(8,388,608 bytes). The tablet should be running its working rooted
Android. Read-only partition access requires Magisk root.

Do not publish the backup files to GitHub. Even an exact live match
does **not** verify stock firmware provenance, Magisk compatibility
after restore, Download-mode rollback, or safe S-Boot display takeover.
**Never flash the diagnostic LTE DTB or an upstream SM-T570 image.**
