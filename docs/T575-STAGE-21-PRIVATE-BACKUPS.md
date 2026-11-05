# Stage 21 — working Android BOOT/DTBO private backup checkpoint

Date: 2026-11-05

The owner used rooted ADB on the working SM-T575 to copy the currently
installed BOOT and DTBO partitions to a private folder on the Mac:
`~/Downloads/SM-T575-Recovery/`.

| Image | Observed bytes | Device partition bytes |
| --- | ---: | ---: |
| boot-current.img | 61,865,984 | 61,865,984 |
| dtbo-current.img | 8,388,608 | 8,388,608 |

The user recorded SHA-256 checksums locally. Neither the raw images
nor private local paths/checksums need to be committed to this repository.
The images are of the *currently installed* Android, potentially
Magisk-modified; they are not known pristine stock firmware.

Next perform offline sanity checks using existing scripts:

```bash
python3 scripts/t575-stage17-local-backup-inventory.py \
  --boot "$HOME/Downloads/SM-T575-Recovery/boot-current.img" \
  --dtbo "$HOME/Downloads/SM-T575-Recovery/dtbo-current.img"

python3 scripts/t575-stage19-boot-header.py \
  "$HOME/Downloads/SM-T575-Recovery/boot-current.img"
```

This checks sizes, signatures and legacy boot header format. A further
read-only comparison of the saved files against the *live* partitions
would improve confidence in transfer integrity, but must be implemented
with failure detection and without treating raw partition bytes as
shareable GitHub data.

**Recovery remains BLOCKED:** partition-sized backups alone do not
validate a non-wiping T575 restore path, compatible Download-mode
flashing, exact bootloader state, or a Linux display handover. Do not
flash the images, alter vbmeta, reboot into experimental Linux, or run
the SM-T570 installer.
