#!/usr/bin/env python3
"""Non-invasive SM-T575 peripheral inventory for a compile-only Linux DTB.

Reads *only* a compiled Linux FDT and reports candidates from the inherited
T570 configuration. Samsung's original proprietary DTB/DTBO is never needed.
These findings are advisory, not a driver/hardware validation or boot gate.
"""
import runpy
import sys
from pathlib import Path

def strings(raw):
    return ", ".join(x.decode("utf-8", "replace") for x in raw.split(b"\0") if x)

def state(props):
    raw = props.get("status", b"okay\0").split(b"\0")[0]
    return raw.decode("ascii", "replace")

def survey(dtb):
    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(dtb)
    categories = {
        "DISPLAY / MIPI": ("panel", "hx83102", "dsim", "dsi", "decon", "simple-framebuffer"),
        "TOUCHSCREEN / SPI": ("himax", "hxcommon", "spi@", "spi-"),
        "PEN / I2C": ("wacom", "w90xx", "i2c@", "hsi2c"),
        "AUDIO": ("tas2562", "rt5510", "rt5665", "sound", "abox"),
        "POWER / USB": ("max77705", "regulator", "usb@10c00000"),
    }
    print("SM-T575 advisory DT peripheral inventory (compile-only)")
    print("Stock overlay 5: Himax SPI21, Wacom HSI2C23, TAS2562 enabled, RT5510 disabled.")
    print("No drivers, regulators or GPIOs are exercised by this script.")
    for category, keys in categories.items():
        print("\n== " + category + " ==")
        matches = []
        for path, props in nodes.items():
            # Avoid confusing disabled child nodes with active devices.
            c = strings(props.get("compatible", b""))
            haystack = (path + " " + c).lower()
            if any(key in haystack for key in keys):
                matches.append((path, state(props), c))
        if not matches:
            print("  (no matching nodes)")
        else:
            for path, status, compatible in matches[:45]:
                print(f"  [{status}] {path} compatible={compatible[:120]}")
            if len(matches) > 45:
                print(f"  ... {len(matches)-45} additional matches omitted")

    # Report non-equivalence; never auto-enable these based on matching names.
    print("\nRequired manual checks before any T575 boot or driver enablement:")
    print(" - Panel GPIO polarity, regulators and reset order, and 600x1920-vs-1200x1920 timings")
    print(" - SPI21 controller mapping and Himax firmware/IRQ/reset pinctrl")
    print(" - HSI2C23 controller mapping, Wacom supply and calibration")
    print(" - rt5510 disabled and tas2562 codec/ASoC bindings verified")
    print(" - Confirm active DT status with parents and aliases, not child status alone")
    print(" - Modem stays disabled; this is NOT a boot-tested DTB")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-peripherals.py compiled-linux.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(survey(sys.argv[1]))
    except (OSError, ValueError, KeyError) as e:
        print(f"Failed to inspect DTB: {e}", file=sys.stderr)
        sys.exit(1)
