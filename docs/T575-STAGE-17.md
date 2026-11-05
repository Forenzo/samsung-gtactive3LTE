# SM-T575 LTE — Stage 17: offline recovery-file inventory

Stage 16 owner-supplied read-only partition geometry:

| Partition | Bytes |
| --- | ---: |
| boot | 61,865,984 |
| recovery | 71,106,560 |
| dtbo | 8,388,608 |
| vbmeta | 65,536 |
| vbmeta_samsung | 65,536 |
| super | 7,130,316,800 |

BOOT and DTBO matched the prior readings. **Recovery remains unverified.**

Stage 17 adds `scripts/t575-stage17-local-backup-inventory.py`. It
checks only explicitly named *local files*, with no ADB/device connection.
It reports SHA-256, sizes, and raw BOOT/DTBO signature matches. This
is not proof a file is the tablet's current image, has correct provenance,
contains the right Magisk modifications or will restore correctly.
An AP firmware archive is not interchangeable with a raw partition image.

Example when candidate files already exist privately on the Mac:

```bash
python3 scripts/t575-stage17-local-backup-inventory.py \
  --boot /private/path/to/boot.img \
  --dtbo /private/path/to/dtbo.img \
  --firmware /private/path/to/original-firmware.zip
```

If no backup files exist, run without arguments for an explicit
`INCOMPLETE` result; do not fabricate paths or create a raw partition
dump simply to satisfy the script. Never commit firmware or identifiers
to this public repository.

No Linux image can be flashed until a device-specific non-wiping
restore procedure, exact working Android image backup, bootloader
state and display handover are independently validated.
