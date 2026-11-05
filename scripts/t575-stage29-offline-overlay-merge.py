#!/usr/bin/env python3
"""Stage 29 — offline *temporary* DTBO #5 merge and focused status inventory.

Reads the private local BOOT/DTBO backups. Uses the installed fdtoverlay
(device-tree-compiler package) to generate three private temporary FDT
files in an automatically removed directory. Never writes to the tablet,
backups, or repository and never prints raw properties or unique IDs.
The selected index 5 is historical, not revalidated against live Android.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

# Import our vetted, bounded, local FDT parser; source file is in this folder.
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec

HERE = Path(__file__).resolve().parent
MODULE_FILE = HERE / "t575-stage28-fdt-status-targets.py"
loader = SourceFileLoader("stage28_fdt", str(MODULE_FILE))
spec = spec_from_loader(loader.name, loader)
mod = module_from_spec(spec)
loader.exec_module(mod)

CATEGORIES = mod.CATEGORIES

def report_effective(blob):
    nodes = mod.parse(blob)
    print(f"Offline merged FDT: {len(nodes)} nodes")
    for category, pattern in CATEGORIES.items():
        matching = [n for n in nodes if pattern.search(n["name"])]
        print(f"  {category}: {len(matching)} matching node names (max 32 shown)")
        for item in matching[:32]:
            status = item["props"].get("status", "(no explicit status)")
            print(f"    {item['path']} [status={status}]")
    print("NOTE: no explicit status does not prove the hardware driver works.")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path,
                   default=Path.home() / "Downloads" / "SM-T575-Recovery")
    p.add_argument("--overlay", type=int, default=5)
    args = p.parse_args()
    tool = shutil.which("fdtoverlay")
    if not tool:
        print("Stage 29 BLOCKED: 'fdtoverlay' is not installed on this Mac.", file=sys.stderr)
        print("Install the 'dtc' (device-tree-compiler) package using Homebrew, then retry.", file=sys.stderr)
        return 2
    base, overlay = mod.load(args.folder.expanduser(), args.overlay)
    if len(base) < 40 or len(overlay) < 40:
        raise ValueError("Invalid FDT sizes")
    print(f"Stage 29 — offline applying historical overlay #{args.overlay}")
    # Private vendor DTs may hold sensitive properties; never persist to a public
    # checkout or normal Downloads files. Temporary folder is owner-only.
    old_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="t575-stage29-") as directory:
            root = Path(directory)
            base_file, overlay_file, merged_file = (
                root / "base.dtb", root / "selected.dtbo", root / "merged.dtb")
            base_file.write_bytes(base)
            overlay_file.write_bytes(overlay)
            proc = subprocess.run(
                [tool, "-i", str(base_file), "-o", str(merged_file), str(overlay_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            if proc.returncode:
                # Diagnostic stderr may include vendor paths: suppress raw text.
                print(f"fdtoverlay returned exit status {proc.returncode} "
                      "(diagnostic details withheld to avoid exposing vendor data).")
                print("Merge NOT VERIFIED. No boot or flash approval.")
                return 1
            if not merged_file.is_file() or merged_file.stat().st_size > 8_000_000:
                raise ValueError("Merged DTB missing or unexpectedly large")
            report_effective(merged_file.read_bytes())
    finally:
        os.umask(old_umask)
    print("Offline selected-overlay merge: PASS")
    print("Does not establish actual Android DTBO selection or Linux driver support.")
    print("Private merge files removed. RESTORE/BOOT/FLASH GATE: BLOCKED.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Stage 29 stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
