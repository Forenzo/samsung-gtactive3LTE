#!/usr/bin/env python3
"""Stage 39: offline structural audit of UAIF1 TAS2562 DAI linkage."""
import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import struct
import sys

here = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader("stage38", str(here / "t575-stage38-audio-phandle-references.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
stage38 = importlib.util.module_from_spec(spec)
loader.exec_module(stage38)

def main():
    exe = shutil.which("fdtoverlay")
    if exe is None:
        print("Install dtc for fdtoverlay")
        return 2
    base, overlay = stage38.merge_mod.dt.load(Path.home() / "Downloads" / "SM-T575-Recovery", 5)
    nodes = stage38.parse(stage38.merge_mod.merge(base, overlay, exe))
    codec = nodes.get("/hsi2c@108C0000/tas2562@4c")
    link = nodes.get("/sound/uaif@1/codec")
    parent = nodes.get("/sound/uaif@1")
    print("Stage 39: UAIF1 to TAS2562 offline DAI reference")
    if codec is None or link is None or parent is None:
        print("Missing codec or UAIF1 nodes")
        return 2
    handle = codec.get("phandle", codec.get("linux,phandle"))
    dai = link.get("sound-dai")
    if handle is None or len(handle) != 4 or dai is None or len(dai) != 8:
        print("Unexpected sound-dai tuple geometry; review required")
        return 2
    valid = handle == dai[:4]
    index = struct.unpack_from(">I", dai, 4)[0]
    print("TAS2562 phandle match:", "YES" if valid else "NO")
    print("DAI specifier cells: 1")
    print("DAI index:", index)
    print("UAIF1 parent: present")
    print("No guarantee of Linux ABOX/ASoC support or usable audio.")
    print("No device, source DTS, or backups modified.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if valid else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, struct.error):
        print("Stage 39 failed offline validation", file=sys.stderr)
        sys.exit(1)
