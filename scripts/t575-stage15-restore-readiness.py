#!/usr/bin/env python3
"""Stage 15: read-only recovery prerequisites on an attached SM-T575.

Does not dump partitions, modify device, flash, or reboot. Any ambiguous
result is a BLOCKER; this script never approves an experimental Linux boot.
"""
import subprocess
import sys

def adb(*args):
    return subprocess.run(["adb", *args], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, timeout=15)

def read(command):
    p = adb("shell", command)
    return p.stdout.strip() if p.returncode == 0 else ""

def main():
    p = adb("devices")
    devices = [line for line in p.stdout.splitlines()[1:] if line.endswith("\tdevice")]
    if p.returncode or len(devices) != 1:
        raise RuntimeError("Connect exactly one authorized ADB device")
    if read("getprop ro.product.model") != "SM-T575":
        raise RuntimeError("SM-T575 model mismatch")
    root = read("su -c id")
    if "uid=0(" not in root:
        raise RuntimeError("Cannot verify Magisk root")
    print("Stage 15 — read-only BOOT restore readiness inventory")
    for name in ("boot", "recovery", "dtbo", "vbmeta", "vbmeta_samsung", "super"):
        # Only checks by-name links; never resolves or reads a partition image.
        command = f"su -c 'test -e /dev/block/by-name/{name} && echo present || echo absent'"
        status = read(command)
        print(f"  {name}: {status or 'unknown'}")
    print("  Current bootloader security state: NOT VERIFIED by Android properties")
    print("  Current BOOT image backup: NOT VERIFIED")
    print("  Restore-from-Download-mode procedure: NOT VERIFIED")
    print("  Matching stock firmware package: NOT VERIFIED")
    print("  Exact boot header/DTBO selection in preserved BOOT: NOT VERIFIED")
    print("RESULT: BLOCKED — inventory only, not flash/boot approval.")
    print("Never upload private firmware, Magisk images or identifiers to public GitHub.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Stopped safely: {exc}", file=sys.stderr)
        sys.exit(1)
