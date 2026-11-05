# Stage 20 — find the *right* SM-T575 recovery material (offline)

Date: 2026-11-05. This is a non-destructive continuation from Stage 19.

## Stage 19 result

The two local files in Downloads, `boot.img` and `magisk-sept11.img`,
both have a recognizable Android boot header version 2 and 4096-byte pages,
but each is **100,663,296 bytes (96 MiB)**. The attached SM-T575's BOOT
partition was measured at **61,865,984 bytes (59 MiB)**; the previously
inspected stock SM-T575 firmware used Android header version 2 with
**2048-byte pages**. Their reported kernel and DTB lengths match each
other, but their ramdisk lengths differ. These observations do not
identify the originating device or prove Magisk patching.

Neither file is approved as an SM-T575 backup or flash image. The mismatch
is substantive; matching Android magic alone is insufficient.

## Stage 20 search

Run on the Mac (offline; no Android connection required):

```sh
python3 scripts/t575-stage20-targeted-recovery-search.py
```

This scans Downloads, Documents and Desktop, default maximum depth three,
for filenames suggesting T575 firmware or exact-size BOOT/DTBO candidate
images. Explicit directories can also be provided.

The script reads file metadata, not partition data or image contents.
It does not follow symlinked subdirectories, unpack Samsung archives,
upload files, or write anywhere. It prints candidate **basenames and
sizes** only. Some original stock AP packages use compressed `.lz4`
members; a filename match does not mean the archive has the current
Magisk-patched BOOT image or that it can restore current data.

A negative search does not mean no firmware exists anywhere on the Mac.
If nothing matches, manually identify the original firmware archive and
private backup location before planning a recovery method.

## Unresolved requirements

- Exact currently installed T575 BOOT image, provenance and integrity.
- Matched stock firmware for bootloader `T575XXSFEYI1`, and the relevant
  boot header, DTB, DTBO and vbmeta constraints.
- Tested, non-wiping restore process for this *specific* device.
- S-Boot DECON window and IDMA scanout ownership, without unsafe runtime
  register pokes.
- Independent CI confirmation and actual kernel image build evidence.

**BOOT SAFETY GATE: BLOCKED.** Do not flash, unlock, factory reset, or
use the upstream SM-T570 installer.
