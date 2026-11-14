# SM-T575 first GUI: Wayland proving ground, Plasma Mobile target

This directory builds an **aarch64 Alpine userspace tarball** with Weston DRM,
Mesa, libinput, seatd, udev and supporting libraries, as a **GitHub Actions
artifact only**. It is NOT a boot image, not a runnable tablet OS, not a
Duranium installation, and does not contain any commands that modify BOOT or
Android partitions.

The intended final desktop is **Plasma Mobile**, as requested by the device
owner. Weston is merely a temporary Wayland/DRM/input test compositor to
separate display-driver problems from KDE/Qt/Plasma issues; it will not be
installed as the intended daily-use shell.

## Build

Run the workflow `t575-first-gui-userspace` on
`integration/upstream-active3-family-firstboot`. The workflow builds an ARM64
container image with QEMU emulation, exports its root filesystem into
`t575-weston-userspace-aarch64.tar.gz`, and uploads:

- the rootfs tarball,
- an installed package/version manifest,
- a SHA256 manifest,
- an archive inspection result.

No on-device shell is involved. No `heimdall`, `adb`, or partition-flash
command is used. The workflow does not create a boot image.

## Important outstanding integration work

1. Review archive size and package completeness, and pin the base image to an
   immutable digest once the first successful build is verified. Image tag
   `alpine:3.22` and floating Alpine package revisions are not fully
   reproducible; the package manifest records the exact resolved versions.
2. Implement a deliberately temporary initramfs-to-userspace handoff with
   recovery diagnostics and correct mounts for `/dev`, `/proc`, `/sys`,
   `/run` and udev events. Current `initramfs/init.c` remains our proven
   minimal diagnostics PID 1; it does NOT have a desktop session manager.
3. Integrate the **exact Linux 7.3.0 kernel modules** and correct load order
   (Wacom I2C; SPI and Himax; DRM). The rootfs package does not carry these
   kernel modules and cannot be booted independently.
4. Check kernel initramfs/BOOT space and whether RAM use of the extracted
   userspace fits the tablet. Keep verified stock BOOT restore available.
5. In the first actual graphical test, run Weston *only after* DRM/input
   permissions, device nodes, seat management and USB diagnostics work.
6. After Weston succeeds, build a KDE/Qt-oriented image with Plasma Mobile,
   KWin, keyboard, DBus and a working login/session path, then prove touch,
   stylus, orientation and GPU behaviour. A fully working Plasma session is
   not implied by the current Wacom/Himax evdev tests.

**Do not use the current Wi-Fi Duranium installer as a shortcut on the LTE
tablet.** Its full install path writes Android USERDATA.

Known device evidence: DRM at 1200 x 1920; Wacom W9019 uses evdev; Himax
HX83102E reports two simultaneous contacts on the physical SM-T575.

The base Alpine v3.22 package is a development convenience for this very first
test. The postmarketOS/Alpine-derived Plasma Mobile build remains the
longer-term target; substituting another distro later remains possible.
