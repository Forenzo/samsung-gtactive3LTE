#!/usr/bin/env python3
"""Stage 43 — LTE-only codec compile config safety checks; optional pinned source.

No device contact, kernel build, flashing or source changes. A passing
configuration check is NOT evidence the codec actually compiled.
"""
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "configs/gtactive3lte-tas2562-compileonly.config"
WIFI = ROOT / "configs/gtactive3-bringup.config"
LTE = ROOT / "dts/exynos9810-gtactive3lte.dts"

def check(label, ok):
    print(f"  {'PASS' if ok else 'FAIL'} — {label}")
    return bool(ok)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kernel", type=Path, help="Optional path to patched/pinned Linux source checkout")
    args = ap.parse_args()
    conf = FRAGMENT.read_text(encoding="utf-8")
    wifi = WIFI.read_text(encoding="utf-8")
    dts = re.sub(r"/\*.*?\*/|//[^\n]*", "", LTE.read_text(encoding="utf-8"), flags=re.S)
    entries = re.findall(r"(?m)^CONFIG_[A-Z0-9_]+=.*$", conf)
    print("Stage 43 — isolated T575 TAS2562 compile-only config")
    checks = [
        check("TAS2562 is a module in LTE-only fragment",
              entries.count("CONFIG_SND_SOC_TAS2562=m") == 1),
        check("LTE fragment excludes Wi-Fi MT6660 and machine symbols",
              not any("MT6660" in x or "GTACTIVE3_RT5665" in x for x in entries)),
        check("original T570 machine config unchanged in place",
              "CONFIG_SND_SOC_SAMSUNG_GTACTIVE3_RT5665=m" in wifi),
        check("LTE board sound explicitly disabled",
              bool(re.search(r'&\{/sound\}\s*\{\s*status\s*=\s*"disabled"', dts))),
        check("LTE amplifier node remains explicitly disabled",
              bool(re.search(r'amplifier@4c\s*\{[^{}]*status\s*=\s*"disabled"', dts, re.S))),
        check("LTE RT5510 remains explicitly disabled",
              bool(re.search(r'&\{/soc@0/usi@108c00c0/i2c@108c0000/amplifier@34\}\s*\{\s*status\s*=\s*"disabled"', dts))),
    ]
    if args.kernel:
        kernel = args.kernel.expanduser()
        kconf = kernel / "sound/soc/codecs/Kconfig"
        kmake = kernel / "sound/soc/codecs/Makefile"
        driver = kernel / "sound/soc/codecs/tas2562.c"
        if not all(x.is_file() for x in (kconf, kmake, driver)):
            print("  FAIL — kernel source missing TAS2562 source/Kconfig/Makefile")
            checks.append(False)
        else:
            checks.append(check("pinned kernel defines TAS2562",
                         bool(re.search(r"(?m)^config SND_SOC_TAS2562\s*$", kconf.read_text()))))
            checks.append(check("pinned kernel builds tas2562 module",
                         "obj-$(CONFIG_SND_SOC_TAS2562)" in kmake.read_text()))
            checks.append(check("pinned kernel recognizes ti,tas2562",
                         '"ti,tas2562"' in driver.read_text()))
    else:
        print("  Pinned kernel source: NOT CHECKED (optional --kernel /path)")
    print("Stage 43:", "PASS — compile-only configuration isolated" if all(checks) else "FAIL — review")
    print("No actual module compile performed; no audio enablement.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if all(checks) else 1

if __name__ == "__main__":
    sys.exit(main())
