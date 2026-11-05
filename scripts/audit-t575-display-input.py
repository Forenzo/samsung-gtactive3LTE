#!/usr/bin/env python3
"""Stage 8: read-only GPIO/phandle, supply and panel handover audit.

Only the compiled Linux DTB is inspected. This does not exercise devices.
Vendor GPIO cells from Android's legacy bindings are not automatically
equivalent to Linux GPIO flags, and physical polarity is NOT certified.
"""
import runpy
import struct
import sys
from pathlib import Path

TOUCH = "/soc@0/usi@13ae00c0/spi@13ae0000/touchscreen@0"
PEN = "/soc@0/usi@109100c0/i2c@10910000/digitizer@56"
FRAME = "/chosen/framebuffer-0"
PANEL = "/panel"

def cells(v):
    if not v or len(v) % 4:
        return []
    return [x[0] for x in struct.iter_unpack(">I", v)]

def prop_str(v):
    return v.split(b"\x00")[0].decode("utf-8", "replace") if v else "(absent)"

def audit(file):
    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(file)
    phandles = {}
    for path, attrs in nodes.items():
        n = cells(attrs.get("phandle", b""))
        if len(n) == 1:
            phandles[n[0]] = path

    errors = []
    print("Stage 8: GPIO / regulator / display handover inventory")
    print("Vendor reference: Himax IRQ GPA1_0, reset GPG0_6; Wacom IRQ GPA3_3,")
    print("pen detect GPA3_7, FW enable GPM4_1; panel LDO GPG2_2,")
    print("buck GPH1_4, reset GPA3_4, board control GPA2_5.")
    print("These are vendor pin labels, not yet Linux GPIO binding verification.")

    for desc, path, props in [
        ("Himax touchscreen", TOUCH,
         ("interrupt-parent", "interrupts", "reset-gpios", "pinctrl-0",
          "pinctrl-1", "firmware-name", "spi-max-frequency")),
        ("Wacom digitizer", PEN,
         ("interrupt-parent", "interrupts", "vdd-supply", "reset-gpios",
          "pinctrl-0", "firmware-name")),
        ("Frame buffer", FRAME,
         ("width", "height", "stride", "format", "reg", "memory-region")),
        ("Native panel", PANEL,
         ("status", "compatible", "reset-gpios", "enable-gpios",
          "power-supply", "backlight")),
    ]:
        a = nodes.get(path)
        if a is None:
            errors.append(f"Missing {desc}: {path}")
            continue
        print(f"\n{desc}: {path}")
        for k in props:
            v = a.get(k)
            if v is None:
                print(f"  {k}: absent")
                continue
            if k in ("compatible", "format", "status", "firmware-name"):
                print(f"  {k}: {prop_str(v)}")
                continue
            words = cells(v)
            print(f"  {k}: {' '.join(hex(x) for x in words) if words else v.hex()}")
            if k in ("interrupt-parent", "vdd-supply", "memory-region", "backlight",
                     "power-supply") and words:
                print(f"      provider: {phandles.get(words[0], '(unresolved phandle)')}")
            if k.endswith("-gpios") and words:
                print(f"      provider: {phandles.get(words[0], '(unresolved phandle)')}")
            if k.startswith("pinctrl-") and words:
                print("      pinctrl: " + ", ".join(phandles.get(x, "(unresolved)") for x in words))

    print("\nREGULATOR DETAILS")
    pen_props = nodes.get(PEN, {})
    supply = cells(pen_props.get("vdd-supply", b""))
    if supply:
        target = phandles.get(supply[0])
        if target:
            p = nodes[target]
            print(f"  Wacom supply node: {target}")
            for k in ("regulator-name", "regulator-min-microvolt",
                      "regulator-max-microvolt", "gpio", "enable-gpios", "status"):
                b = p.get(k)
                print(f"  {k}: {' '.join(hex(x) for x in cells(b)) if b and cells(b) else prop_str(b)}")
        else:
            errors.append("Wacom vdd-supply phandle unresolved")
    else:
        errors.append("Wacom vdd-supply absent")

    fb = nodes.get(FRAME, {})
    width, height = cells(fb.get("width", b"")), cells(fb.get("height", b""))
    if width != [1200] or height != [1920]:
        errors.append("Unexpected inherited boot framebuffer dimensions")
    panel = nodes.get(PANEL, {})
    if prop_str(panel.get("status")) != "disabled":
        errors.append("Native panel must remain disabled pending power/timing analysis")

    print("\nDISPLAY TIMING REVIEW")
    print("  Samsung stock HX83102E vendor panel: resolution=<600 1920>, four lanes, 60 Hz")
    print("  Linux boot simple-framebuffer: expected 1200x1920; no native timing validation")
    print("  Distinguish vendor internal panel logical-width from effective pixel width.")
    print("  Do not enable native DRM panel or drive LDO/buck/reset GPIOs yet.")
    for issue in errors:
        print("ERROR: " + issue, file=sys.stderr)
    if errors:
        return 1
    print("PASS: referenced input paths, supply and boot-display guard present.")
    print("NOTE: static-only; phandle resolution is not proof of GPIO polarity or driver support.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-display-input.py compiled-linux.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(audit(sys.argv[1]))
    except (KeyError, ValueError, OSError, struct.error) as e:
        print(f"Audit failed: {e}", file=sys.stderr)
        sys.exit(1)
