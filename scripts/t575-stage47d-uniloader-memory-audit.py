#!/usr/bin/env python3
"""Stage 47D: static memory-fit audit of inherited SM-T570 uniLoader profile.

READ ONLY. It audits prospective copy destinations, NOT bootloader behavior.
Never runs uniLoader, creates an Android BOOT image, flashes or reboots.
This is a candidate profile inspection only, not approval to use T570 code.
"""
import argparse
from pathlib import Path
import re
import struct
import sys

KNOWN_RESERVED = {
    "camera-contig": (0x95000000, 0x00a00000),
    "rkp": (0xaf600000, 0x02400000),
    "tima": (0xb8000000, 0x00200000),
    "secure-log": (0xc0000000, 0x00080000),
    "S-Boot framebuffer": (0xca000000, 0x01400000),
    "secure-camera": (0xe1900000, 0x02000000),
    "teegris": (0xed310000, 0x00002000),
    "modem": (0xf0000000, 0x09200000),
    "modem-log": (0xf9200000, 0x02000000),
    "abox": (0xfb200000, 0x02800000),
    "exynos-ss": (0xfda00000, 0x01c08000),
    "fimc-lib": (0xff780000, 0x00880000),
    "camera-pool-high": (0x880000000, 0x0b400000),
}
REQUIRED = ("CONFIG_TEXT_BASE", "CONFIG_PAYLOAD_ENTRY",
            "CONFIG_RAMDISK_ENTRY", "CONFIG_FRAMEBUFFER_BASE",
            "CONFIG_FRAMEBUFFER_WIDTH", "CONFIG_FRAMEBUFFER_HEIGHT",
            "CONFIG_FRAMEBUFFER_STRIDE")
MAX_FILE_SIZE = 256 * 1024 * 1024

def parse_config(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed = {}
    for line in lines:
        m = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=(.*)", line.strip())
        if m:
            parsed[m.group(1)] = m.group(2)
    missing = [k for k in REQUIRED if k not in parsed]
    if missing:
        raise ValueError("missing uniLoader settings: " + ", ".join(missing))
    return {k: int(parsed[k], 0) for k in REQUIRED}

def get_file(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label}: missing regular file or symlink")
    size = path.stat().st_size
    if not (0 < size <= MAX_FILE_SIZE):
        raise ValueError(f"{label}: invalid size {size}")
    return size

def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]

def run(args):
    cfg = parse_config(args.config)
    if (cfg["CONFIG_FRAMEBUFFER_BASE"], cfg["CONFIG_FRAMEBUFFER_WIDTH"],
        cfg["CONFIG_FRAMEBUFFER_HEIGHT"], cfg["CONFIG_FRAMEBUFFER_STRIDE"]) != (
            0xca000000, 1200, 1920, 4):
        raise ValueError("Inherited framebuffer configuration differs from expected T575 dimensions")
    image_len = get_file(args.kernel, "ARM64 Image")
    with args.kernel.open("rb") as f:
        head = f.read(64)
    if head[56:60] != b"ARM\x64":
        raise ValueError("kernel missing ARM64 Image header")
    text_offset, mem_size = struct.unpack_from("<QQ", head, 8)
    # Linux arm64 header image_size describes the full loaded footprint.
    image_footprint = max(image_len, mem_size or image_len)
    ramdisk_len = get_file(args.initramfs, "diagnostic initramfs")
    dtb_len = get_file(args.dtb, "T575 DTB")
    if dtb_len > 4 * 1024 * 1024:
        raise ValueError("LTE DTB too large for offline audit")
    print("Stage 47D — inherited uniLoader memory-copy destinations")
    regions = {
        "kernel copy/footprint": (cfg["CONFIG_PAYLOAD_ENTRY"],
                                  cfg["CONFIG_PAYLOAD_ENTRY"] + image_footprint),
        "ramdisk copy": (cfg["CONFIG_RAMDISK_ENTRY"],
                          cfg["CONFIG_RAMDISK_ENTRY"] + ramdisk_len),
    }
    # Text base is a link address, NOT proof of the loaded loader's full RAM footprint.
    loader_addr = cfg["CONFIG_TEXT_BASE"]
    for name, (start, end) in regions.items():
        print(f"  {name}: {start:#x}..{end:#x} ({end - start} bytes)")
    print(f"  uniLoader link TEXT_BASE: {loader_addr:#x} (runtime footprint UNKNOWN)")
    print(f"  Linux ARM64 text_offset: {text_offset:#x} (entry semantics unverified)")
    print(f"  T575 DTB size: {dtb_len} bytes (runtime DTB destination UNKNOWN)")
    names = list(regions)
    if overlaps(regions[names[0]], regions[names[1]]):
        raise ValueError("prospective Linux kernel and ramdisk collide")
    for name, region in regions.items():
        if region[0] < 0x80000000 or region[1] > 0x1000000000:
            raise ValueError(name + " outside broad RAM analysis window")
        for reserved, (start, length) in KNOWN_RESERVED.items():
            if overlaps(region, (start, start + length)):
                raise ValueError(name + " overlaps known reserved memory " + reserved)
    for name, region in regions.items():
        if region[0] <= loader_addr < region[1]:
            raise ValueError(name + " would overwrite uniLoader link address")
    print("  Kernel/ramdisk destinations vs known reservations: PASS (static only)")
    print("  NOT PROVEN: actual DRAM bank boundaries, uniLoader runtime size,")
    print("              loader early-init MMIO, DTB address, kernel entry requirements,")
    print("              cache/EL state, S-Boot framebuffer and data-safe restore.")
    print("  Do NOT reuse the Wi-Fi uniLoader or T570 BOOT packager on T575.")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path(
        "bootchain/uniLoader/configs/gtactive3wifi_defconfig"))
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--dtb", type=Path, required=True)
    p.add_argument("--initramfs", type=Path, required=True)
    a = p.parse_args()
    try:
        return run(a)
    except (OSError, ValueError, struct.error) as e:
        print("Stage 47D FAIL:", e, file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
