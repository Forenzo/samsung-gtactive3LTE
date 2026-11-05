#!/usr/bin/env python3
"""Stage 27: inspect selected SM-T575 device-tree hardware nodes offline.

Reads saved private BOOT/DTBO backups only. Prints only node counts, generic
hardware category counts and sanitized known device-tree node names/paths.
Does not print property values, identifiers, MAC addresses, serials, blobs,
or create any output files. This is NOT an overlay merge or flashing test.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

MAGIC = 0xD00DFEED
BEGIN, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9
CATEGORIES = {
    "display": re.compile(r"decon|dsi|display|panel|framebuffer|mipi", re.I),
    "touch": re.compile(r"touch|tsp|sec_ts|fts", re.I),
    "audio": re.compile(r"audio|sound|codec|tas2562|rt5510|i2s|abox", re.I),
    "modem": re.compile(r"modem|cpif|cp_ram|lte|shannon", re.I),
}
MAX_NODES = 12000
MAX_TOKENS = 300000

def be32(b, off):
    return struct.unpack_from(">I", b, off)[0]

def le32(b, off):
    return struct.unpack_from("<I", b, off)[0]

def align(v, n):
    return (v + n - 1) // n * n

def load_segment(folder):
    boot, dtbo = folder / "boot-current.img", folder / "dtbo-current.img"
    for path, size in ((boot, 61865984), (dtbo, 8388608)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise ValueError(f"Invalid/missing local image: {path.name}")
    with boot.open("rb") as f:
        head = f.read(2048)
        if head[:8] != b"ANDROID!" or le32(head, 36) != 2048 or le32(head, 40) != 2:
            raise ValueError("Unexpected BOOT format")
        sizes = [le32(head, i) for i in (8, 16, 24, 1632)]
        off = 2048 + sum(align(v, 2048) for v in sizes)
        seg_size = le32(head, 1648)
        if off + seg_size > boot.stat().st_size:
            raise ValueError("BOOT DT segment out of bounds")
        f.seek(off)
        table = f.read(seg_size)
    with dtbo.open("rb") as f:
        overlay_table = f.read(8_388_608)
    return table, overlay_table

def extract(table, index, label):
    if len(table) < 32:
        raise ValueError(f"{label}: short table header")
    magic, total, header, entry_size, count, entoff, page, version = struct.unpack_from(">8I", table)
    if (magic != 0xD7B7AB1E or total > len(table) or not 32 <= header <= total
            or not 32 <= entry_size <= 256 or not 1 <= count <= 64
            or entoff < header or entoff + count * entry_size > total
            or index < 0 or index >= count):
        raise ValueError(f"{label}: invalid Android DT table or index")
    size, off = struct.unpack_from(">II", table, entoff + index * entry_size)
    if size < 40 or off < entoff + count * entry_size or off + size > total:
        raise ValueError(f"{label}: invalid FDT entry")
    return table[off:off + size]

def node_names(blob):
    if len(blob) < 40 or be32(blob, 0) != MAGIC:
        raise ValueError("Invalid FDT magic/header")
    total, struct_off, strings_off, mem_off, ver, last, cpu, strings_len, struct_len = struct.unpack_from(">9I", blob, 4)
    if (total > len(blob) or not 40 <= struct_off <= total
            or struct_off + struct_len > total or strings_off + strings_len > total
            or ver < 16 or ver > 17):
        raise ValueError("Invalid FDT structure bounds")
    pos, end = struct_off, struct_off + struct_len
    depth, token_count, count, matches = [], 0, 0, {k: [] for k in CATEGORIES}
    while pos + 4 <= end:
        token = be32(blob, pos)
        pos += 4
        token_count += 1
        if token_count > MAX_TOKENS:
            raise ValueError("Too many FDT tokens")
        if token == BEGIN:
            null = blob.find(b"\x00", pos, end)
            if null < 0 or null - pos > 256:
                raise ValueError("Malformed FDT node name")
            raw = blob[pos:null]
            name = raw.decode("ascii", "replace")
            pos = align(null + 1, 4)
            depth.append(name)
            count += 1
            if count > MAX_NODES or len(depth) > 64:
                raise ValueError("Too many FDT nodes or excessive depth")
            # Use basename only and allow only conventional node-name glyphs,
            # avoiding node property values entirely.
            if re.fullmatch(r"[a-zA-Z0-9,_+@.\-]{1,100}", name):
                for key, pattern in CATEGORIES.items():
                    if pattern.search(name) and len(matches[key]) < 35:
                        matches[key].append(name)
        elif token == END_NODE:
            if not depth:
                raise ValueError("Unbalanced FDT END_NODE")
            depth.pop()
        elif token == PROP:
            if pos + 8 > end:
                raise ValueError("Truncated FDT property header")
            size, nameoff = struct.unpack_from(">II", blob, pos)
            pos += 8
            if nameoff >= strings_len or pos + size > end:
                raise ValueError("Invalid FDT property bounds")
            pos = align(pos + size, 4)
        elif token == NOP:
            pass
        elif token == END:
            if depth:
                raise ValueError("Unclosed FDT nodes")
            return count, matches
        else:
            raise ValueError(f"Unknown FDT token {token}")
    raise ValueError("Missing FDT_END token")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "SM-T575-Recovery")
    p.add_argument("--overlay", type=int, default=5,
                   help="Historical Android dtbo_idx; not freshly confirmed")
    args = p.parse_args()
    base_table, overlay_table = load_segment(args.folder.expanduser())
    print("Stage 27 — offline hardware node-name inventory")
    for label, blob in (("BOOT base FDT", extract(base_table, 0, "BOOT")),
                        (f"DTBO overlay #{args.overlay}", extract(overlay_table, args.overlay, "DTBO"))):
        count, matches = node_names(blob)
        print(f"{label}: {count} FDT nodes")
        for category, names in matches.items():
            print(f"  {category}: {len(names)} matching node names (max 35 shown)")
            if names:
                print("    " + ", ".join(names))
    print("Node names only; no properties, device IDs, firmware bytes or files exported.")
    print("Overlay NOT applied; hardware functions and display handover NOT verified.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 27 FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
