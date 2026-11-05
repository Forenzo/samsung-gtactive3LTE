#!/usr/bin/env python3
"""Stage 24: OFFLINE, read-only SM-T575 BOOT v2 and DTBO table structure audit.

Parses metadata from local backups only. Never uses ADB, writes files,
unpacks firmware, reveals identifiers, or approves flashing.
"""
import argparse
import struct
import sys
from pathlib import Path

BOOT_BYTES = 61865984
DTBO_BYTES = 8388608
DTBO_MAGIC = 0xD7B7AB1E

def le32(data, off):
    return struct.unpack_from("<I", data, off)[0]

def align(value, page):
    return (value + page - 1) // page * page

def read_header(path, count):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.name}: missing regular file or symlink")
    with path.open("rb") as f:
        return f.read(count)

def audit_boot(path):
    errors = []
    file_size = path.stat().st_size
    b = read_header(path, 4096)
    if len(b) < 1660 or b[:8] != b"ANDROID!":
        raise ValueError("BOOT: missing or too short for Android boot header v2")
    kernel, ramdisk, second = le32(b, 8), le32(b, 16), le32(b, 24)
    page, version = le32(b, 36), le32(b, 40)
    recovery_dtbo = le32(b, 1632)
    header_size, dtb = le32(b, 1644), le32(b, 1648)
    print(f"BOOT: {file_size} bytes; Android header v{version}; page size {page}")
    print(f"  kernel={kernel} ramdisk={ramdisk} second={second}")
    print(f"  recovery_dtbo={recovery_dtbo} dtb={dtb} header_size={header_size}")
    if file_size != BOOT_BYTES:
        errors.append("BOOT: wrong partition image size")
    if version != 2 or page != 2048:
        errors.append("BOOT: does not match expected v2/2048 layout")
        return errors
    if not (1660 <= header_size <= page):
        errors.append("BOOT: invalid v2 header_size")
    segments = [
        ("kernel", kernel),
        ("ramdisk", ramdisk),
        ("second", second),
        ("recovery_dtbo", recovery_dtbo),
        ("dtb", dtb),
    ]
    offset = page
    for name, length in segments:
        if length:
            end = offset + length
            print(f"  {name}: offset={offset} end={end}")
            if end > file_size:
                errors.append(f"BOOT: {name} exceeds image size")
            offset = align(end, page)
    if offset > file_size:
        errors.append("BOOT: calculated image layout exceeds partition")
    return errors

def audit_dtbo(path):
    errors = []
    b = read_header(path, 32)
    if len(b) < 32:
        raise ValueError("DTBO: table header too short")
    magic, total, header, entry_size, count, entry_offset, page, version = struct.unpack(">8I", b)
    file_size = path.stat().st_size
    print(f"DTBO: {file_size} bytes; table magic=0x{magic:08x}")
    print(f"  total={total} header={header} entry_size={entry_size} entries={count}")
    print(f"  entry_offset={entry_offset} page_size={page} version={version}")
    if file_size != DTBO_BYTES:
        errors.append("DTBO: partition size mismatch")
    if magic != DTBO_MAGIC:
        errors.append("DTBO: invalid Android DT table magic")
    if not (32 <= header <= total <= file_size):
        errors.append("DTBO: invalid header/total size")
    if not (32 <= entry_size <= 256 and 1 <= count <= 256):
        errors.append("DTBO: invalid entry size/count")
    if entry_offset < header or entry_offset + count * entry_size > total:
        errors.append("DTBO: entry table out of bounds")
    if errors:
        return errors
    with path.open("rb") as f:
        f.seek(entry_offset)
        for n in range(count):
            raw = f.read(entry_size)
            if len(raw) != entry_size:
                errors.append(f"DTBO: entry {n} truncated")
                break
            dt_size, dt_offset = struct.unpack_from(">II", raw)
            print(f"  overlay #{n}: size={dt_size} offset={dt_offset}")
            if not dt_size or dt_offset < header or dt_offset + dt_size > total:
                errors.append(f"DTBO: entry {n} payload outside table")
            else:
                here = f.tell()
                f.seek(dt_offset)
                magic_raw = f.read(4)
                f.seek(here)
                if magic_raw != bytes.fromhex("d00dfeed"):
                    errors.append(f"DTBO: entry {n} is not an FDT blob")
    return errors

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "SM-T575-Recovery")
    args = p.parse_args()
    folder = args.folder.expanduser()
    errors = []
    for name, fn in (("BOOT", audit_boot), ("DTBO", audit_dtbo)):
        try:
            errors.extend(fn(folder / ("boot-current.img" if name == "BOOT" else "dtbo-current.img")))
        except (OSError, ValueError, struct.error) as exc:
            errors.append(f"{name}: {exc}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print("Stage 24 metadata:", "PASS" if not errors else "FAIL")
    print("Provenance and Download-mode non-wiping recovery: NOT TESTED")
    print("BOOT/FLASH GATE: BLOCKED. No device access or file modification.")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
