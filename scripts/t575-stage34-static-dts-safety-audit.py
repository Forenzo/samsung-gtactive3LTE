#!/usr/bin/env python3
"""Stage 34: static safety audit of the LTE Linux DTS against verified stock evidence.

Reads only the public source DTS in the local repository; no tablet/ADB,
private images, compiler, flash or file changes. Reports mismatches
without silently enabling unvalidated hardware.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "dts" / "exynos9810-gtactive3lte.dts"

def block(source, selector):
    # Find a top-level &{...} override, taking braces in selectors into account.
    token = "&{" + selector + "}"
    start = source.find(token)
    if start < 0:
        return None
    open_brace = source.find("{", start + len(token))
    if open_brace < 0:
        return None
    end = source.find("};", open_brace)
    if end < 0:
        return None
    return source[open_brace:end]

def check(name, condition, detail):
    print(f"  {'PASS' if condition else 'CHECK'} — {name}: {detail}")
    return condition

def main():
    src = PATH.read_text(encoding="utf-8")
    # Remove comments so documentation alone cannot satisfy a safety gate.
    uncommented = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S)
    print("Stage 34 — current LTE DTS evidence/safety audit (static)")
    ok = True
    ok &= check("T575 identity", '"samsung,gtactive3lte"' in uncommented,
                "distinct LTE compatible")
    for label, sel in (
        ("wrong T570 RT5510 amplifier", "/soc@0/usi@108c00c0/i2c@108c0000/amplifier@34"),
        ("unverified board sound card", "/sound"),
        ("unvalidated T570 DECON takeover", "/soc@0/display-controller@16030000"),
    ):
        text = block(uncommented, sel)
        safe = text is not None and re.search(r'\bstatus\s*=\s*"disabled"\s*;', text) is not None
        ok &= check(label, safe, "explicitly disabled" if safe else "safety gate missing")
    # The LTE TAS2562 prototype must NEVER become enabled by an
    # accidental DTS edit. Keep the codec, inherited T570 sound card and
    # wrong RT5510 all explicitly disabled until an approved bring-up.
    codec_parent = block(uncommented, "/soc@0/usi@108c00c0/i2c@108c0000")
    codec = re.search(
        r'amplifier@4c\\s*\\{([^{}]*)\\};',
        codec_parent or "", flags=re.S)
    codec_body = codec.group(1) if codec else ""
    ok &= check("LTE TAS2562 codec remains disabled",
                bool(codec) and
                bool(re.search(r'\\bstatus\\s*=\\s*"disabled"\\s*;', codec_body)) and
                bool(re.search(r'\\breg\\s*=\\s*<0x4c>\\s*;', codec_body)) and
                'compatible = "ti,tas2562"' in codec_body and
                bool(re.search(r'#sound-dai-cells\\s*=\\s*<1>\\s*;', codec_body)),
                "address/binding pinned, prototype disabled")
    for label, addr in (("modem carveout", "0xf0000000"),
                        ("modem logging carveout", "0xf9200000"),
                        ("S-Boot framebuffer reservation", "0xca000000")):
        ok &= check(label, addr in uncommented, f"{addr} represented")
    touch = block(uncommented, "/soc@0/usi@13ae00c0/spi@13ae0000/touchscreen@0")
    ok &= check("T575 SPI touchscreen cap", touch is not None and "7000000" in touch,
                "7 MHz cap" if touch is not None else "missing override")
    print("Stock effective DT evidence: DSIM1=okay, sound=okay, TAS2562=ok, RT5510=disabled")
    print("Intentional Linux prototype difference: sound and DECON stay disabled.")
    print("Do not equate vendor 'okay' with mainline driver support or safe handover.")
    print("Result:", "PASS — retain conservative DTS" if ok else "REVIEW NEEDED")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
