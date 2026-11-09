#!/usr/bin/env python3
"""Stage 46: offline recovery preflight for Samsung SM-T575.

NO adb, Heimdall, Odin, USB probing, writes, flashing or reboots.
The output is advisory; this program MUST NOT unlock any flash/boot gate.
Optionally inspect local stock firmware filenames/archive member names only.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import tarfile
import zipfile

DEFAULT = Path.home() / "Downloads" / "SM-T575-Recovery"
EXPECTED = {
    "boot-current.img": (
        61865984,
        "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372",
    ),
    "dtbo-current.img": (
        8388608,
        "6bd251a32cae12f07ba3918d7d34fffe1a14290ce2c578b68a623aabd557c946",
    ),
}
FIRMWARE_PATTERN = re.compile(r"(?i)^(AP|BL|CP|CSC|HOME_CSC)_T575[A-Z0-9_.+-]*")
BOOT_PATTERN = re.compile(r"(?i)(?:^|/)boot\.img(?:\.lz4)?$")
DTBO_PATTERN = re.compile(r"(?i)(?:^|/)dtbo\.img(?:\.lz4)?$")
MAX_FILES = 80

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def inspect_archive(path):
    """Return only whether AP archive contains boot/dtbo member names."""
    if path.name.lower().endswith((".tar", ".tar.md5")):
        with tarfile.open(path, "r:") as handle:
            members = [m.name for m in handle if m.isfile()]
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as handle:
            members = handle.namelist()
    else:
        return None
    if len(members) > 2000:
        raise ValueError("Unusually large archive member list; inspect manually")
    return bool(any(BOOT_PATTERN.search(n) for n in members)), bool(
        any(DTBO_PATTERN.search(n) for n in members)
    )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT)
    parser.add_argument("--firmware-dir", type=Path,
                        help="Optional local SM-T575 stock package directory; names only")
    args = parser.parse_args()
    print("Stage 46 — SM-T575 offline recovery preflight")
    print("  BOOT and DTBO trusted-backup fingerprints:")
    backups_ok = True
    for name, (size, expected_hash) in EXPECTED.items():
        path = args.backup_dir.expanduser() / name
        if not path.is_file():
            print(f"    {name}: MISSING")
            backups_ok = False
        elif path.stat().st_size != size or digest(path) != expected_hash:
            print(f"    {name}: MISMATCH — DO NOT TREAT AS RESTORE IMAGE")
            backups_ok = False
        else:
            print(f"    {name}: PASS (size + SHA-256 match)")
    print("  Stock firmware availability:")
    firmware_complete = False
    if args.firmware_dir:
        directory = args.firmware_dir.expanduser()
        if not directory.is_dir():
            print("    Supplied firmware folder not found")
        else:
            entries = [p for p in directory.iterdir() if p.is_file()]
            if len(entries) > MAX_FILES:
                print("    Too many files to inventory safely")
                return 2
            types = set()
            ap_archives = []
            for p in entries:
                match = FIRMWARE_PATTERN.match(p.name)
                if match:
                    types.add(match.group(1).upper())
                    if match.group(1).upper() == "AP":
                        ap_archives.append(p)
            for label in ("AP", "BL", "CP", "HOME_CSC"):
                print(f"    {label}: {'FILE FOUND' if label in types else 'NOT FOUND'}")
            firmware_complete = all(t in types for t in ("AP", "BL", "CP", "HOME_CSC"))
            for p in ap_archives[:2]:
                try:
                    result = inspect_archive(p)
                except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError):
                    result = None
                if result is not None:
                    print("    AP archive members: BOOT", "FOUND" if result[0] else "MISSING",
                          "| DTBO", "FOUND" if result[1] else "MISSING")
                    firmware_complete &= all(result)
    else:
        print("    NOT CHECKED — supply --firmware-dir if stock package is available")
    print("  Backup copies:", "VERIFIED" if backups_ok else "UNVERIFIED")
    print("  Firmware package:", "INVENTORIED (not authenticated)" if firmware_complete
          else "NOT YET ESTABLISHED")
    print("  Required before any recovery procedure can be approved:")
    print("    correct SM-T575 firmware region/CSC and bootloader revision;")
    print("    exact restore mapping, anti-rollback and non-wiping behavior;")
    print("    Download Mode transport verification; safe S-Boot handover.")
    print("  This script cannot test a non-wiping restore.")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if backups_ok else 1

if __name__ == "__main__":
    sys.exit(main())
