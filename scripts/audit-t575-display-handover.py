#!/usr/bin/env python3
"""Stage 9 compile-only framebuffer handover sanity and isolation audit.

This checks the *compiled Linux* device tree, not runtime behavior.
No native panel power sequence, flashable image, or stock firmware is used.

The Linux simple-framebuffer binding permits memory-region in place of reg.
See Documentation/devicetree/bindings/display/simple-framebuffer.yaml.
"""
import runpy
import struct
import sys
from pathlib import Path

FRAME = "/chosen/framebuffer-0"
RESERVED = "/reserved-memory/framebuffer@ca000000"
PANEL = "/panel"
DECON = "/soc@0/display-controller@16030000"
BACKLIGHT = "/soc@0/backlight@16080000"

def words(b):
    if b is None or len(b) % 4:
        return []
    return [v[0] for v in struct.iter_unpack(">I", b)]

def string(b):
    if b is None:
        return ""
    return b.split(b"\0")[0].decode("utf-8", "replace")

def audit(path):
    helpers = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))
    nodes = helpers["parse"](path)
    ranges = helpers["ranges"]
    errors = []
    def need(path):
        node = nodes.get(path)
        if node is None:
            errors.append(f"missing node {path}")
            return {}
        return node

    frame, region, panel = need(FRAME), need(RESERVED), need(PANEL)
    decon, backlight = need(DECON), need(BACKLIGHT)
    root = need("/")
    reserved_parent = need("/reserved-memory")

    width = words(frame.get("width"))
    height = words(frame.get("height"))
    stride = words(frame.get("stride"))
    fmt = string(frame.get("format"))
    compat = frame.get("compatible", b"").split(b"\0")
    expected = {"width": (width, [1200]), "height": (height, [1920]),
                "stride": (stride, [4800])}
    print("Stage 9: framebuffer reservation, layout and handover check")
    for label, (got, want) in expected.items():
        print(f"  {label}: {got} expected {want}")
        if got != want:
            errors.append(f"framebuffer {label} differs from inherited 1200x1920x4 layout")
    print(f"  format: {fmt}")
    if fmt != "x8r8g8b8":
        errors.append("unsupported framebuffer pixel layout for expected diagnostic setup")
    if b"simple-framebuffer" not in compat:
        errors.append("missing simple-framebuffer compatible")

    if width and height and stride:
        visible = height[0] * stride[0]
        minline = width[0] * 4
        if stride[0] < minline:
            errors.append("framebuffer stride smaller than width x four bytes")
    else:
        visible = None
    print(f"  visible bytes: {visible}")

    phandles = {}
    for p, attrs in nodes.items():
        ph = words(attrs.get("phandle"))
        if len(ph) == 1:
            if ph[0] in phandles:
                errors.append(f"duplicate FDT phandle {ph[0]:#x}")
            phandles[ph[0]] = p
    ref = words(frame.get("memory-region"))
    target = phandles.get(ref[0]) if len(ref) == 1 else None
    print(f"  framebuffer memory-region target: {target}")
    if target != RESERVED:
        errors.append("framebuffer memory-region does not reference expected reservation")
    if "no-map" not in region:
        errors.append("stock framebuffer reservation must remain no-map")

    ac = words(reserved_parent.get("#address-cells"))
    sc = words(reserved_parent.get("#size-cells"))
    try:
        entries = ranges(region["reg"], ac[0], sc[0]) if ac and sc else []
    except (KeyError, ValueError, struct.error):
        entries = []
    print(f"  reserved region: {[(hex(a), hex(s)) for a,s in entries]}")
    if entries != [(0xCA000000, 0x01400000)]:
        errors.append("handover reserve address/length differs from stock")
    if visible is not None and entries and visible > entries[0][1]:
        errors.append("visible framebuffer exceeds fixed reservation")

    root_ac = words(root.get("#address-cells"))
    if not root_ac:
        errors.append("root missing address-cells")
    print(f"  panel status: {string(panel.get('status')) or 'okay'}")
    print(f"  DECON status: {string(decon.get('status')) or 'okay'} "
          f"compatible={string(decon.get('compatible'))}")
    print(f"  backlight status: {string(backlight.get('status')) or 'okay'} "
          f"compatible={string(backlight.get('compatible'))}")
    if string(panel.get("status")) != "disabled":
        errors.append("native panel must stay disabled")
    if b"samsung,exynos9810-decon-takeover" not in decon.get("compatible", b"").split(b"\0"):
        errors.append("expected DECON takeover driver description missing")
    bl = words(panel.get("backlight"))
    print(f"  panel backlight provider: {phandles.get(bl[0]) if len(bl)==1 else None}")
    if len(bl) == 1 and phandles.get(bl[0]) != BACKLIGHT:
        errors.append("panel backlight reference unresolved or unexpected")

    print("  Linux binding allows memory-region without a separate reg property.")
    print("  No native HX83102E DSI/DRM panel driver or GPIO power sequencing validated.")
    print("  Stock panel: 600x1920 vendor timing field, 4 lanes, 60 Hz.")
    print("  Framebuffer: 1200x1920, 4800 bytes/line, XRGB8888.")
    print("  Actual bootloader scanout address, takeover driver and clock retention")
    print("  are NOT proven by this static test.")
    if errors:
        for e in errors:
            print("ERROR: " + e, file=sys.stderr)
        return 1
    print("PASS: Stage 9 static layout, reserved-memory and DECON takeover descriptions.")
    print("NOT BOOT-VALIDATED. Do not flash.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-display-handover.py compiled.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(audit(sys.argv[1]))
    except (OSError, KeyError, ValueError, struct.error) as e:
        print(f"Audit failed: {e}", file=sys.stderr)
        sys.exit(1)
