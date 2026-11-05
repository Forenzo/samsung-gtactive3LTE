#!/usr/bin/env python3
"""Stage 11: compile-only simpledrm configuration and LTE DT handover gate.

This checks a generated kernel .config and a compiled Linux DTB. It cannot
confirm S-Boot scanout, DECON register state, a visible screen or boot safety.
"""
import runpy
import struct
import sys
from pathlib import Path

FRAME = "/chosen/framebuffer-0"
REGION = "/reserved-memory/framebuffer@ca000000"
DECON = "/soc@0/display-controller@16030000"
PANEL = "/panel"

def propstr(data):
    return (data or b"").split(b"\0", 1)[0].decode("ascii", "replace")

def u32(data):
    return [v[0] for v in struct.iter_unpack(">I", data)] if data and len(data) % 4 == 0 else []

def audit(config_path, dtb_path):
    config = Path(config_path).read_text()
    options = dict(line.strip().split("=", 1) for line in config.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    errors = []
    for key in ("CONFIG_DRM", "CONFIG_DRM_SIMPLEDRM"):
        value = options.get(key, "n")
        print(f"  {key}={value}")
        if value != "y":
            errors.append(f"{key} must be built into the test kernel (not a module)")
    if options.get("CONFIG_FB_SIMPLE") == "y":
        errors.append("legacy simplefb also built in: review framebuffer driver ownership")

    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(dtb_path)
    frame = nodes.get(FRAME)
    region = nodes.get(REGION)
    if frame is None or region is None:
        errors.append("framebuffer node or reservation missing")
    else:
        if b"simple-framebuffer" not in frame.get("compatible", b"").split(b"\0"):
            errors.append("missing simple-framebuffer compatible")
        if propstr(frame.get("status")) == "disabled":
            errors.append("simple-framebuffer node disabled")
        for name, expected in (("width", 1200), ("height", 1920), ("stride", 4800)):
            if u32(frame.get(name)) != [expected]:
                errors.append(f"framebuffer {name} differs from audited value {expected}")
        if propstr(frame.get("format")) != "x8r8g8b8":
            errors.append("framebuffer pixel format changed; audit driver compatibility")
        if not frame.get("memory-region"):
            errors.append("missing framebuffer memory-region phandle")
        # Full reservation must stay larger than scanout's 9,216,000 bytes.
        region_reg = u32(region.get("reg"))
        if region_reg != [0, 0xca000000, 0x01400000]:
            errors.append(f"unexpected framebuffer reservation: {region_reg}")
        print("  framebuffer: 1200x1920, stride 4800, x8r8g8b8")
        print("  fixed reserved-memory: 0xca000000 + 0x01400000")
    for path in (DECON, PANEL):
        node = nodes.get(path)
        status = propstr(node.get("status")) if node else "(missing)"
        print(f"  {path}: {status}")
        if status != "disabled":
            errors.append(f"{path} must remain disabled")
    print("  NOT CHECKED: S-Boot scanout, pixel visibility, DMA mapping, clock ownership")
    for issue in errors:
        print(f"ERROR: {issue}", file=sys.stderr)
    if errors:
        return 1
    print("PASS: Stage 11 simpledrm test configuration and static T575 DT gate.")
    print("NOT boot-tested, not a flashable image. Keep Android untouched.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: audit-t575-simpledrm.py kernel/.config compiled-t575.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(audit(sys.argv[1], sys.argv[2]))
    except (OSError, ValueError, KeyError, struct.error) as exc:
        print(f"Stage 11 audit failure: {exc}", file=sys.stderr)
        sys.exit(1)
