#!/usr/bin/env python3
"""Advisory T575 input bus audit: reads compiled Linux DTB only.

Checks static SPI/I2C address assignments and selected properties against
Samsung's *reported* stock overlay 5. Differences are reported as REVIEW,
not automatically overwritten or treated as hardware failures.
"""
import runpy
import struct
import sys
from pathlib import Path

def u32(raw):
    return struct.unpack(">I", raw)[0] if len(raw) == 4 else None

def val(raw):
    if raw is None:
        return "(absent)"
    if len(raw) == 4:
        return f"{u32(raw)} (0x{u32(raw):x})"
    if len(raw) % 4 == 0 and raw:
        return " ".join(hex(x[0]) for x in struct.iter_unpack(">I", raw))
    return raw.split(b"\0")[0].decode("utf-8", "replace")

def main(path):
    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(path)
    checks = [
        ("Himax SPI21 touchscreen",
         "/soc@0/usi@13ae00c0/spi@13ae0000/touchscreen@0",
         {"reg": 0, "spi-max-frequency": 7000000},
         ("interrupts", "reset-gpios", "irq-gpios", "firmware-name", "pinctrl-0")),
        ("Wacom HSI2C23 digitizer",
         "/soc@0/usi@109100c0/i2c@10910000/digitizer@56",
         {"reg": 0x56},
         ("interrupts", "irq-gpios", "vdd-supply", "firmware-name", "pinctrl-0")),
    ]
    review = []
    print("SM-T575 Stage 7: static input device property comparison")
    for label, node, expected, extras in checks:
        print(f"\n{label}: {node}")
        p = nodes.get(node)
        if p is None:
            review.append(f"{label}: inherited Linux node absent")
            continue
        for k, value in expected.items():
            got = u32(p.get(k, b""))
            print(f"  {k}: {val(p.get(k))} (stock overlay: {value})")
            if got != value:
                review.append(f"{label}: {k}: inherited {got} vs stock {value}")
        for k in extras:
            print(f"  {k}: {val(p.get(k))}")
    if review:
        print("\nREVIEW REQUIRED (do not blindly change GPIO bindings):")
        for x in review:
            print(" - " + x)
    else:
        print("\nBoth bus addresses and touchscreen SPI limit match stock overlay 5.")
    print("NOTE: This is an advisory description audit, not a hardware probe.")
    print("NOTE: GPIO polarity, phandles, firmware, pinctrl and power must be verified separately.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-input-details.py compiled-linux.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1]))
    except (ValueError, KeyError, OSError, struct.error) as e:
        print(f"Audit error: {e}", file=sys.stderr)
        sys.exit(1)
