#!/usr/bin/env python3
"""SM-T575 Stage 13: read-only Android framebuffer/DT metadata comparison.

Reads targeted sysfs attributes and one 12-byte reserved-memory 'reg' DT
property. Does not map/decode live MMIO, read raw flash, reboot or write.
Does NOT establish S-Boot's scanout state or a boot-safe Linux DTB.
"""
import subprocess
import struct
import sys

def adb(*args, check=False):
    p = subprocess.run(["adb", *args], capture_output=True, check=False)
    if check and p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", "replace").strip())
    return p

def shell(cmd):
    p = adb("shell", cmd)
    return p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else "(unavailable)"

def root_cat(path):
    # Avoid passing raw Android property values/identifiers to the console.
    p = adb("exec-out", "su", "-c", f"cat {path}")
    return p.stdout if p.returncode == 0 else None

def main():
    devices = adb("devices", check=True).stdout.decode("utf-8", "replace").splitlines()
    online = [line for line in devices[1:] if line.endswith("\tdevice")]
    if len(online) != 1:
        raise RuntimeError("Require exactly one authorized ADB device")
    if shell("getprop ro.product.model") != "SM-T575":
        raise RuntimeError("SM-T575 model gate failed")
    if "uid=0(" not in shell("su -c id"):
        raise RuntimeError("Magisk root required for read-only DT property")
    print("Stage 13 — Android runtime display metadata (NOT bootloader scanout)")
    for fb in (0, 1):
        prefix = f"/sys/class/graphics/fb{fb}"
        link = shell(f"readlink -f {prefix}")
        print(f"fb{fb} kernel device: {link}")
        for attr in ("virtual_size", "stride", "bits_per_pixel", "modes"):
            val = shell(f"su -c 'cat {prefix}/{attr}'")
            print(f"  {attr}: {val}")
    path = "/proc/device-tree/reserved-memory/bootloader_fb/reg"
    raw = root_cat(path)
    if raw is None:
        print("bootloader_fb/reg: unavailable (do not infer absence)")
    elif len(raw) == 12:
        hi, lo, length = struct.unpack(">III", raw)
        base = (hi << 32) | lo
        print(f"bootloader_fb: base=0x{base:x} size=0x{length:x}")
        if base != 0xca000000 or length != 0x01400000:
            print("WARNING: stock reserve differs from audited expectation")
    else:
        print(f"bootloader_fb/reg: unexpected property length {len(raw)}")
    print("NOT PROVEN: S-Boot IDMA base/window, SysMMU bypass, clock, or Linux scanout.")
    print("NO flashing, reboot, physical register reads, or boot image creation.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"Stage 13 stopped: {exc}", file=sys.stderr)
        sys.exit(1)
