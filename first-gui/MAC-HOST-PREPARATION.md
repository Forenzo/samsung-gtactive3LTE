# SM-T575 LTE: macOS host preparation for Plasma Mobile

This is a **read-only host preparation task**, not a tablet installation.
The intended desktop is **Plasma Mobile**, and the only firmware proven to
boot the LTE hardware remains the small Linux 7.3 diagnostic boot.

## 1. Download the verified Plasma userspace artifact

Open the completed workflow run:

https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/43613442608

Under **Artifacts**, download:
`t575-plasma-mobile-aarch64-build-only`

Save the ZIP somewhere with at least 3 GiB free. The workflow produced
an approximately 753 MB ZIP containing the compressed rootfs, package
manifest, SHA256 checksums, and archive listings. The root filesystem
contains roughly 1.8 GiB of installed packages.

**Do not flash this archive**: it is not an Android boot image.

## 2. Inspect the archive before doing anything else

With the GitHub repository checked out on the Mac, run:

```sh
python3 first-gui/host-audit-plasma.py \
  ~/Downloads/t575-plasma-mobile-aarch64-build-only.zip
```

The filename may differ if the browser renamed the ZIP. This check
verifies the rootfs checksum from the CI manifest, package list, and
the presence of KWin and Plasma Mobile's Wayland session files.
The script **does not extract** the archive or execute any ARM binaries.

Expected output includes:
- `SHA256 OK`
- `Plasma Mobile executable and session files: PRESENT`
- `Inspection only. No extraction, no NFS export and NO tablet changes.`

## 3. USB network readiness

On the tablet we previously verified:
- USB NCM diagnostic link up,
- diagnostic TCP console reachable at `fe80::57:aff:fe00:1` using
  the macOS `en7` link-local interface (interface number can change),
- working display, Wacom pen and Himax multitouch.

**This does not prove that NFS mounts work.** The diagnostic init is a
limited TCP console, not a Linux shell, and the kernel's complete
NFS capability must first be confirmed by the separate CI audit:
`.github/workflows/t575-diagnostic-build.yml`.

To see which Mac interface currently carries the tablet, inspect
`ifconfig` and `networksetup -listallhardwareports`. Do not assume
the interface is always `en7`.

Do **not** launch `nfsd`, write `/etc/exports`, or expose a
world-readable NFS directory until the device-side kernel, network
addressing, mount point and recovery design have been tested. In
particular, don't export your entire home directory or internal disk.

## 4. Boot handoff is still future work

We still need an experimental kernel with NFS client support, a
minimal userspace able to mount the host export after USB gadget
initialization, a carefully designed read-only rootfs with RAM
writable state, and a recoverable handoff to a Plasma session.

Those steps do not come for free from the package build. No image
is yet ready for flashing or running a graphical session on the tablet.

The working diagnostic image and Android partition contents are to
remain untouched until the owner explicitly approves a new BOOT-only
test and its rollback procedure.
