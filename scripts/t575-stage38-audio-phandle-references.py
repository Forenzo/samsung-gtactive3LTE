#!/usr/bin/env python3
"""Stage 38 — offline TAS2562 phandle references in the merged Samsung audio tree.

Searches for an exact 32-bit cell equal to the codec's phandle in
properties under /sound and ABOX-like nodes, reporting sanitized paths,
property names and hit counts only. A numeric cell match is merely a
candidate, NOT proof of an ASoC DAI connection. No DT bytes or identifiers
are exported. Does not contact Android or modify firmware/DTS.
"""
from pathlib import Path
import importlib.machinery
import importlib.util
import re
import shutil
import struct
import sys

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader("stage30", str(HERE / "t575-stage30-merged-hardware-and-runtime-index.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
merge_mod = importlib.util.module_from_spec(spec)
loader.exec_module(merge_mod)

TARGET = "/hsi2c@108C0000/tas2562@4c"
AUDIO = re.compile(r"^/sound(?:/|$)|/abox(?:@|/)|/audio(?:@|/)|/sound(?:@|/)", re.I)
SAFE_NAME = re.compile(r"^[a-zA-Z0-9,_+@.\-]{0,128}$")
SAFE_PROP = re.compile(r"^[a-zA-Z0-9,#+._\-]{1,96}$")
MAX_TOKENS = 300000

def be32(b, pos):
    return struct.unpack_from(">I", b, pos)[0]

def parse(blob):
    if len(blob) < 40 or be32(blob, 0) != 0xd00dfeed:
        raise ValueError("invalid FDT header")
    total, off, soff, _, ver, _, _, slen, length = struct.unpack_from(">9I", blob, 4)
    if total > len(blob) or off < 40 or off + length > total or soff + slen > total:
        raise ValueError("invalid FDT bounds")
    strings = blob[soff:soff+slen]
    nodes = {}
    stack, end, tokens = [], off+length, 0
    while off+4 <= end:
        tok = be32(blob, off); off += 4; tokens += 1
        if tokens > MAX_TOKENS: raise ValueError("too many FDT tokens")
        if tok == 1:
            zero = blob.find(b"\x00", off, end)
            if zero < 0 or zero-off > 128: raise ValueError("bad FDT node name")
            name = blob[off:zero].decode("ascii", "replace")
            if not SAFE_NAME.fullmatch(name): raise ValueError("nonstandard node name")
            stack.append(name)
            off = (zero + 4) & ~3
            if len(stack) > 64: raise ValueError("excessive FDT depth")
            path = "/" + "/".join(n for n in stack if n)
            nodes[path] = {}
            if len(nodes)>16000: raise ValueError("too many FDT nodes")
        elif tok == 2:
            if not stack: raise ValueError("unbalanced FDT")
            stack.pop()
        elif tok == 3:
            if not stack or off+8 > end: raise ValueError("bad FDT property header")
            size, keyoff = struct.unpack_from(">II", blob, off); off += 8
            if keyoff >= len(strings) or size > end-off:
                raise ValueError("property out of bounds")
            zero = strings.find(b"\x00", keyoff)
            if zero < 0: raise ValueError("unterminated property name")
            key = strings[keyoff:zero].decode("ascii", "replace")
            path = "/" + "/".join(n for n in stack if n)
            # Retain only relevant properties: two codec phandle keys and
            # properties under audio nodes. Never print property byte values.
            if path == TARGET and key in ("phandle", "linux,phandle"):
                nodes[path][key] = blob[off:off+size]
            elif AUDIO.search(path) and SAFE_PROP.fullmatch(key) and size <= 8192:
                nodes[path][key] = blob[off:off+size]
            off = (off+size+3)&~3
        elif tok == 4: continue
        elif tok == 9:
            if stack: raise ValueError("unclosed FDT nodes")
            return nodes
        else: raise ValueError("unknown FDT token")
    raise ValueError("missing FDT_END")

def main():
    exe = shutil.which("fdtoverlay")
    if not exe:
        print("fdtoverlay missing; brew install dtc")
        return 2
    base, overlay = merge_mod.dt.load(Path.home() / "Downloads" / "SM-T575-Recovery", 5)
    nodes = parse(merge_mod.merge(base, overlay, exe))
    codec = nodes.get(TARGET)
    print("Stage 38 — offline TAS2562 audio phandle reference audit")
    if codec is None:
        print("TAS2562 node: NOT FOUND")
        return 1
    raw = codec.get("phandle", codec.get("linux,phandle"))
    if raw is None or len(raw) != 4:
        print("Codec phandle: MISSING/INVALID; cannot trace numeric references")
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 2
    token = raw
    hits = []
    for path, props in nodes.items():
        if not AUDIO.search(path): continue
        for name, value in props.items():
            if len(value) % 4: continue
            cells = [value[i:i+4] for i in range(0,len(value),4)]
            matches = sum(v == token for v in cells)
            if matches:
                hits.append((path, name, matches))
    print("Codec phandle: FOUND (numeric value withheld)")
    print(f"Audio-tree candidate reference properties: {len(hits)}")
    for path, name, count in hits[:32]:
        print(f"  {path} :: {name} [matching cells={count}]")
    if len(hits) > 32: print(f"  ... {len(hits)-32} more candidate properties")
    print("Any numeric match is ONLY a candidate; DAI tuple semantics require separate review.")
    print("No binding, supplies, GPIO or working ASoC route established.")
    print("No images exported; backups and Android untouched.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except (OSError, ValueError, struct.error) as exc:
        print(f"Stage 38 STOPPED: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
