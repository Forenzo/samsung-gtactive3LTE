# SM-T575 experimental diagnostic Linux: power off without restoring Android

**Scope:** Samsung Galaxy Tab Active3 LTE SM-T575, with the opt-in
NFS-enabled diagnostic Linux 7.3.0 BOOT image on the device and USB
NCM debug console on IPv6 link-local `<USB_CONSOLE_IP>%<USB_IFACE>`.
This is a manual end-of-session power-off, not a repair/flash recipe.

The owner requested that the exact procedure be saved for subsequent
sessions. It was supplied after a successful RAM-only supervised NFS
probe and input driver bring-up, with no filesystem mounted for writes.
The owner's next message was positive; independent verification of
power-off/current draw was not captured.

## From macOS Terminal, while the USB console is reachable

```bash
python3 - <<'PY'
import socket

with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
    s.settimeout(10)
    s.connect(("<USB_CONSOLE_IP>", 23, 0,
               socket.if_nametoindex("en7")))
    s.recv(4096)
    s.sendall(b"write /proc/sysrq-trigger o\n")
    print("Linux power-off requested.")
PY
```

The existing `initramfs/init.c` debug console offers
`write PATH VALUE`; the kernel has `CONFIG_MAGIC_SYSRQ=y`.
Writing `o` to `/proc/sysrq-trigger` invokes the Magic SysRq
power-off path rather than the console's `reboot` command.

**Cautions:**
- This is a comparatively abrupt SysRq power-off, not a full
  userspace-managed shutdown. Stop tests and unmount any writable
  filesystems first. The previous test only used read-only NFS and
  cleanly unmounted it.
- If the tablet enters Download Mode or restarts, stop and assess;
  do not issue repeated blind resets.
- Unplug USB after verifying it is really off. Connecting a charger
  may cause platform-specific wake/charging behavior.
- BOOT remains the experimental diagnostic Linux, not stock Android.
  On next boot, USB IPv4 setup, RAM helpers and manual Wacom/Himax
  module insertion must be repeated if not made persistent.
- This instruction is valid for this exact reviewed diagnostic console
  and kernel setup, not general Android or arbitrary Galaxy tablets.

No BOOT/DTBO/userdata writes, reflash, kexec or bootloader register
operations are involved in this power-off request.
