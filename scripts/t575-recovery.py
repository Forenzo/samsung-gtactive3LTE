#!/usr/bin/env python3
"""SM-T575 recovery controller, Stage 46E: OFFLINE verification only.

Commands:
  verify   Validate the exact saved Android BOOT/DTBO and Heimdall PIT.
  prepare  Also inspect a proposed BOOT payload against the known partition.

This utility deliberately contains NO flash, restore, ADB, reboot, USB or
Heimdall execution functionality. A PASS does NOT authorize device writes.
Keep the SM-T570 setup.sh installer away from this LTE device.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import sys

BOOT_SHA = "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"
DTBO_SHA = "6bd251a32cae12f07ba3918d7d34fffe1a14290ce2c578b68a623aabd557c946"
EXPECTED = {
    "BOOT": {"offset": 27792, "blocks": 15104, "size": 61865984, "id": 12,
             "filename": "boot.img", "backup": "boot-current.img", "sha": BOOT_SHA},
    "DTBO": {"offset": 25728, "blocks": 2048, "size": 8388608, "id": 10,
             "filename": "dtbo.img", "backup": "dtbo-current.img", "sha": DTBO_SHA},
}
GUARDED = {"PIT", "BOOTLOADER", "BOOTLOADER2", "EFS", "SEC_EFS",
           "RECOVERY", "VBMETA", "VBMETA_SAMSUNG", "SUPER", "USERDATA"}
PIT_ENTRY = re.compile(r"^--- Entry #(\d+) ---$")

def safe_file(path, max_size=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.name}: missing regular file or symlink")
    if max_size is not None and path.stat().st_size > max_size:
        raise ValueError(f"{path.name}: exceeds allowed input size")
    return path

def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()

def parse_pit(path):
    data = safe_file(path, 500_000).read_text(encoding="utf-8")
    if "PIT file download successful." not in data or "Entry Count: 39" not in data:
        raise ValueError("PIT report is not the expected successful 39-entry dump")
    entries, current = [], None
    for raw in data.splitlines():
        line = raw.strip()
        m = PIT_ENTRY.fullmatch(line)
        if m:
            if current is not None:
                entries.append(current)
            current = {"index": int(m.group(1))}
        elif current is not None and ": " in line:
            key, val = line.split(": ", 1)
            current[key] = val
    if current is not None:
        entries.append(current)
    result = {}
    for entry in entries:
        name = entry.get("Partition Name")
        if not name or name in result:
            raise ValueError("PIT has missing or duplicate partition names")
        result[name] = entry
    if len(entries) != 39 or not GUARDED.issubset(result):
        raise ValueError("PIT partition inventory unexpected")
    return result

def verify(args):
    pit = parse_pit(args.pit.expanduser())
    regions = []
    for name, spec in EXPECTED.items():
        entry = pit.get(name, {})
        for key, value in (("Partition Block Size/Offset", spec["offset"]),
                           ("Partition Block Count", spec["blocks"]),
                           ("Identifier", spec["id"])):
            if entry.get(key) != str(value):
                raise ValueError(f"{name}: unexpected PIT {key}")
        if (entry.get("Flash Filename") != spec["filename"] or
            entry.get("Device Type") != "8 (UFS)" or
            entry.get("Attributes") != "5 (Read/Write)"):
            raise ValueError(f"{name}: unexpected PIT device/filename/attributes")
        start, end = spec["offset"], spec["offset"] + spec["blocks"]
        regions.append((start, end, name))
        backup = safe_file(args.backups.expanduser() / spec["backup"])
        if backup.stat().st_size != spec["size"] or checksum(backup) != spec["sha"]:
            raise ValueError(f"{name}: backup differs from trusted fingerprint")
        print(f"  {name}: partition mapping and trusted backup PASS "
              f"({spec['size']} bytes)")
    regions.sort()
    if regions[0][1] > regions[1][0]:
        raise ValueError("BOOT and DTBO overlap")
    print("  BOOT/DTBO: separate UFS regions PASS")
    print("  PIT protected-partition inventory: PASS")
    return True

def inspect_candidate(path):
    candidate = safe_file(path)
    size = candidate.stat().st_size
    max_size = EXPECTED["BOOT"]["size"]
    if not (2048 <= size <= max_size):
        raise ValueError(f"Candidate length {size} bytes outside BOOT partition bounds")
    with candidate.open("rb") as f:
        header = f.read(2048)
    if len(header) < 1660 or header[:8] != b"ANDROID!":
        raise ValueError("Candidate has no Android BOOT v2 header; other boot formats require separate review")
    kernel_size, ramdisk_size, page_size, version = (
        struct.unpack_from("<I", header, x)[0] for x in (8, 16, 36, 40))
    header_size = struct.unpack_from("<I", header, 1644)[0]
    if (version != 2 or page_size != 2048 or
        not (1660 <= header_size <= page_size) or
        not kernel_size):
        raise ValueError("Candidate BOOT header differs from expected v2/2048 layout")
    def aligned(n):
        return (n + page_size - 1) // page_size * page_size
    second_size = struct.unpack_from("<I", header, 24)[0]
    recovery_dtbo = struct.unpack_from("<I", header, 1632)[0]
    dtb_size = struct.unpack_from("<I", header, 1648)[0]
    total = page_size + sum(aligned(n) for n in
                           (kernel_size, ramdisk_size, second_size, recovery_dtbo, dtb_size))
    if total > size:
        raise ValueError("Candidate BOOT segments extend beyond file length")
    print(f"  Candidate: Android BOOT v2, {size} bytes, kernel {kernel_size}, "
          f"ramdisk {ramdisk_size}, DTB {dtb_size}")
    print(f"  Candidate SHA-256: {checksum(candidate)}")
    print("  Candidate structure: PASS (bootability and S-Boot handover NOT tested)")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("verify", "prepare"))
    ap.add_argument("--backups", type=Path,
                    default=Path.home() / "Downloads/SM-T575-Recovery")
    ap.add_argument("--pit", type=Path,
                    default=Path.home() / "Downloads/t575-pit-inspection.txt")
    ap.add_argument("--candidate", type=Path, help="Local proposed BOOT image for prepare")
    args = ap.parse_args()
    print("SM-T575 recovery controller — offline/read-only")
    try:
        verify(args)
        if args.command == "prepare":
            if args.candidate is None:
                raise ValueError("prepare requires --candidate FILE")
            inspect_candidate(args.candidate.expanduser())
        elif args.candidate:
            raise ValueError("--candidate is only permitted with prepare")
        print("  OFFLINE PREFLIGHT: PASS")
        rc = 0
    except (ValueError, OSError, UnicodeError, struct.error) as exc:
        print("  OFFLINE PREFLIGHT: FAIL —", exc, file=sys.stderr)
        rc = 1
    print("  Non-wiping restore: NOT demonstrated")
    print("  Bootloader acceptance / handover: NOT demonstrated")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return rc

if __name__ == "__main__":
    sys.exit(main())
