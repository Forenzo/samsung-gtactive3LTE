#!/usr/bin/env python3
"""Stage 45: install the LTE-only ASoC prototype in a CI kernel checkout.

This modifies ONLY the supplied throwaway kernel source directory. It does
not edit the repository's Wi-Fi patch series, device, or firmware.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "drv/audio/t575/gtactive3lte_tas2562.c"
SYMBOL = "SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562"
MARKER = "config " + SYMBOL
KCONFIG_ENTRY = """
config SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562
	tristate "Galaxy Tab Active3 LTE TAS2562 audio (experimental)"
	depends on SND_SOC_SAMSUNG_EXYNOS9810_ABOX && I2C
	select SND_SOC_TAS2562
	help
	  Compile-only SM-T575 speaker ABOX UAIF1 / TAS2562 machine
	  prototype. Its device-tree sound node remains disabled.
"""
MAKE_ENTRY = "obj-$(CONFIG_SND_SOC_SAMSUNG_GTACTIVE3LTE_TAS2562) += snd-soc-gtactive3lte-tas2562.o"
COMPOSITE = "snd-soc-gtactive3lte-tas2562-y := gtactive3lte_tas2562.o"

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/t575-stage45-install-machine-source.py /absolute/kernel")
        return 2
    kernel = Path(sys.argv[1]).resolve()
    if not kernel.is_dir() or not (kernel / "Makefile").is_file():
        print("Kernel source tree not found")
        return 2
    dest = kernel / "sound/soc/samsung"
    kconf = dest / "Kconfig"
    mk = dest / "Makefile"
    code = dest / SOURCE.name
    if not kconf.is_file() or not mk.is_file():
        print("Samsung ASoC source tree missing")
        return 2
    kc = kconf.read_text()
    ma = mk.read_text()
    if MARKER in kc or MAKE_ENTRY in ma or code.exists():
        print("Refusing to overwrite existing LTE machine driver")
        return 1
    if "config SND_SOC_SAMSUNG_EXYNOS9810_ABOX" not in kc:
        print("Pinned kernel does not include the ABOX driver Kconfig")
        return 1
    if not (kernel / "sound/soc/codecs/tas2562.c").is_file():
        print("Pinned kernel missing TAS2562 codec source")
        return 1
    if "endif #SND_SOC_SAMSUNG" not in kc:
        print("Expected Samsung Kconfig closing marker missing")
        return 1
    # Sanity checks first, then exclusively modify the throwaway CI tree.
    shutil.copyfile(SOURCE, code)
    kconf.write_text(kc.replace("endif #SND_SOC_SAMSUNG", KCONFIG_ENTRY + "\nendif #SND_SOC_SAMSUNG"))
    mk.write_text(ma.rstrip() + "\n" + COMPOSITE + "\n" + MAKE_ENTRY + "\n")
    print("Stage 45: LTE-only machine source installed in temporary kernel checkout")
    print("No Wi-Fi driver edited; no DTS hardware enabled")
    return 0

if __name__ == "__main__":
    sys.exit(main())
