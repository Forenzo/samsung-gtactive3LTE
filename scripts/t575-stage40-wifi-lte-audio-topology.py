#!/usr/bin/env python3
"""Stage 40 — audit the inherited T570 audio graph against proven T575 UAIF1.

Checks only public repository text. This deliberately does not build, enable,
edit, probe, or flash audio hardware. PASS means incompatibility was found and
the conservative T575 sound disable is retained, not audio support.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WIFI_PATCH = ROOT / "patches/linux/0110-arm64-dts-exynos-gtactive3wifi-Add-audio.patch"
LTE = ROOT / "dts/exynos9810-gtactive3lte.dts"
CONFIG = ROOT / "configs/gtactive3-bringup.config"

def check(label, ok, summary):
    print(f"  {'PASS' if ok else 'REVIEW'} — {label}: {summary}")
    return bool(ok)

def main():
    wifi = WIFI_PATCH.read_text(encoding="utf-8")
    lte = LTE.read_text(encoding="utf-8")
    cfg = CONFIG.read_text(encoding="utf-8")
    # Only added lines of the patch, not deleted text or commit prose.
    added = "\n".join(line[1:] for line in wifi.splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    no_comments = re.sub(r"/\*.*?\*/|//[^\n]*", "", lte, flags=re.S)
    print("Stage 40 — static T570 vs T575 UAIF1 ASoC topology check")
    results = [
        check("Wi-Fi speaker CPU routes via ABOX1",
              bool(re.search(r"speaker-dai-link\s*\{.*?sound-dai\s*=\s*<&abox\s+1\s*>",
                             added, re.S)), "T570 CPU route uses ABOX DAI 1"),
        check("Wi-Fi speaker codec is RT5510",
              bool(re.search(r"speaker-dai-link\s*\{.*?codec\s*\{\s*sound-dai\s*=\s*<&rt5510>",
                             added, re.S)), "T570 speaker references RT5510"),
        check("LTE inherited sound explicitly disabled",
              bool(re.search(r'&\{/sound\}\s*\{\s*status\s*=\s*"disabled"', no_comments)),
              "do not register T570 RT5510 card on T575"),
        check("LTE inherited RT5510 explicitly disabled",
              bool(re.search(r'&\{/soc@0/usi@108c00c0/i2c@108c0000/amplifier@34\}\s*\{\s*status\s*=\s*"disabled"', no_comments)),
              "wrong amplifier remains off"),
        check("Inherited T570 ASoC machine remains selected in generic config",
              "CONFIG_SND_SOC_SAMSUNG_GTACTIVE3_RT5665=m" in cfg,
              "requires T575-specific machine-driver review"),
        check("TAS2562 codec is not yet selected in bringup config",
              "CONFIG_SND_SOC_TAS2562=" not in cfg,
              "do not infer codec driver build support"),
    ]
    print("Owner-confirmed vendor T575: /sound/uaif@1/codec -> TAS2562 DAI 0")
    print("T570: same ABOX UAIF1 CPU route, but different speaker codec.")
    print("A kernel sound-card binding and codec driver integration are NOT validated.")
    print("Result:", "PASS — preserve T575 sound disable" if all(results) else "REVIEW REQUIRED")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
