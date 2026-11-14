# SM-T575 LTE: first graphical Linux userspace (RAM-only first)

## Target desktop: Plasma Mobile

The owner has confirmed **Plasma Mobile** as the desired desktop. Weston is
only a short-lived compositor/input proving ground. Do **not** introduce Phosh
as the final environment. KDE KWin/Plasma Mobile with Qt, on-screen keyboard,
DBus and session support is the target once the lower graphics layer passes.

## State of the physical tablet (2026-11-13 verified)

- Mainline Linux 7.3.0 diagnostic initramfs boots on the LTE SM-T575.
- Native 1200 x 1920 DRM/KMS framebuffer is registered as exynosdrmfb.
- USB NCM diagnostic service provides a TCP/23 console.
- Wacom W9019 (/dev/input/event1): hover, X/Y, pressure, tip contact, tilt and side button tested.
- Himax HX83102E (/dev/input/event2): SPI mode 3, 10 MHz, hardware ID 83102e; tap, swipe and two simultaneous contacts tested.
- Kernel driver enumeration alone does **not** demonstrate successful Panfrost acceleration, Wayland, Phosh, suspend/resume or full-distribution boot.

## The boundary we must not cross accidentally

The current `initramfs/init.c` is a tiny nolibc diagnostic PID 1, not a distro. It does not provide apt/apk, a shell, login or a display server. The Wi-Fi SM-T570 postmarketOS Duranium disk image and installer are NOT a verified T575 desktop install. In particular, Duranium `install` writes to Android userdata; don't use it for a first UI test or silently claim compatibility.

Keep the stock Android backup, verified BOOT restore/rollback path and source-built diagnostic boot image available. Do not write Android userdata, metadata, super, vbmeta, EFS, modem or other protected partitions for a GUI proof of concept.

## Staged delivery

### Gate A: build a temporary RAM-resident Linux userspace (host/CI only)

Use reproducible, pinned aarch64 packages (Alpine/postmarketOS family) to assemble a root filesystem with:
- BusyBox/shell, minimal init or service launcher, /dev, /proc, /sys, /run setup and devtmpfs.
- kmod plus exact-version kernel modules and firmware where needed.
- libinput, libdrm, Mesa (software fallback), EGL/GLES, and a minimal Wayland compositor such as Weston.
- Remote rescue/diagnostic console or equivalent USB access, with explicit watchdog and recovery behavior.
- Correct event mapping for Wacom event1 and Himax event2; avoid relying on hard-coded numbers once udev/eudev appears.

Provide package manifest + licenses/checksums and inspect the final cpio size, memory budget (4 GB tablet), and BOOT ramdisk size limitations. Retain a console fallback if the compositor crashes.

**No on-device flashing in this stage.** First output is a CI artifact and documented inspection report.

### Gate B: first GUI boot (BOOT-only, owner-approved)

Only after the owner inspects the image and recovery path, try the new boot image in the same BOOT-only diagnostic manner as earlier. Do not touch userdata. If the image requires a new kernel, use the existing proven device tree/driver patches, preserve display/input drivers and do not assume the Wi-Fi device image works unmodified.

Pass criteria:
- Kernel boots, screen is visible and Weston draws a test pattern/window.
- USB diagnostics/recovery are accessible.
- Finger events from Himax operate GUI; S Pen operates GUI.
- No unexpected writes to Android partitions.
- Boot recovery to the previous diagnostic image or Android remains available.

### Gate C: Plasma Mobile trial

Only after Gate B passes, package and launch Plasma Mobile with KDE/Qt, KWin Wayland, session management, DBus, keyboard and login/service stack. Validate portrait orientation, on-screen keyboard, status panel, app launcher and input. Test software rendering first if Panfrost acceleration is unproven. Investigate Panfrost separately and log real evidence.

### Gate D: full postmarketOS Duranium install

Optional later milestone. Requires validated LTE-specific rootfs/image, bootchain, rollback, battery/thermal behavior, working firmware and user-approved storage/backup strategy. **Do not initiate while testing the first GUI.**

## Present next action

The first build-only Alpine ARM64 Weston test rootfs is now defined in `first-gui/` with the `t575-first-gui-userspace` workflow. Review workflow output, package manifest and tarball; then review initramfs handoff, module load order, packaging and framebuffer/DRM setup. Do not flash or run installer commands on the owner's device as part of the build.
