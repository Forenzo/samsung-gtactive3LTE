#!/usr/bin/env python3
"""Stage 16: non-destructive SM-T575 boot-partition geometry check.

Only reads Android sysfs block metadata and by-name symlink targets.
No partition data, device-unique identifiers, image creation, or writes.
"""
import subprocess
import sys

NAMES = ("boot", "recovery", "dtbo", "vbmeta", "vbmeta_samsung", "super")
EXPECTED = {"boot": 60416 * 1024, "dtbo": 8192 * 1024}

def adb(command):
    p = subprocess.run(["adb", "shell", command], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, timeout=20)
    if p.returncode:
        raise RuntimeError("ADB probe failed; no device changes were made")
    return p.stdout.strip()

def main():
    devices = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, timeout=15)
    authorized = [x for x in devices.stdout.splitlines()[1:]
                  if x.endswith("\tdevice")]
    if devices.returncode or len(authorized) != 1:
        raise RuntimeError("Exactly one authorized ADB device required")
    if adb("getprop ro.product.model") != "SM-T575":
        raise RuntimeError("SM-T575 model gate failed")
    if "uid=0(" not in adb("su -c id"):
        raise RuntimeError("Root permission gate failed")
    print("Stage 16: partition geometry metadata (read-only)")
    errors = []
    for name in NAMES:
        # Names are hardcoded, never user-controlled. readlink and blockdev
        # are metadata-only; they do not read any partition's contents.
        command = ("su -c '"
                   f"p=/dev/block/by-name/{name}; "
                   "if [ ! -e \"$p\" ]; then echo missing; "
                   "else readlink -f \"$p\"; blockdev --getsize64 \"$p\"; fi"
                   "'")
        out = adb(command).splitlines()
        if len(out) != 2 or not out[1].strip().isdigit():
            print(f"  {name}: cannot verify size ({'missing' if out == ['missing'] else 'unsupported'})")
            errors.append(name)
            continue
        target, size = out[0], int(out[1])
        # Do not print physical block path or unique host data.
        print(f"  {name}: {size} bytes ({size // 1024} KiB)")
        if not target.startswith("/dev/block/") or size <= 0:
            errors.append(name)
        if name in EXPECTED and size != EXPECTED[name]:
            print(f"    WARNING: differs from prior {EXPECTED[name] // 1024} KiB measurement")
            errors.append(name)
    if errors:
        print("METADATA CHECK INCOMPLETE: " + ", ".join(errors))
    else:
        print("Partition geometry metadata consistent with expected BOOT and DTBO sizes.")
    print("BOOT/DTBO CONTENTS: not read. Backups and Download-mode restore still unverified.")
    print("BOOT TEST GATE: BLOCKED. Do not flash or overwrite Android.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        sys.exit(1)
