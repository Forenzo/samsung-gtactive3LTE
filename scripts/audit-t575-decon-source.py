#!/usr/bin/env python3
"""Stage 10: review T570 DECON takeover assumptions; gate LTE use.

Reads only the pinned source patch and the *compiled Linux* SM-T575 DTB.
This is a source-level safety gate, NOT a driver test or a flashable boot.
"""
import runpy
import struct
import sys
from pathlib import Path

SOURCE = Path("patches/linux/0124-drm-Add-an-Exynos9810-DPU-takeover-KMS-driver.patch")
DECON = "/soc@0/display-controller@16030000"
FRAME = "/chosen/framebuffer-0"
PANEL = "/panel"

def first(data):
    return data.split(b"\0")[0].decode("utf-8", "replace") if data else "(absent)"

def audit(dtb):
    parse = runpy.run_path(str(Path(__file__).with_name("audit-t575-memory.py")))["parse"]
    nodes = parse(dtb)
    errors = []
    print("Stage 10: pinned T570 DECON driver source and T575 safety gate")
    if not SOURCE.is_file():
        print("ERROR: pinned driver patch not found", file=sys.stderr)
        return 1
    source = SOURCE.read_text(encoding="utf-8")
    critical = {
        "DECON compatible": 'samsung,exynos9810-decon-takeover',
        "IDMA scanout register": "IDMA_IN_BASE_ADDR_Y",
        "Bootloader buffer read": "dpu->boot_addr = cur;",
        "Simple DRM aperture eviction": "aperture_remove_conflicting_devices(",
        "Aperture ownership": "devm_aperture_acquire_for_platform_device(",
        "Shadow window update": "SHADOW_REG_UPDATE_REQ_WIN(dpu->win)",
        "Original panel setup retention": "The panel and DSI links are not reprogrammed.",
        "T570 measured window assumption": "window 5 <- IDMA_G0",
    }
    for desc, needle in critical.items():
        present = needle in source
        print(f"  source {desc}: {'found' if present else 'MISSING'}")
        if not present:
            errors.append(f"source assumption changed: {desc}; re-audit before use")

    # This detects source drift; it does NOT prove the driver has no other
    # guards, nor is it intended as a driver security analysis.
    unresolved = [
        "T575 window 5 / IDMA_G0 scanout selection not measured",
        "T575 IDMA base address and SysMMU bypass not measured under S-Boot",
        "DECON clock/IRQ ownership on T575 not measured",
        "Panel 600-vs-1200 vendor width semantics not resolved",
        "Runtime simpledrm-to-DECON takeover not tested on T575",
    ]
    for issue in unresolved:
        print(f"  UNVERIFIED: {issue}")

    decon, frame, panel = (nodes.get(p) for p in (DECON, FRAME, PANEL))
    if decon is None:
        errors.append("DECON node absent")
    else:
        print(f"  T575 DECON status: {first(decon.get('status'))}")
        if first(decon.get("status")) != "disabled":
            errors.append("T575 DECON must be disabled pending measured scanout validation")
    if panel is None or first(panel.get("status")) != "disabled":
        errors.append("native HX83102E panel must remain disabled")
    if frame is None or b"simple-framebuffer" not in frame.get("compatible", b"").split(b"\0"):
        errors.append("boot framebuffer description missing")
    if frame is not None and not frame.get("memory-region"):
        errors.append("boot framebuffer memory-region absent")

    print("  The simple-framebuffer DT node is retained, but this is NOT proof")
    print("  that simpledrm is enabled in the future kernel configuration.")
    if errors:
        for e in errors:
            print("ERROR: " + e, file=sys.stderr)
        return 1
    print("PASS: Stage 10 conservative source audit and T575 display isolation.")
    print("NO hardware probe, kernel binary test, or flash approval.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit-t575-decon-source.py compiled-linux.dtb", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(audit(sys.argv[1]))
    except (OSError, ValueError, KeyError, UnicodeDecodeError, struct.error) as error:
        print(f"Stage 10 error: {error}", file=sys.stderr)
        sys.exit(1)
