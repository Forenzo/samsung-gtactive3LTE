#!/usr/bin/env python3
"""Stage 25: offline BOOT embedded DTB and selected DTBO structural audit.

Reads only the private local images and prints non-identifying FDT metadata.
No ADB, writes, extracted files, device identifiers or flashing.
Index 5 is a previously observed Android boot argument, not freshly verified.
"""
import argparse
import io
from pathlib import Path
import struct
import sys

FDT_MAGIC = 0xD00DFEED
DTBO_MAGIC = 0xD7B7AB1E

def le32(b, offset):
    return struct.unpack_from("<I", b, offset)[0]

def align(value, page):
    return (value + page - 1) // page * page

def fdt_header(handle, offset, limit, label):
    handle.seek(offset)
    data = handle.read(40)
    if len(data) != 40:
        raise ValueError(f"{label}: incomplete FDT header")
    (magic, total, off_struct, off_strings, off_reserve, version,
     last_comp, boot_cpuid, strings_size, struct_size) = struct.unpack(">10I", data)
    if magic != FDT_MAGIC:
        raise ValueError(f"{label}: missing FDT magic")
    if not 40 <= total <= limit:
        raise ValueError(f"{label}: FDT size {total} outside containing segment {limit}")
    if off_reserve < 40 or off_reserve + 16 > total:
        raise ValueError(f"{label}: bad reserve map offset")
    if off_struct < 40 or off_struct + struct_size > total:
        raise ValueError(f"{label}: structure block out of bounds")
    if off_strings < 40 or off_strings + strings_size > total:
        raise ValueError(f"{label}: string block out of bounds")
    if not 16 <= version <= 17 or last_comp > version:
        raise ValueError(f"{label}: unexpected FDT version {version}")
    print(f"  {label}: FDT v{version}, total={total}, "
          f"struct={struct_size}, strings={strings_size} (bounds OK)")

def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.name}: no regular image file")
    return path.stat().st_size

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path,
                        default=Path.home() / "Downloads" / "SM-T575-Recovery")
    parser.add_argument("--overlay", type=int, default=5,
                        help="selected index previously observed in Android (default: 5)")
    args = parser.parse_args()
    folder = args.folder.expanduser()
    boot = folder / "boot-current.img"
    dtbo = folder / "dtbo-current.img"
    if regular(boot) != 61_865_984 or regular(dtbo) != 8_388_608:
        raise ValueError("unexpected BOOT/DTBO partition image sizes")
    print("Stage 25: OFFLINE device-tree structure audit")
    with boot.open("rb") as handle:
        header = handle.read(2048)
        if header[:8] != b"ANDROID!":
            raise ValueError("BOOT missing Android magic")
        page, version = le32(header, 36), le32(header, 40)
        if (page, version) != (2048, 2):
            raise ValueError("BOOT not v2/2048")
        kernel, ramdisk, second, recovery, dtb = (le32(header, x)
                                                  for x in (8, 16, 24, 1632, 1648))
        offset = page
        for length in (kernel, ramdisk, second, recovery):
            offset += align(length, page)
        if not dtb or offset + dtb > boot.stat().st_size:
            raise ValueError("BOOT embedded DTB outside image bounds")
        print(f"  embedded BOOT DTB segment: offset={offset}, length={dtb}")
        handle.seek(offset)
        payload = handle.read(dtb)
        print(f"  BOOT DTB segment prefix (hex): {payload[:16].hex()}")
        # A BOOT v2 DTB segment may be vendor-packaged rather than a
        # single raw FDT. Locate and validate candidates without exporting
        # the proprietary DT data or presuming a format.
        marker = bytes.fromhex("d00dfeed")
        found = []
        cursor = 0
        while True:
            relative = payload.find(marker, cursor)
            if relative < 0:
                break
            cursor = relative + 4
            try:
                fdt_header(io.BytesIO(payload), relative, len(payload) - relative,
                           f"BOOT FDT candidate at segment offset {relative}")
                found.append(relative)
            except ValueError:
                continue
        if not found:
            print("  BOOT segment is NOT a validated raw FDT or located FDT sequence.")
            print("  This does not imply the byte-matched Android BOOT backup is corrupt.")
        else:
            print(f"  validated embedded FDT offsets: {found}")
    with dtbo.open("rb") as handle:
        b = handle.read(32)
        if len(b) != 32:
            raise ValueError("DTBO table header truncated")
        magic, total, header_size, entry_size, count, entries_offset, page, version = struct.unpack(">8I", b)
        if magic != DTBO_MAGIC or not (32 <= header_size <= total <= 8_388_608):
            raise ValueError("invalid DTBO table")
        if entry_size < 32 or entry_size > 256 or count == 0 or count > 256:
            raise ValueError("unreasonable DTBO entry geometry")
        if entries_offset < header_size or entries_offset + count * entry_size > total:
            raise ValueError("DTBO table entries out of bounds")
        if not 0 <= args.overlay < count:
            raise ValueError(f"selected overlay {args.overlay} out of range 0..{count - 1}")
        handle.seek(entries_offset + args.overlay * entry_size)
        entry = handle.read(entry_size)
        length, offset = struct.unpack_from(">II", entry)
        if length < 40 or offset < header_size or offset + length > total:
            raise ValueError("selected overlay payload out of bounds")
        print(f"  selected DTBO index (historical): {args.overlay}/{count - 1}")
        print(f"  DTBO payload: offset={offset}, length={length}")
        fdt_header(handle, offset, length, "selected overlay FDT")
    if not found:
        print("PARTIAL: selected DTBO validates, BOOT DTB packaging remains unresolved.")
    else:
        print("PASS: BOOT FDT candidates and selected DTBO structurally validated.")
    print("UNVERIFIED: correct revision, actual Android overlay selection, merged DT, boot restoration.")
    print("NO BOOT/FLASH APPROVAL. No file changes or device access.")
    return 0 if found else 2

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 25 FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
