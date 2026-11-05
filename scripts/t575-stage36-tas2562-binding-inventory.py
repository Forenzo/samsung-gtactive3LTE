#!/usr/bin/env python3
"""Stage 36: inspect offline merged SM-T575 TAS2562 property NAMES only.

Cross-check against the upstream Linux TAS2562 binding without assuming
Samsung's vendor properties are compatible. Private DTB remains temporary.
No ADB, hardware access, changes to DTS, or flashing.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader(
    "stage30", str(HERE / "t575-stage30-merged-hardware-and-runtime-index.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

KEYS = ("compatible", "reg", "status", "ti,imon-slot-no",
        "interrupt-parent", "interrupts", "interrupts-extended",
        "shut-down", "shutdown-gpios", "reset-gpios",
        "vdd-supply", "dvdd-supply", "pvdd-supply",
        "pinctrl-0", "pinctrl-names", "#sound-dai-cells")
TARGET = "/hsi2c@108C0000/tas2562@4c"

def u32(buf, pos):
    return struct.unpack_from(">I", buf, pos)[0]

def scan(blob):
    if len(blob) < 40 or u32(blob, 0) != 0xd00dfeed:
        raise ValueError("invalid merged FDT magic")
    (total, struct_off, strings_off, reserve_off, ver, last, boot_cpu,
     strings_len, struct_len) = struct.unpack_from(">9I", blob, 4)
    if (total > len(blob) or struct_off < 40 or struct_off + struct_len > total
            or strings_off < 40 or strings_off + strings_len > total):
        raise ValueError("invalid FDT segment bounds")
    strings = blob[strings_off:strings_off + strings_len]
    pos, end = struct_off, struct_off + struct_len
    stack, node_found, found, count = [], False, {}, 0
    while pos + 4 <= end:
        token = u32(blob, pos)
        pos += 4
        count += 1
        if count > 300000:
            raise ValueError("too many FDT tokens")
        if token == 1:
            null = blob.find(b"\x00", pos, end)
            if null < 0 or null - pos > 128:
                raise ValueError("invalid node name")
            name = blob[pos:null].decode("ascii", "replace")
            pos = (null + 4) & ~3
            stack.append(name)
            if len(stack) > 64:
                raise ValueError("excessive nesting")
            path = "/" + "/".join(x for x in stack if x)
            if path == TARGET:
                node_found = True
        elif token == 2:
            if not stack:
                raise ValueError("unbalanced FDT")
            stack.pop()
        elif token == 3:
            if pos + 8 > end or not stack:
                raise ValueError("truncated property header")
            size, str_index = struct.unpack_from(">II", blob, pos)
            pos += 8
            if str_index >= len(strings) or size > end - pos:
                raise ValueError("invalid property range")
            str_end = strings.find(b"\x00", str_index)
            if str_end < 0:
                raise ValueError("bad property name")
            key = strings[str_index:str_end].decode("ascii", "replace")
            path = "/" + "/".join(x for x in stack if x)
            if path == TARGET and key in KEYS:
                # Report presence, not vendor property values.
                found[key] = size
            pos = (pos + size + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            if stack:
                raise ValueError("unclosed node")
            break
        else:
            raise ValueError("unrecognized FDT token")
    return node_found, found

def main():
    folder = Path.home() / "Downloads" / "SM-T575-Recovery"
    tool = shutil.which("fdtoverlay")
    if not tool:
        print("Missing fdtoverlay: brew install dtc")
        return 2
    base, overlay = mod.dt.load(folder, 5)
    merged = mod.merge(base, overlay, tool)
    present, props = scan(merged)
    print("Stage 36 — private offline TAS2562 binding-property inventory")
    print("  TAS2562 node found:", "YES" if present else "NO")
    for key in KEYS:
        print(f"  {key}: {'present' if key in props else 'absent'}")
    print("  reg address 0x4c: verified from node name, raw 'reg' not interpreted")
    print("No private property values printed. No changes to backups or Android.")
    print("Linux upstream compatible expected: ti,tas2562 (not yet established here).")
    print("Do NOT enable sound/amplifier until binding, supplies, IRQ and DAI links are mapped.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if present else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"Stage 36 STOPPED: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
