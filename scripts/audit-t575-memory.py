#!/usr/bin/env python3
"""Audit SM-T575 compile-only DTB reserve nodes, without storing vendor DTB.

This checks the compiled Linux FDT itself, independent of dtc warnings.
It checks direct child /reserved-memory ranges and does not mistake nested
debug subregions for independently overlapping reservations.
"""
import struct
import sys
from pathlib import Path

EXPECTED = {
    "modem@f0000000": (0xF0000000, 0x09200000),
    "modem-log@f9200000": (0xF9200000, 0x02000000),
    "abox@fb200000": (0xFB200000, 0x02800000),
}

def word(data, pos):
    return struct.unpack_from(">I", data, pos)[0]

def parse(path):
    data = Path(path).read_bytes()
    if len(data) < 40 or word(data, 0) != 0xD00DFEED:
        raise ValueError("Not a flattened device-tree blob")
    total, structoff, stroff, _, _, _, _, strsize, structsize = struct.unpack_from(">9I", data, 4)
    if total > len(data) or structoff + structsize > total or stroff + strsize > total:
        raise ValueError("Invalid FDT section bounds")
    names = data[stroff:stroff + strsize]
    stack, nodes = [], {}
    pos = structoff
    while pos < structoff + structsize:
        token = word(data, pos); pos += 4
        if token == 1:
            end = data.index(b"\\0", pos)
            name = data[pos:end].decode()
            pos = (end + 4) & ~3
            stack.append(name)
            nodes["/" + "/".join(x for x in stack if x)] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            size = word(data, pos)
            nameoff = word(data, pos + 4)
            pos += 8
            end = names.index(b"\\0", nameoff)
            key = names[nameoff:end].decode()
            val = data[pos:pos + size]
            pos = (pos + size + 3) & ~3
            nodes["/" + "/".join(x for x in stack if x)][key] = val
        elif token == 4:
            pass
        elif token == 9:
            break
        else:
            raise ValueError(f"Unexpected FDT token {token}")
    return nodes

def ranges(prop, addr_cells, size_cells):
    values = [word(prop, i) for i in range(0, len(prop), 4)]
    step = addr_cells + size_cells
    if not step or len(values) % step:
        raise ValueError("Malformed reg property")
    out = []
    for i in range(0, len(values), step):
        addr = size = 0
        for n in values[i:i + addr_cells]:
            addr = (addr << 32) | n
        for n in values[i + addr_cells:i + step]:
            size = (size << 32) | n
        if size:
            out.append((addr, size))
    return out

def main(dtb):
    nodes = parse(dtb)
    parent = nodes.get("/reserved-memory")
    if not parent:
        raise ValueError("No /reserved-memory node")
    ac = word(parent["#address-cells"], 0)
    sc = word(parent["#size-cells"], 0)
    entries = []
    for path, props in nodes.items():
        if path.startswith("/reserved-memory/") and path.count("/") == 2 and "reg" in props:
            for addr, size in ranges(props["reg"], ac, sc):
                entries.append((addr, addr + size, path, "no-map" in props))
    errors = []
    for node, (addr, size) in EXPECTED.items():
        matches = [v for v in entries if v[2] == "/reserved-memory/" + node]
        if len(matches) != 1 or matches[0][:2] != (addr, addr + size) or not matches[0][3]:
            errors.append(f"{node}: missing/wrong address/size/no-map")
    for i, (a, b, name, _) in enumerate(entries):
        for c, d, other, _ in entries[i + 1:]:
            if a < d and c < b:
                errors.append(f"overlap: {name} and {other} ({max(a,c):#x}-{min(b,d):#x})")
    for a, b, name, nomap in sorted(entries):
        print(f"{a:#014x}-{b:#014x} {name} {'no-map' if nomap else ''}")
    if errors:
        for err in errors:
            print("ERROR:", err, file=sys.stderr)
        return 1
    print("PASS: SM-T575 modem/A-Box carveouts present, no direct-child reserved-memory overlaps")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1]))
    except (IndexError, ValueError, KeyError, OSError, struct.error) as err:
        print(f"Audit failed: {err}", file=sys.stderr)
        sys.exit(1)
