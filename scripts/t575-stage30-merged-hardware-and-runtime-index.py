#!/usr/bin/env python3
"""Stage 30: offline merged display/audio status and optional read-only runtime DTBO index.

Uses private BOOT/DTBO backups and fdtoverlay; temporary FDTs automatically
removed. If an authorized SM-T575 is connected, queries only the running
Android's DTBO selection (never publishes full bootargs or identifiers).
No flashing, partition writes, register access, or device reboot.
"""
import argparse
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader("stage28_fdt", str(HERE / "t575-stage28-fdt-status-targets.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
dt = importlib.util.module_from_spec(spec)
loader.exec_module(dt)

TARGETS = (
    "dsim@0x16080000", "dsim@0x16090000", "decon_f@0x16030000",
    "decon_t@0x16050000", "hx83102e", "decon_board_hx83102e",
    "sound", "tas2562@4c", "rt5510@34", "modem_if", "cp_ram_logging",
)

def adb(*args):
    try:
        p = subprocess.run(["adb", *args], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None

def runtime_index():
    devices = adb("devices")
    if devices is None:
        return None, "ADB unavailable"
    authorized = [line for line in devices.decode("utf-8", "replace").splitlines()[1:]
                  if line.endswith("\tdevice")]
    if len(authorized) != 1:
        return None, "not exactly one authorized ADB device"
    model = adb("shell", "getprop", "ro.product.model")
    if model is None or model.strip() != b"SM-T575":
        return None, "not confirmed SM-T575"
    prop = adb("shell", "getprop", "ro.boot.dtbo_idx")
    if prop:
        v = prop.strip().decode("ascii", "replace")
        if re.fullmatch(r"\d{1,3}", v):
            return int(v), "ro.boot.dtbo_idx"
    # Read bootargs ONLY to pick out the numeric dtbo_idx; never print
    # any other boot parameters, serial values, or the full command line.
    cmd = adb("shell", "cat", "/proc/cmdline")
    if cmd:
        m = re.search(rb"(?:^|\s)androidboot\.dtbo_idx=(\d{1,3})(?=\s|$)", cmd)
        if m:
            return int(m.group(1)), "androidboot.dtbo_idx"
    return None, "runtime index not exposed through checked read-only sources"

def merge(base, overlay, tool):
    old_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="t575-stage30-") as tmp:
            folder = Path(tmp)
            bf, of, mf = folder / "base.dtb", folder / "overlay.dtbo", folder / "merged.dtb"
            bf.write_bytes(base)
            of.write_bytes(overlay)
            proc = subprocess.run([tool, "-i", str(bf), "-o", str(mf), str(of)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            if proc.returncode != 0 or not mf.is_file() or mf.stat().st_size > 8_000_000:
                raise ValueError("offline overlay merge failed")
            return mf.read_bytes()
    finally:
        os.umask(old_umask)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path,
                   default=Path.home() / "Downloads" / "SM-T575-Recovery")
    p.add_argument("--overlay", type=int, default=5,
                   help="offline index selected from older Android evidence")
    p.add_argument("--offline", action="store_true", help="skip optional ADB read-only index query")
    args = p.parse_args()
    tool = shutil.which("fdtoverlay")
    if not tool:
        raise ValueError("fdtoverlay missing; install dtc")
    base, overlay = dt.load(args.folder.expanduser(), args.overlay)
    nodes = dt.parse(merge(base, overlay, tool))
    print("Stage 30 — merged T575 display/audio inventory")
    print(f"Offline DTBO index: {args.overlay}; merged nodes: {len(nodes)}")
    for needle in TARGETS:
        matches = [node for node in nodes if node["name"] == needle]
        print(f"  {needle}: {len(matches)} node(s)")
        for node in matches[:8]:
            print(f"    {node['path']}: status={node['props'].get('status', '(no explicit status)')}")
    if args.offline:
        print("Running Android DTBO index: NOT CHECKED (--offline)")
    else:
        selected, source = runtime_index()
        if selected is None:
            print(f"Running Android DTBO index: UNKNOWN ({source})")
        else:
            print(f"Running Android DTBO index: {selected} (source: {source})")
            print("Historical overlay index matches running Android:"
                  f" {'YES' if selected == args.overlay else 'NO — investigate'}")
    print("Private temporary FDTs removed; original backup images unchanged.")
    print("Even matching index does NOT prove a Linux boot image or non-wiping restore.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Stage 30 STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
