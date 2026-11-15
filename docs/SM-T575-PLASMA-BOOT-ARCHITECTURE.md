# SM-T575 Plasma Mobile: boot architecture after the first ARM64 build

Verified on 2026-11-14 from GitHub Actions run 43613442608:
- Plasma Mobile aarch64 userspace built and package checks passed.
- 669 Alpine packages installed; apk reports 1815 MiB.
- exported tar.gz approximately 725 MiB; Actions artifact approximately 753 MB.
- Plasma Mobile 6.3.6, KWin 6.3.6, plasma-workspace 6.3.6, mobile
  and ordinary Plasma wayland session files installed.
- This is a **root filesystem archive**. It is NOT a boot image.
- No graphics session has been launched on the LTE tablet.

## Design decision

Do not embed a ~725 MiB compressed desktop archive in the existing Android
BOOT ramdisk. It is much larger than the current diagnostic payload, and an
unpacked ~1.8 GiB userspace is a significant fraction of the T575's ~4 GiB RAM.
Do not invoke the Wi-Fi variant's full Duranium installer: it writes userdata.

Use a **host-backed root filesystem over the already working USB NCM link**
as the preferred first trial (no Android partition writes). Keep the tiny
diagnostic environment in BOOT and treat starting the remote root as an
explicit, reversible operation.

The present kernel fragment (`configs/gtactive3-bringup.config`) enables
USB NCM and TMPFS but does **not explicitly enable an NFS, 9p or CIFS client**.
Do not presume remote mounting works on the current boot image. Before
changing hardware:
1. Inspect the *fully generated* kernel .config for CONFIG_NFS_FS,
   CONFIG_NFS_V3/4 and CONFIG_ROOT_NFS; if absent, add only the required
   client support in a future kernel build. Avoid changing proven display,
   pen, Himax, battery, UFS and USB settings.
2. Check whether a network root can be mounted after the USB NCM gadget
   is configured. This likely calls for a staged PID 1 upgrade; the existing
   nolibc console has no shell, mount command or distro handoff.
3. Export and hash the built rootfs on the host; inspect ownership, /dev,
   /proc, /sys, /run and executable symlinks. Avoid restoring the archive
   onto Android internal storage.
4. Set up NFS or equivalent read-only mount from a controlled host, with
   RAM-backed writable paths for /run, /tmp and other mutable state.
   The USB NCM link-local address does not itself establish a route
   for NFS: configure IPv4 or known stable IPv6 both sides deliberately.
5. Add explicit diagnostic PID 1 handoff (mount/chroot/exec or switch_root)
   only after ensuring that a crashed desktop can return to a recovery
   boot and that a USB disconnect cannot hang PID 1 indefinitely.
6. Load the exact-version Linux modules required by DRM, GPU and input;
   event numbers are incidental and must be discovered by device name.
   The current Wacom event1 / Himax event2 enumeration is proven but
   does not prove graphical use.
7. Start KWin Wayland and the Plasma Mobile session with seatd/dbus and
   a session user once the rootfs is live. Disable untested services.
   Fallback to Weston for isolated DRM/libinput debugging only.

## Verify before ever attempting a tablet trial

- [x] CI builds ARM64 Plasma Mobile packages.
- [x] Package preflight locates kwin_wayland and startplasma-wayland.
- [ ] Rootfs startup prerequisites audited (system services, udev, permissions).
- [x] Experimental *compiled* kernel NFSv3 client enabled in CI run 43616388593; current tablet boot still lacks NFS.\n- [ ] Experimental NFS kernel boot and module/runtime support verified on physical tablet.
- [x] Mac-side export advertised via showmount and USB IPv4 ping tested: 10.77.57.1 <-> 10.77.57.2, 3/3 packets, no loss (2026-11-15).\n- [ ] Tablet-side NFS mount and file reads tested (NOT YET: running diagnostic kernel lacks NFS).
- [ ] Safe handoff and recovery code compiled and inspected.
- [ ] GPU / DRM initialization and KWin startup logs captured.
- [ ] Owner approves any new BOOT-only image; no other partition writes.
- [ ] First Plasma Mobile frame rendered on the actual 1200x1920 screen.
- [ ] Finger input and pressure-sensitive S Pen tested in the GUI.

The source may be developed and tested in CI now without tablet changes.
The owner-selected final environment remains **Plasma Mobile**, not Phosh.

## Host network checkpoint (2026-11-15)

Owner reported macOS USB interface en7 with alias 10.77.57.1/30 and tablet usb0
10.77.57.2/30. Ping reached tablet (3/3, average ~1.14 ms). macOS nfsd
reported running (eight threads). The owner's `/etc/exports` reads:

```
/Volumes/T575-Plasma/rootfs -ro -maproot=root 10.77.57.2
```

`showmount -e localhost` advertised the expected rootfs to client
10.77.57.2. These are **host-side successes only**. No actual NFS mount,
NFS RPC reachability from the tablet, or display/session launch has been
verified. NFSv3 is not encrypted and the client restriction alone does not
restrict the service listening interfaces. Stop nfsd when not testing.

Do not execute `kexec`, flash BOOT, or attempt `mount` using the current
NFS-disabled diagnostic kernel. A recoverable experimental test environment
must be assembled and reviewed first.
