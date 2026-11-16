# Offline assembly of the experimental NFS-enabled SM-T575 BOOT candidate

The original Linux 7.3 diagnostic BOOT image was assembled from the rooted
Android BOOT backup using `scripts/t575-assemble-candidate.py` and booted
successfully on Nov 13. This experiment **reuses that packager** instead of
inventing another loader, address layout, signing scheme or initramfs.

The NFS build artifact already contains `uniLoader-linux-gtactive3` and
`ramdisk.cpio.gz`; it does **not** contain a ready Android BOOT image.
`scripts/t575-assemble-netroot-offline.py` verifies the complete ZIP and
bootchain manifest, pins the standalone ARM64 Image SHA to the owner's
previously audited 2026-11-16 NFS build, and packages its LTE-specific loader
and matching diagnostic ramdisk with the **original, privately stored Samsung
DTB**. The proven BOOT v2 assembler provides the pinned AOSP mkbootimg and
avbtool and the original private stock BOOT load addresses. The original BOOT
admission script checks the candidate offline. Neither the original firmware
nor the owner's embedded DTB is uploaded to GitHub.

## Local offline review only

The artifact previously audited on the Mac was:
`~/Downloads/t575-netroot-experimental-UNTESTED-review.zip`.

From the correct repository branch, and only if a local review image is wanted:

```sh
python3 scripts/t575-assemble-netroot-offline.py \
  --artifact ~/Downloads/t575-netroot-experimental-UNTESTED-review.zip \
  --stock ~/Downloads/SM-T575-Recovery/boot-current.img \
  --output ~/Downloads/SM-T575-Recovery/t575-netroot-BOOT-OFFLINE-REVIEW.img
```

The script refuses to overwrite an existing output, verifies the trusted
rooted Android BOOT backup by exact size/SHA, invokes the existing NFS artifact
audit, performs the independent BOOT admission check, and prints the resulting
whole-partition image SHA. It has no USB, adb, Heimdall, kexec, or boot commands.

**Even a PASS does not authorize flashing.** The owner's original rooted
Android BOOT recovery backup is verified structurally, but **a non-wiping
restore and recovery after a failed new kernel boot have not been independently
demonstrated**. Before any new hardware trial, establish and explicitly
approve a recovery plan, including forced Download Mode access after a failed
boot, BOOT-only restore behavior, preservation of USERDATA/SUPER/EFS, and
the known-good diagnostic or Android fallback. Separate experimental BOOT
approval remains required.

The new NFS image retains the familiar diagnostic PID 1 and watchdog; that
does not guarantee it will initialize on hardware or enter Download Mode
after a pre-init kernel fault. The NFS supervisor artifact is a separate
userspace program, not yet incorporated into the diagnostic ramdisk or
needed for this offline BOOT construction.

**No new GitHub build, upload, tablet reboot, flash, or NFS mount is required
to produce this candidate.**
