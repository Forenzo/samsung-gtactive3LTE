#!/usr/bin/env python3
"""Stage 37 — offline whitelist-only TAS2562 compatible, I2C address and parent audit.

Based on private, previously validated BOOT+DTBO index 5. Prints only
match verdicts and bounded status strings. Does not expose any other
compatible strings, vendor property contents, unique IDs or blobs.
Never contacts tablet, modifies backups or enables audio.
"""
from pathlib import Path
import importlib.machinery
import importlib.util
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader("stage30", str(HERE / "t575-stage30-merged-hardware-and-runtime-index.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
merge_mod = importlib.util.module_from_spec(spec)
loader.exec_module(merge_mod)

TARGET = "/hsi2c@108C0000/tas2562@4c"
PARENT = "/hsi2c@108C0000"
WHITELIST = {"compatible", "reg", "status", "#sound-dai-cells",
             "pinctrl-0", "pinctrl-names", "interrupts",
             "interrupts-extended", "reset-gpios", "shutdown-gpios"}

def u32(b, off):
    return struct.unpack_from(">I", b, off)[0]

def fdt_properties(blob):
    if len(blob) < 40 or u32(blob, 0) != 0xd00dfeed:
        raise ValueError("FDT header invalid")
    total, struct_off, strings_off, reserve_off, version, last, cpu, slen, length = struct.unpack_from(">9I", blob, 4)
    if total > len(blob) or struct_off < 40 or struct_off + length > total or strings_off + slen > total:
        raise ValueError("FDT blocks out of bounds")
    strings = blob[strings_off:strings_off + slen]
    pos, end = struct_off, struct_off + length
    stack, records, tokens = [], {TARGET: {}, PARENT: {}}, 0
    while pos + 4 <= end:
        token = u32(blob, pos); pos += 4; tokens += 1
        if tokens > 300000:
            raise ValueError("too many FDT tokens")
        if token == 1:
            zero = blob.find(b"\0", pos, end)
            if zero < 0 or zero - pos > 128:
                raise ValueError("bad node name")
            stack.append(blob[pos:zero].decode("ascii", "replace"))
            pos = (zero + 4) & ~3
            if len(stack) > 64: raise ValueError("nesting too deep")
        elif token == 2:
            if not stack: raise ValueError("unbalanced FDT")
            stack.pop()
        elif token == 3:
            if not stack or pos + 8 > end: raise ValueError("truncated FDT property")
            size, keyoff = struct.unpack_from(">II", blob, pos); pos += 8
            if keyoff >= len(strings) or size > end - pos:
                raise ValueError("property outside FDT bounds")
            zero = strings.find(b"\0", keyoff)
            if zero < 0: raise ValueError("bad property name")
            key = strings[keyoff:zero].decode("ascii", "replace")
            path = "/" + "/".join(x for x in stack if x)
            if path in records and key in WHITELIST:
                records[path][key] = blob[pos:pos+size]
            pos = (pos + size + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            if stack: raise ValueError("unclosed FDT node")
            return records
        else:
            raise ValueError("unknown FDT token")
    raise ValueError("missing FDT end token")

def status(props):
    if "status" not in props: return "(implicit)"
    v = props["status"].split(b"\0", 1)[0]
    return v.decode("ascii") if v in (b"okay", b"ok", b"disabled") else "(other)"

def main():
    fdtoverlay = shutil.which("fdtoverlay")
    if not fdtoverlay:
        print("Missing fdtoverlay; install dtc")
        return 2
    base, overlay = merge_mod.dt.load(Path.home() / "Downloads" / "SM-T575-Recovery", 5)
    merged = merge_mod.merge(base, overlay, fdtoverlay)
    props = fdt_properties(merged)
    codec, parent = props[TARGET], props[PARENT]
    compatible = codec.get("compatible", b"").split(b"\0")
    reg = codec.get("reg", b"")
    dai = codec.get("#sound-dai-cells", b"")
    print("Stage 37 — read-only TAS2562 I2C and compatible inventory")
    print("  codec node:", "FOUND" if codec else "NOT FOUND")
    print("  compatible includes ti,tas2562:", "YES" if b"ti,tas2562" in compatible else "NO")
    print("  I2C child reg first cell 0x4c:",
          "YES" if len(reg) >= 4 and u32(reg, 0) == 0x4c else "NOT VERIFIED")
    print("  #sound-dai-cells = 1:",
          "YES" if len(dai) == 4 and u32(dai, 0) == 1 else "NO/UNKNOWN")
    print("  codec status:", status(codec))
    print("  parent I2C node:", "FOUND" if parent else "NOT FOUND")
    print("  parent I2C status:", status(parent))
    for key in ("interrupts", "interrupts-extended", "reset-gpios", "shutdown-gpios"):
        print(f"  {key}: {'PRESENT' if key in codec else 'ABSENT'}")
    print("  note: no explicit properties does not rule out vendor-controlled reset/supplies")
    print("  note: this checks metadata only, not kernel DT binding or board sound-card routing")
    print("  private FDTs discarded; RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, struct.error) as err:
        print(f"Stage 37 STOPPED: {type(err).__name__}", file=sys.stderr)
        sys.exit(1)
