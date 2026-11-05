#!/usr/bin/env python3
"""Offline, read-only Stage 17 inventory of explicitly supplied local recovery files."""
import argparse
import hashlib
from pathlib import Path

SIZES = {"boot": 61865984, "dtbo": 8388608}
MAGIC = {"boot": b"ANDROID!", "dtbo": bytes.fromhex("d7b7ab1e")}

def check(name, value):
    if not value:
        print(f"{name}: NOT PROVIDED")
        return False
    p = Path(value).expanduser()
    if p.is_symlink() or not p.is_file():
        print(f"{name}: NOT VERIFIED (must be a regular file, not a symlink)")
        return False
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        signature = handle.read(8)
        digest.update(signature)
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    size = p.stat().st_size
    size_ok = name not in SIZES or size == SIZES[name]
    magic_ok = name not in MAGIC or signature.startswith(MAGIC[name])
    print(f"{name}: {size} bytes; SHA256={digest.hexdigest()}")
    if name in SIZES:
        print(f"  expected partition size: {'MATCH' if size_ok else 'MISMATCH'}")
        print(f"  raw image signature: {'MATCH' if magic_ok else 'MISMATCH'}")
    print("  Provenance, correct device and restore compatibility: NOT VERIFIED")
    return size_ok and magic_ok

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", help="local raw boot image candidate")
    p.add_argument("--dtbo", help="local raw dtbo image candidate")
    p.add_argument("--firmware", help="local stock firmware package")
    args = p.parse_args()
    print("Stage 17: offline recovery inventory; no ADB, no device operations")
    results = {n: check(n, getattr(args,n)) for n in ("boot", "dtbo", "firmware")}
    print("Candidate file checks:", "PASS" if all(results.values()) else "INCOMPLETE")
    print("BOOT/FLASH SAFETY GATE: BLOCKED (restore has not been tested).")
    print("No files written, no firmware extracted; keep backups private.")

if __name__ == "__main__":
    main()
