#!/usr/bin/env python3
"""Stage 46D: offline PIT / backup recovery feasibility audit.

Reads the Heimdall print-pit TEXT already saved on the owner's Mac and
the owner's private BOOT/DTBO backups. No ADB, USB, Download Mode,
Heimdall commands, partition writes, image creation, or reboot.

This is a geometry/provenance audit; it DOES NOT prove non-wiping
restoration, bootloader acceptance, or a working recovery procedure.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys

HOME = Path.home()
EXPECTED = {
    "BOOT": (15104, 27792, 61865984, "boot.img",
             "a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372"),
    "DTBO": (2048, 25728, 8388608, "dtbo.img",
             "6bd251a32cae12f07ba3918d7d34fffe1a14290ce2c578b68a623aabd557c946"),
}
REQUIRED = {"BOOT", "DTBO", "RECOVERY", "VBMETA", "VBMETA_SAMSUNG",
            "SUPER", "USERDATA", "PIT"}
FIELD = re.compile(r"^([^:]+):\s*(.*)$")
ENTRY = re.compile(r"^--- Entry #(\d+) ---$")
MAX_PIT_BYTES = 500_000

def parse_pit(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PIT_BYTES:
        raise ValueError("PIT must be a local regular text file under 500 kB")
    raw = path.read_text(encoding="utf-8")
    entries, current = [], None
    for line in raw.splitlines():
        match = ENTRY.fullmatch(line.strip())
        if match:
            if current is not None:
                entries.append(current)
            current = {"entry": int(match.group(1))}
        elif current is not None:
            field = FIELD.match(line.strip())
            if field:
                current[field.group(1)] = field.group(2)
    if current is not None:
        entries.append(current)
    if "PIT file download successful." not in raw:
        raise ValueError("The supplied text does not report a successful PIT retrieval")
    return entries

def fingerprint(path, expected_size, expected_sha):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected_size:
        return False
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest() == expected_sha

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pit", type=Path,
                    default=HOME / "Downloads/t575-pit-inspection.txt")
    ap.add_argument("--backups", type=Path,
                    default=HOME / "Downloads/SM-T575-Recovery")
    args = ap.parse_args()
    try:
        entries = parse_pit(args.pit.expanduser())
    except (OSError, ValueError) as exc:
        print("Stage 46D: PIT inspection unavailable:", str(exc))
        return 2
    print("Stage 46D — offline PIT geometry and restore-risk audit")
    print("  Heimdall session: recorded successful PIT retrieval")
    print("  Parsed PIT entries:", len(entries))
    by_name = {}
    for item in entries:
        name = item.get("Partition Name", "")
        if name in by_name:
            print("  FAIL: duplicate partition entry name", name)
            return 1
        if name:
            by_name[name] = item
    ok = len(entries) == 39 and REQUIRED.issubset(by_name)
    print("  Expected 39 entries and safety-critical partitions:",
          "PASS" if ok else "REVIEW")
    for name, (expected_blocks, expected_offset, expected_size, flash_name, sha) in EXPECTED.items():
        item = by_name.get(name, {})
        try:
            offset = int(item.get("Partition Block Size/Offset", "-1"))
            blocks = int(item.get("Partition Block Count", "-1"))
            identifier = int(item.get("Identifier", "-1"))
        except ValueError:
            offset, blocks, identifier = -1, -1, -1
        # Infer logical block size solely from backup size and recorded count.
        inferred = expected_size // blocks if blocks > 0 and expected_size % blocks == 0 else 0
        valid = (inferred == 4096 and blocks == expected_blocks and
                 offset == expected_offset and
                 item.get("Flash Filename") == flash_name and
                 item.get("Attributes") == "5 (Read/Write)" and
                 item.get("Device Type") == "8 (UFS)")
        backup = args.backups.expanduser() / ("boot-current.img" if name == "BOOT"
                                               else "dtbo-current.img")
        hash_ok = fingerprint(backup, expected_size, sha)
        ok &= valid and hash_ok
        print(f"  {name}: PIT geometry {'PASS' if valid else 'REVIEW'}, "
              f"backup fingerprint {'PASS' if hash_ok else 'REVIEW'}")
        if valid:
            print(f"    PIT identifier {identifier}; offset {offset}; "
                  f"{blocks} blocks x {inferred} bytes = {blocks * inferred} bytes")
    boot = by_name.get("BOOT", {})
    dtbo = by_name.get("DTBO", {})
    if all(k in boot for k in ("Partition Block Size/Offset", "Partition Block Count")) and all(
        k in dtbo for k in ("Partition Block Size/Offset", "Partition Block Count")
    ):
        try:
            bstart = int(boot["Partition Block Size/Offset"])
            bend = bstart + int(boot["Partition Block Count"])
            dstart = int(dtbo["Partition Block Size/Offset"])
            dend = dstart + int(dtbo["Partition Block Count"])
            separate = (bend <= dstart or dend <= bstart)
        except ValueError:
            separate = False
        print("  BOOT and DTBO do not overlap:", "PASS" if separate else "REVIEW")
        ok &= separate
    else:
        ok = False
    print("  Sensitive partitions: USERDATA, EFS, SEC_EFS, SUPER, VBMETA")
    print("  No changes to any partitions are authorized by this result.")
    print("  Model/CSC/anti-rollback, AVB and transport write behavior: NOT PROVEN")
    print("  Original Android bootability after a restore: NOT PROVEN")
    print("  Verified non-wiping restore: NOT PROVEN")
    print("  Result:", "PASS — offline consistency only" if ok else "REVIEW REQUIRED")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
