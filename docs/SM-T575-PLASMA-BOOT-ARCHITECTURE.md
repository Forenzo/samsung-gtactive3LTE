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
- [x] Mac-side export advertised via showmount and USB IPv4 ping tested: 10.77.57.1 <-> 10.77.57.2, 3/3 packets, no loss (2026-11-15).\n- [x] Tablet-side MOUNTv3 MNT and NFSv3 GETATTR RPCs succeeded from diagnostic Linux, with root file handle length 28 and NFS object type 2 (directory), 2026-11-15.\n- [ ] Actual kernel NFS filesystem mount and file reads tested (NOT YET: running diagnostic kernel lacks NFS).
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

## Tablet-side NFSv3 RPC checkpoint (2026-11-15)

The owner ran `first-gui/nfs-rpc-probe-transfer.py` via the existing IPv6
TCP/23 console, with the USB gadget's IPv4 address `10.77.57.2/30` and
macOS NFS host at `10.77.57.1`. Artifact checksum:
`54046c9fd755f62b2e4d991e19ba4436ff6ac17c14d64f24bdf931a7cb98fa0b`.

Observed on physical SM-T575:

```text
MOUNTv3 MNT authorized; root file handle length 28
NFSv3 GETATTR success: root type 2
PASS: export authorization and read-only NFS metadata access work.
run: exit 0 signal 0
```

This demonstrates an authorized NFSv3 root file handle and remote directory
metadata retrieval, not a mounted filesystem, not successful reads of all
Plasma files, and not graphical operation. The old diagnostic kernel still
reports `CONFIG_NFS_FS=n`. Only the separate experimental CI kernel includes
NFS client support. No BOOT write, flash, kexec or partition change occurred.

## No-flash NFS module attempt: blocked by missing built-in handshake API (2026-11-16)

The owner staged five verified modules in initramfs RAM. The first actual
`insmod /t575-test-sunrpc.ko` returned errno 2; the tablet's screen showed
`sunrpc: Unknown symbol` for `tls_alert_recv`,
`tls_handshake_close`, `tls_server_hello_x509`,
`tls_handshake_cancel`, `tls_get_record_type`,
`tls_client_hello_x509`, and `tls_client_hello_anon`.
The file was present at the time of this second attempt. The earlier errno 2
was a separate missing-file case. The diagnostic system continued running.

Linux 7.3's `NET_HANDSHAKE` option is `bool`, default `y` when SUNRPC is
enabled; `net/handshake/tlshd.c` exports the missing symbols. The running
kernel had no NFS/SUNRPC and evidently does not export the necessary
handshake symbols, whereas the experimental NFS modules were compiled
against a kernel configuration that includes that built-in API. Matching
`vermagic` is NOT sufficient to bridge that configuration difference.

**Do not retry the existing NFS .ko files, force-load them, or assume TLS can
be fixed by adding an ordinary module.** Pivot to the opt-in experimental
NFS-enabled kernel, first ensuring a temporary or recoverable boot procedure,
complete working USB diagnostics, preserved Android BOOT image, and owner
approval before any kexec/reboot or flash operation. No kernel switch has
been performed in this checkpoint.

## Experimental kernel pre-boot gate (2026-11-16)

The fallback plan is the opt-in NFSv3-enabled kernel, NOT attempting to
force-load the previously failed `sunrpc.ko` into the old kernel.
Workflow `.github/workflows/t575-netroot-experimental-build.yml` now
asserts compiled-in `CONFIG_NET_HANDSHAKE=y` and NFSv3 and exports the
ARM64 kernel `Image` separately for offline inspection, not installation.
Read-only physical capabilities: `python3 first-gui/kexec-readonly-preflight.py`.

**DO NOT RUN `kexec` YET.** Presence of a console command is not evidence
that the kernel implements arm64 `kexec_file_load`, nor that handoff of the
runtime device tree, reserved-memory, boot firmware state, initramfs,
console, watchdog, or USB recovery is safe. The existing command is a
low-level syscall invocation and has not been tested. Require documented
proof that a forced restart reaches the current working diagnostic console
before deliberate loss of runtime state, plus an owner-approved recovery
sequence. Until these conditions are satisfied all artifact output is
build/review only. No partition modification is part of this gate.

## Kexec no-go checkpoint (2026-11-16)

Owner ran `first-gui/kexec-readonly-preflight.py`: running kernel
`7.3.0`, taint `0`; `/proc/sys/kernel/kexec_load_disabled` and
`/sys/kernel/kexec_loaded` were both inaccessible/not exposed. These
status paths alone are not an authoritative kexec capability test.

More decisive: `bootchain/build.sh` starts the kernel configuration with
`make allnoconfig`; neither `configs/gtactive3-bringup.config` nor
`configs/t575-plasma-netroot.config` requests any CONFIG_KEXEC feature.
Therefore current and experimental diagnostic configurations do not establish
support for kexec or kexec_file_load. The TCP console's kexec command is
**not a tested, available, or approved boot mechanism**; do not invoke it.

Next boot path, if the owner explicitly chooses it: prepare an independent,
fully recoverable, BOOT-only experiment with verified stock BOOT backup,
working Download Mode/Odin fallback, exact device model and build checks,
and hard prohibition on userdata/super/metadata writes. Keep every build
artifact non-flashable/unexecuted until that recovery plan is approved.
