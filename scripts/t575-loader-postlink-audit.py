#!/usr/bin/env python3
"""Offline post-link RAM collision audit for SM-T575 uniLoader.

Uses the *linked* ELF symbols (not estimates) and the selected config.
Checks virtual linker addresses only; physical DRAM ownership, S-Boot loaded
address, relocation cache state, kernel EL and non-wiping recovery remain
UNPROVEN. Never makes a BOOT image, flashes or invokes a device.
"""
import argparse
import re
import struct
import subprocess
from pathlib import Path
import sys

RESERVED = {
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
}
def checkfile(p):
    if p.is_symlink() or not p.is_file() or p.stat().st_size == 0:
        raise ValueError(f"not a regular nonempty file: {p}")
def symbols(elf, nm):
    raw = subprocess.check_output([nm, "-P", str(elf)], text=True)
    found = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.fullmatch(r"[0-9a-fA-F]+", parts[2]):
            found[parts[0]] = int(parts[2], 16)
    return found
def collision(a, b):
    return a[0] < b[1] and b[0] < a[1]
def audit(args):
    for p in (args.elf, args.kernel, args.initramfs, args.config):
        checkfile(p)
    cfg = {}
    for ln in args.config.read_text().splitlines():
        m = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=(.*)", ln.strip())
        if m:
            cfg[m.group(1)] = m.group(2)
    for key, val in (("CONFIG_SAMSUNG_GTACTIVE3LTE", "y"),
                     ("CONFIG_CHAINLOAD", None),
                     ("CONFIG_LIBFDT", "y")):
        got = cfg.get(key)
        if got != val:
            raise ValueError(f"unsafe/absent loader option: {key}={got}")
    if cfg.get("CONFIG_RAMDISK_NO_COPY") == "y":
        raise ValueError("initramfs copy disabled")
    vals = {k: int(cfg[k], 0) for k in ("CONFIG_TEXT_BASE",
                                        "CONFIG_PAYLOAD_ENTRY",
                                        "CONFIG_RAMDISK_ENTRY",
                                        "CONFIG_FDT_BUF_SIZE")}
    if int(cfg.get("CONFIG_FDT_BUF_ADDR", "0"), 0):
        raise ValueError("external FDT buffer not audited")
    s = symbols(args.elf, args.nm)
    required = ("_reloc_start", "_reloc_end", "kernel", "dtb",
                "ramdisk", "_stack_end", "kernel_size", "ramdisk_size")
    for key in required:
        if key not in s:
            raise ValueError(f"missing linker symbol {key}")
    base, end = s["_reloc_start"], s["_reloc_end"]
    if not (base == vals["CONFIG_TEXT_BASE"] and end > base):
        raise ValueError("linked loader relocation interval invalid")
    if end - base > 256 * 1024 * 1024:
        raise ValueError("loader unexpectedly large")
    with args.kernel.open("rb") as f:
        hdr = f.read(64)
    if hdr[56:60] != b"ARM\x64":
        raise ValueError("invalid ARM64 Image header")
    image_size = struct.unpack_from("<Q", hdr, 16)[0]
    image_footprint = max(args.kernel.stat().st_size, image_size)
    if image_footprint > 256 * 1024 * 1024:
        raise ValueError("kernel image footprint unreasonably large")
    init_size = args.initramfs.stat().st_size
    if s["kernel_size"] != args.kernel.stat().st_size:
        raise ValueError("embedded kernel length differs from source")
    if s["ramdisk_size"] != init_size:
        raise ValueError("embedded initramfs length differs from source")
    if not (base <= s["kernel"] < s["dtb"] < s["ramdisk"] < end):
        raise ValueError("linked section order unexpected")
    zones = {
        "relocated uniLoader, embedded payloads, BSS and stack": (base, end),
        "Linux kernel destination/declared footprint": (
            vals["CONFIG_PAYLOAD_ENTRY"],
            vals["CONFIG_PAYLOAD_ENTRY"] + image_footprint),
        "initramfs destination": (
            vals["CONFIG_RAMDISK_ENTRY"],
            vals["CONFIG_RAMDISK_ENTRY"] + init_size),
    }
    print("Stage 47: post-link memory fit (static only)")
    for name, (a, b) in zones.items():
        print(f"  {name}: {a:#x}..{b:#x} ({b-a:,} bytes)")
    for name, addr in (("kernel", s["kernel"]), ("dtb", s["dtb"]),
                       ("ramdisk", s["ramdisk"])):
        print(f"  embedded {name}: {addr:#x}")
    items = list(zones.items())
    for i, (a_name, a_range) in enumerate(items):
        for b_name, b_range in items[i+1:]:
            if collision(a_range, b_range):
                raise ValueError(f"{a_name} overlaps {b_name}")
        for b_name, (start, length) in RESERVED.items():
            if collision(a_range, (start, start+length)):
                raise ValueError(f"{a_name} overlaps reserved region {b_name}")
    print("  Static linked loader/copy destination collision check: PASS")
    print("  CRITICAL UNVERIFIED: loaded address from S-Boot vs relocated linker")
    print("  CRITICAL UNVERIFIED: live DRAM ownership, MMU, cache and EL handover")
    print("  CRITICAL UNVERIFIED: DTB buffer lifetime, visible display, safe restore")
    print("  RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--elf", required=True, type=Path)
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--initramfs", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--nm", default="aarch64-linux-gnu-nm")
    args = p.parse_args()
    try:
        return audit(args)
    except (ValueError, OSError, subprocess.CalledProcessError, struct.error) as e:
        print(f"Post-link audit: FAIL — {e}", file=sys.stderr)
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 1
if __name__ == "__main__":
    sys.exit(main())
