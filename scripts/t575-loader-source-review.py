#!/usr/bin/env python3
"""Stage 47 LTE loader compatibility review (offline, no compilation or USB).

Reports hardcoded T570 loader assumptions so an LTE board port can replace
them. A successful review never authorizes flashing or claims boot safety.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "bootchain/uniLoader/configs/gtactive3wifi_defconfig"
LOADER = ROOT / "bootchain/uniLoader/arch/aarch64/load-kernel.c"
MAIN = ROOT / "bootchain/uniLoader/main/main.c"

def main():
    config = CFG.read_text()
    loader = LOADER.read_text()
    main_src = MAIN.read_text()
    needed = {
        "Wi-Fi board selector": "CONFIG_SAMSUNG_GTACTIVE3WIFI=y" in config,
        "kernel copy fixed address": "CONFIG_PAYLOAD_ENTRY" in loader,
        "ramdisk copy fixed address": "CONFIG_RAMDISK_ENTRY" in loader,
        "bootloader invokes board early-init": "board_ops.ops.early_init" in main_src,
        "bootloader invokes board late-init": "board_ops.ops.late_init" in main_src,
        "kernel launch implementation": "load_kernel_and_jump" in loader,
    }
    print("Stage 47 — inherited loader review; no kernel build")
    for name, present in needed.items():
        print(f"  {'FOUND' if present else 'MISSING'}: {name}")
    if not all(needed.values()):
        print("FAIL: Inherited code changed; re-review before LTE adaptation.")
        return 1
    print("  ACTION REQUIRED: implement a dedicated SM-T575 board selector and board init")
    print("  ACTION REQUIRED: prove RAM ownership and loader runtime footprint")
    print("  ACTION REQUIRED: confirm S-Boot register/EL/cache and display handover")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    print("  Static source inventory: PASS (LTE compatibility NOT validated)")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
