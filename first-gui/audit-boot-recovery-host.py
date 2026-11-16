#!/usr/bin/env python3
"""Read-only Mac-side recovery inventory for Samsung SM-T575.

No adb, heimdall, Odin, device connection, mount, reboot, flashing, or writes.
Run with --boot PATH to hash and inspect your OWN verified original boot image.
Without --boot, prints possible backups from a few explicit local directories.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import sys

EXPECTED_STOCK_SIZE = 61_865_984  # historical local observation, NOT a guarantee
ROOTS = [
    Path.home() / "samsung-gtactive3LTE",
    Path.home() / "Linux-Tablet",
    Path.home() / "Downloads",
]
NAMES = ("boot-current.img", "boot.img", "stock-boot.img", "t575-stock-boot.img",
         "boot-stock.img", "t575-boot.img")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inspect(path):
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("BOOT image argument must be a regular file")
    size = path.stat().st_size
    print("BACKUP FILE:", path)
    print("SIZE BYTES:", size)
    if size != EXPECTED_STOCK_SIZE:
        print("NOTE: differs from previously observed 61,865,984-byte backup")
    with path.open("rb") as f:
        header = f.read(1664)
    if len(header) < 1648 or header[:8] != b"ANDROID!":
        raise ValueError("Not a recognizable Android boot.img header; STOP")
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, version = struct.unpack_from("<9I", header, 8)
    print("ANDROID BOOT HEADER VERSION:", version)
    print("PAGE SIZE:", page_size)
    print("KERNEL SIZE:", kernel_size)
    print("RAMDISK SIZE:", ramdisk_size)
    print("SECOND SIZE:", second_size)
    if version != 2 or page_size not in {2048, 4096, 8192, 16384}:
        print("WARNING: unexpected version/page size; do not treat as validated recovery image")
    if not kernel_size or not ramdisk_size or kernel_size > size or ramdisk_size > size:
        raise ValueError("Implausible boot components; STOP")
    print("SHA256:", sha256(path))
    print("CONTENT: present and parseable; ORIGINAL/STOCK PROVENANCE: NOT VERIFIED")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path, help="Exact owner backup path to inspect (no device writes)")
    a = p.parse_args()
    print("SM-T575 HOST RECOVERY INVENTORY — READ ONLY")
    for exe in ("adb", "heimdall", "python3", "shasum"):
        print(f"HOST TOOL {exe}: {shutil.which(exe) or '(not on PATH)'}")
    if a.boot:
        inspect(a.boot)
    else:
        candidates = []
        for root in ROOTS:
            for name in NAMES:
                candidate = root / name
                if candidate.is_file():
                    candidates.append(candidate)
        print("\nPOSSIBLE LOCAL BACKUPS:")
        for path in dict.fromkeys(candidates):
            print(f"  {path} ({path.stat().st_size} bytes)")
        if not candidates:
            print("  None in shallow known locations; pass --boot /exact/path/boot.img")
        print("Pass --boot /exact/path/to/known-backup.img to inspect contents and SHA256.")
    print("\nNOT A RESTORE-TEST. No device accessed, no writes performed.")
    print("Do not flash the experimental package based on this report alone.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as e:
        sys.exit(f"ERROR: {e}")
