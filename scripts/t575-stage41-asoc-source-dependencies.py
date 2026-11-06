#!/usr/bin/env python3
"""Stage 41: inspect public Linux sources for a T575-specific audio enablement path.

Read-only and offline. Searches local public patches, driver sources and Kconfig
for a TAS2562 option, the existing ABOX machine driver and the wifi card link.
It does not edit the DTS/config, install software, contact the tablet or boot.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("drv/audio", "patches/linux", "configs")
EXTS = {".c", ".h", ".patch", ".config", ".Kconfig", ".txt"}
TOKENS = {
    "codec": re.compile(r"\b(?:SND_SOC_TAS2562|SND_SOC_TAS256[0-9A-Z_]*|ti,tas2562)\b", re.I),
    "machine": re.compile(r"\b(?:GTACTIVE3_RT5665|gtactive3-audio|samsung,gtactive3-audio)\b", re.I),
    "route": re.compile(r"\b(?:speaker-dai-link|UAIF1|sound-dai)\b", re.I),
}
SKIP = {"node_modules", ".git", "kernel", "build", "__pycache__"}
MAX_FILES = 2500

def relevant_files():
    total = 0
    for dirname in DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(p in SKIP for p in path.parts):
                continue
            if path.suffix not in EXTS and path.name != "Kconfig":
                continue
            if path.stat().st_size > 1_000_000:
                continue
            total += 1
            if total > MAX_FILES:
                raise ValueError("source scan file limit exceeded")
            yield path

def main():
    found = {key: [] for key in TOKENS}
    for path in relevant_files():
        content = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT).as_posix()
        for key, regex in TOKENS.items():
            matches = list(regex.finditer(content))
            if matches:
                # Filename and number of matched occurrences only: avoid
                # quoting vendor source or publishing potentially private data.
                found[key].append((rel, len(matches)))
    print("Stage 41 — read-only T575 audio source dependency audit")
    for key, label in (
        ("codec", "TAS2562 driver/binding symbol mentions"),
        ("machine", "T570 machine-driver references"),
        ("route", "audio route / UAIF1 references"),
    ):
        entries = found[key]
        print(f"  {label}: {len(entries)} matching file(s)")
        for name, count in entries[:24]:
            print(f"    {name} [{count} occurrence(s)]")
        if len(entries) > 24:
            print(f"    ... {len(entries)-24} additional files")
    wifi = (ROOT / "patches/linux/0110-arm64-dts-exynos-gtactive3wifi-Add-audio.patch")
    lte = (ROOT / "dts/exynos9810-gtactive3lte.dts")
    config = (ROOT / "configs/gtactive3-bringup.config")
    ready = all(p.is_file() for p in (wifi, lte, config))
    if ready:
        wc = wifi.read_text(encoding="utf-8")
        lc = lte.read_text(encoding="utf-8")
        cf = config.read_text(encoding="utf-8")
        print("  Wi-Fi ABOX DAI1 + RT5510 route described:",
              "YES" if 'sound-dai = <&abox 1>' in wc and 'sound-dai = <&rt5510>' in wc else "NOT VERIFIED")
        print("  LTE sound disabled:",
              "YES" if re.search(r'&\{/sound\}\s*\{\s*status\s*=\s*"disabled"', lc) else "NO — REVIEW")
        print("  Generic T570 machine config selected:",
              "YES" if "CONFIG_SND_SOC_SAMSUNG_GTACTIVE3_RT5665=m" in cf else "NO/UNKNOWN")
    else:
        print("  Source completeness: MISSING INPUT; cannot draw conclusions")
    print("This scans repository sources, not a fully patched kernel tree.")
    print("No driver/boot support inferred from symbol mentions.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if ready else 2

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"Stage 41 STOPPED: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
