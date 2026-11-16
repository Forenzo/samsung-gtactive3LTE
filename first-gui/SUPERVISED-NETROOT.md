# SM-T575 supervised netroot probe — first integration checkpoint

This opt-in **build-only** component extends the existing NFSv3 mount probe
with a child process and a best-effort 25-second supervising timeout. It
does not replace diagnostic PID 1, call kexec, access block devices, install
Plasma, or flash BOOT. The existing USB NCM console and watchdog live in PID 1.

The target is hard-coded to the Mac read-only NFS export
`10.77.57.1:/Volumes/T575-Plasma/rootfs`; it mounts at a uniquely required
`/mnt/t575-netroot-supervised` with ro,nosuid,nodev,noexec, reads only the
Plasma Mobile session desktop entry, and attempts a normal unmount.

**Important:** it has not been executed on the tablet. A timeout cannot
guarantee cleanup if an NFS mount enters uninterruptible kernel I/O; a stuck
mount may need a controlled reboot. The current running diagnostic kernel
reports NFS not registered, so this program deliberately refuses to run there.
Compilation does not prove safe kernel or BOOT restoration.

## Offline CI procedure

Run `t575-supervised-netroot-probe-build` manually on the development
branch. Inspect the resulting ELF header, SHA256SUMS and REVIEW-ONLY.txt.
There is no device-side execution step in this milestone.

## Next gates (not implemented)

1. Independently validate recoverability of an NFS-enabled BOOT-only
   diagnostic kernel, including a non-wiping restoration plan.
2. Design a controlled activation method that doesn't expose privileged
   diagnostic commands on general networks.
3. Once an explicitly approved NFS-enabled kernel actually boots, validate
   the filesystem probe and runtime mount failure handling.
4. Only then add isolated writable tmpfs paths and a separately supervised
   Weston/Plasma session, keeping diagnostic PID 1 alive.
