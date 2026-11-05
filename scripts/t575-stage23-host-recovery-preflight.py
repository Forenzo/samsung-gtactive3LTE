#!/usr/bin/env python3
"""Stage 23: read-only macOS restore-tool and backup readiness report.

No ADB, Download-mode, flashing, USB access, files written or network calls.
Reports prerequisites, NEVER authorizes an experimental Linux boot.
"""
import argparse
import hashlib
import platform
import shutil
import subprocess
from pathlib import Path

FILES = {
    "boot-current.img": (61865984, "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"),
    "dtbo-current.img": (8388608, "6bd251a32cae12f07ba3918d7d34fffe1a14290ce2c578b68a623aabd557c946"),
}

def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "SM-T575-Recovery")
    args = ap.parse_args()
    print("Stage 23 — OFFLINE host recovery-readiness preflight")
    print(f"  Host OS: {platform.system()} {platform.machine()}")
    for tool in ("adb", "heimdall"):
        exe = shutil.which(tool)
        print(f"  {tool}: {'FOUND' if exe else 'NOT FOUND'}")
        if exe and tool == "heimdall":
            try:
                proc = subprocess.run([exe, "version"], capture_output=True, text=True, timeout=10)
                # Only report short version output; no device enumeration.
                lines = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
                print("    version: " + (lines[0][:160] if lines else "(not reported)"))
            except (OSError, subprocess.TimeoutExpired):
                print("    version: unavailable")
    folder = args.folder.expanduser()
    valid = True
    for name, (size, expected_hash) in FILES.items():
        path = folder / name
        if path.is_symlink() or not path.is_file():
            print(f"  {name}: MISSING OR SYMLINKED")
            valid = False
            continue
        good = path.stat().st_size == size and checksum(path) == expected_hash
        valid = valid and good
        print(f"  {name}: {'SIZE/HASH MATCH' if good else 'MISMATCH'}")
    print(f"  Private local backup integrity: {'PASS' if valid else 'NOT VERIFIED'}")
    print("  Download-mode handshake: NOT TESTED")
    print("  Non-wiping BOOT/DTBO restoration: NOT TESTED")
    print("  Matching original Samsung firmware: NOT VERIFIED")
    print("  Actual bootloader unlock state: NOT RECHECKED")
    print("  S-Boot display handover: NOT VERIFIED")
    print("  BOOT TEST / FLASH GATE: BLOCKED")
    print("No device operations or changes were made.")

if __name__ == "__main__":
    main()
