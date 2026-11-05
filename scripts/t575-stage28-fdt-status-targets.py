#!/usr/bin/env python3
"""Stage 28 — offline filtered FDT status and overlay-target inventory.

Reads the two private existing backup images. Reports only category-matched
node paths and exact whitelisted property names: status, target-path,
compatible (compatible values omitted), and target phandle presence.
No serials, MACs, partition bytes, raw DT blobs, files written or ADB.
An overlay must be applied to determine the effective runtime status.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

CATEGORIES = {
    "display": re.compile(r"decon|dsim|dsi|display|panel|hx83102|framebuffer", re.I),
    "touch": re.compile(r"touch|tsp|etspi|sec_ts|fts", re.I),
    "audio": re.compile(r"sound|audio|codec|abox|tas2562|rt5510", re.I),
    "modem": re.compile(r"modem|cp_ram|cpif|lte", re.I),
}
MAX_PRINT = 24

def be32(b, off):
    return struct.unpack_from(">I", b, off)[0]

def le32(b, off):
    return struct.unpack_from("<I", b, off)[0]

def align(x, n):
    return (x + n - 1) // n * n

def dt_entry(table, index, label):
    if len(table) < 32:
        raise ValueError(f"{label}: table too short")
    magic, total, header, ent_size, count, ent_off, page, version = struct.unpack_from(">8I", table)
    if (magic != 0xd7b7ab1e or not 32 <= header <= total <= len(table) or
        not 32 <= ent_size <= 256 or not 1 <= count <= 64 or
        ent_off < header or ent_off + count * ent_size > total or
        not 0 <= index < count):
        raise ValueError(f"{label}: invalid Android DT table")
    size, off = struct.unpack_from(">II", table, ent_off + index * ent_size)
    if size < 40 or off < ent_off + count * ent_size or off + size > total:
        raise ValueError(f"{label}: invalid entry payload bounds")
    return table[off:off + size]

def load(folder, index):
    boot = folder / "boot-current.img"
    overlay = folder / "dtbo-current.img"
    for path, size in ((boot, 61_865_984), (overlay, 8_388_608)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise ValueError(f"{path.name}: missing regular image or size mismatch")
    with boot.open("rb") as f:
        header = f.read(2048)
        if header[:8] != b"ANDROID!" or le32(header, 36) != 2048 or le32(header, 40) != 2:
            raise ValueError("Unexpected BOOT image header")
        base_offset = 2048 + sum(align(le32(header, i), 2048) for i in (8, 16, 24, 1632))
        base_size = le32(header, 1648)
        if base_offset + base_size > 61_865_984:
            raise ValueError("BOOT DT segment exceeds image")
        f.seek(base_offset)
        base_table = f.read(base_size)
    with overlay.open("rb") as f:
        overlay_table = f.read(8_388_608)
    return dt_entry(base_table, 0, "BOOT"), dt_entry(overlay_table, index, "DTBO")

def c_string(b):
    return b.split(b"\x00", 1)[0].decode("ascii", "replace")

def parse(blob):
    if len(blob) < 40 or be32(blob, 0) != 0xd00dfeed:
        raise ValueError("Invalid FDT header")
    total, off_s, off_strings, off_reserve, ver, _, _, strings_len, struct_len = struct.unpack_from(">9I", blob, 4)
    if (total > len(blob) or off_s < 40 or off_s + struct_len > total
            or off_strings + strings_len > total or not 16 <= ver <= 17):
        raise ValueError("Invalid FDT blocks")
    strings = blob[off_strings:off_strings + strings_len]
    result = []
    stack = []
    pos, end = off_s, off_s + struct_len
    tokens = 0
    while pos + 4 <= end:
        token = be32(blob, pos)
        pos += 4
        tokens += 1
        if tokens > 300_000:
            raise ValueError("Unreasonable token count")
        if token == 1:
            stop = blob.find(b"\x00", pos, end)
            if stop < 0 or stop - pos > 256:
                raise ValueError("Invalid node name")
            raw = blob[pos:stop]
            name = raw.decode("ascii", "replace")
            if not re.fullmatch(r"[a-zA-Z0-9,._+@\-]{0,128}", name):
                name = "(nonstandard node name)"
            pos = align(stop + 1, 4)
            stack.append(len(result))
            parent = result[stack[-2]]["path"] if len(stack) > 1 else ""
            path = parent + "/" + name if name else "/"
            result.append({"path": path, "name": name, "props": {}})
            if len(result) > 16000 or len(stack) > 64:
                raise ValueError("Too many nodes")
        elif token == 2:
            if not stack:
                raise ValueError("Unbalanced nodes")
            stack.pop()
        elif token == 3:
            if pos + 8 > end or not stack:
                raise ValueError("Truncated property")
            size, name_off = struct.unpack_from(">II", blob, pos)
            pos += 8
            if name_off >= len(strings) or pos + size > end:
                raise ValueError("Property out of bounds")
            end_name = strings.find(b"\x00", name_off)
            if end_name < 0:
                raise ValueError("Unterminated property name")
            key = strings[name_off:end_name].decode("ascii", "replace")
            # Read only non-sensitive whitelisted *property values*.
            if key in ("status", "target-path"):
                result[stack[-1]]["props"][key] = c_string(blob[pos:pos + min(size, 256)])
            elif key in ("target", "compatible"):
                result[stack[-1]]["props"][key] = "(present)"
            pos = align(pos + size, 4)
        elif token == 4:
            pass
        elif token == 9:
            if stack:
                raise ValueError("Unclosed nodes")
            return result
        else:
            raise ValueError(f"Unexpected FDT token {token}")
    raise ValueError("Missing FDT end marker")

def report(nodes, label):
    print(f"{label}: {len(nodes)} nodes parsed")
    for category, regex in CATEGORIES.items():
        matches = [x for x in nodes if regex.search(x["name"])]
        print(f"  {category}: {len(matches)} matching nodes; showing up to {MAX_PRINT}")
        for node in matches[:MAX_PRINT]:
            status = node["props"].get("status", "(inherited/default)")
            print(f"    {node['path']} [status={status}]")
    fragments = [n for n in nodes if n["name"].startswith("fragment@")]
    if fragments:
        print(f"  overlay fragments: {len(fragments)}")
        for n in fragments[:60]:
            props = n["props"]
            target = props.get("target-path", "phandle target" if "target" in props else "unspecified")
            print(f"    {n['name']}: target={target}")
        if len(fragments) > 60:
            print(f"    ... {len(fragments) - 60} more fragments not shown")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "SM-T575-Recovery")
    parser.add_argument("--overlay", type=int, default=5)
    args = parser.parse_args()
    base, overlay = load(args.folder.expanduser(), args.overlay)
    print("Stage 28 — offline FDT status/overlay-target audit")
    report(parse(base), "BOOT base FDT")
    report(parse(overlay), f"DTBO overlay #{args.overlay} (historical)")
    print("Status is per-tree ONLY; effective merged runtime status NOT established.")
    print("No devices contacted or files modified. RESTORE/BOOT/FLASH GATE: BLOCKED.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 28 FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
