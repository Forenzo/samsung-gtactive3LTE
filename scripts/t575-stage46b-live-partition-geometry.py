#!/usr/bin/env python3
"""Stage 46B: read-only Android BOOT/DTBO block mapping and size probe.

Connects to already-running Android over ADB; does NOT reboot or start
Download Mode. Executes ONLY readlink and blockdev read operations.
Never invokes Heimdall flash, modifies partitions or exports identifiers.
A match is NOT proof that Download Mode restoration works.
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys

EXPECTED = {"boot": 61865984, "dtbo": 8388608}

def run(cmd, timeout=12):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, check=False)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adb", default="adb", help="Path to adb executable")
    args = ap.parse_args()
    if not shutil.which(args.adb):
        print("ERROR: adb not found")
        return 2
    print("Stage 46B — read-only installed partition geometry")
    state = run([args.adb, "get-state"])
    if state.returncode != 0 or state.stdout.strip() != "device":
        print("ERROR: tablet must already be running Android with ADB enabled")
        return 2
    model = run([args.adb, "shell", "getprop ro.product.model"])
    if model.stdout.strip() != "SM-T575":
        print("ERROR: not identified as SM-T575; refusing probe")
        return 2
    matched = True
    for name, expected in EXPECTED.items():
        node = "/dev/block/by-name/" + name
        # Quote entire command as the su -c parameter for Android adb shell.
        script = "readlink -f " + node + "; blockdev --getsize64 " + node
        command = "su -c '" + script + "'"
        out = run([args.adb, "shell", command])
        lines = [x.strip() for x in out.stdout.replace("\r", "").splitlines() if x.strip()]
        if out.returncode != 0 or len(lines) < 2:
            print(f"  {name.upper()}: UNAVAILABLE (read-only query failed)")
            matched = False
            continue
        physical, raw_size = lines[-2:]
        try:
            size = int(raw_size)
        except ValueError:
            print(f"  {name.upper()}: INVALID block size response")
            matched = False
            continue
        expected_prefixes = ("/dev/block/", "/dev/")
        if not physical.startswith(expected_prefixes):
            print(f"  {name.upper()}: INVALID block mapping")
            matched = False
            continue
        print(f"  {name.upper()}: mapping present; size={size} bytes; "
              f"expected={expected}; " + ("MATCH" if size == expected else "MISMATCH"))
        matched &= size == expected
    print("  Download Mode PIT: NOT CHECKED")
    print("  Heimdall transport: NOT CHECKED")
    print("  Non-wiping restore: NOT PROVEN")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if matched else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print("ERROR: ADB read-only query timed out")
        sys.exit(2)
