#!/usr/bin/env python3
"""Stage 26: audit the nested Android DT table in a private SM-T575 BOOT backup.

Entirely offline, read-only; validates container/entry/FDT boundaries, not
bootloader selection, overlay compatibility, or flashing/recovery safety.
No device-tree contents or unique hardware identifiers are printed.
"""
import argparse
import struct
import sys
from pathlib import Path

DT_TABLE_MAGIC = 0xd7b7ab1e
FDT_MAGIC = 0xd00dfeed
BOOT_SIZE = 61_865_984
DTBO_SIZE = 8_388_608

def get32(data, offset, endian):
    return struct.unpack_from(endian + "I", data, offset)[0]

def align(x, a):
    return (x + a - 1) // a * a

def table_header(f, offset, max_len, label):
    f.seek(offset)
    buf = f.read(32)
    if len(buf) != 32:
        raise ValueError(f"{label}: short DT table header")
    magic, total, header, entry_size, count, entry_offset, page, version = struct.unpack(">8I", buf)
    if magic != DT_TABLE_MAGIC:
        raise ValueError(f"{label}: unexpected table magic")
    if not (32 <= header <= total <= max_len):
        raise ValueError(f"{label}: invalid total/header size")
    if not (32 <= entry_size <= 256 and 1 <= count <= 64):
        raise ValueError(f"{label}: invalid entry geometry")
    if entry_offset < header or entry_offset + count * entry_size > total:
        raise ValueError(f"{label}: entries out of table range")
    print(f"{label}: total={total}, header={header}, entry_size={entry_size}, "
          f"entries={count}, page={page}, version={version}")
    return total, entry_size, count, entry_offset

def check_fdt(f, absolute, limit, label):
    f.seek(absolute)
    b = f.read(40)
    if len(b) != 40:
        raise ValueError(f"{label}: truncated FDT header")
    magic, size, off_struct, off_strings, off_mem, ver, last, _, strings_len, struct_len = struct.unpack(">10I", b)
    if magic != FDT_MAGIC or not (40 <= size <= limit):
        raise ValueError(f"{label}: invalid FDT magic/size")
    if off_mem < 40 or off_mem + 16 > size:
        raise ValueError(f"{label}: invalid reserve map")
    if off_struct < 40 or off_struct + struct_len > size:
        raise ValueError(f"{label}: invalid structure block")
    if off_strings < 40 or off_strings + strings_len > size:
        raise ValueError(f"{label}: invalid string block")
    if not 16 <= ver <= 17 or last > ver:
        raise ValueError(f"{label}: unexpected FDT version")
    return size

def entries(f, start, max_len, label, selected=None):
    total, entry_size, count, offset = table_header(f, start, max_len, label)
    if selected is not None and not 0 <= selected < count:
        raise ValueError(f"{label}: selected index out of bounds")
    regions = []
    for i in range(count):
        f.seek(start + offset + entry_size * i)
        b = f.read(entry_size)
        if len(b) != entry_size:
            raise ValueError(f"{label}: entry #{i} truncated")
        size, relative = struct.unpack_from(">II", b)
        if size < 40 or relative < offset + count * entry_size or relative + size > total:
            raise ValueError(f"{label}: entry #{i} outside the DT table payload")
        actual = check_fdt(f, start + relative, size, f"{label} FDT #{i}")
        if actual != size:
            raise ValueError(f"{label}: entry #{i} length differs from FDT length")
        regions.append((relative, relative + size))
        print(f"  FDT #{i}: relative offset={relative}, bytes={size}"
              + (" [historically selected]" if i == selected else ""))
    for (a, b), (c, d) in zip(sorted(regions), sorted(regions)[1:]):
        if b > c:
            raise ValueError(f"{label}: overlapping payloads")
    return count

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "SM-T575-Recovery")
    p.add_argument("--overlay", type=int, default=5)
    args = p.parse_args()
    folder = args.folder.expanduser()
    boot, dtbo = folder / "boot-current.img", folder / "dtbo-current.img"
    for path, length in ((boot, BOOT_SIZE), (dtbo, DTBO_SIZE)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size != length:
            raise ValueError(f"{path.name}: invalid file, symlink, or size")
    print("Stage 26 — offline nested DT table validation")
    with boot.open("rb") as f:
        b = f.read(2048)
        if b[:8] != b"ANDROID!" or get32(b, 36, "<") != 2048 or get32(b, 40, "<") != 2:
            raise ValueError("BOOT does not match the observed Android header v2/2048")
        kernel, ramdisk, second, recovery, dt_size = (get32(b, i, "<") for i in (8, 16, 24, 1632, 1648))
        start = 2048 + sum(align(x, 2048) for x in (kernel, ramdisk, second, recovery))
        if start + dt_size > BOOT_SIZE:
            raise ValueError("BOOT DT segment outside partition")
        print(f"BOOT DT segment: partition offset={start}, bytes={dt_size}")
        entries(f, start, dt_size, "BOOT nested DT table")
    with dtbo.open("rb") as f:
        entries(f, 0, DTBO_SIZE, "DTBO overlay table", selected=args.overlay)
    print("PASS: both DT table containers, payload bounds and FDT headers validate.")
    print("No overlays applied; current overlay selection and firmware boot state not proven.")
    print("RESTORE/FLASH GATE: BLOCKED. No device contact, reads of live MMIO, or writes.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 26 FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
