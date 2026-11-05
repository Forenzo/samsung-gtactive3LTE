#!/usr/bin/env python3
"""Stage 31: read-only live Android effective-DT status comparison.

Queries only a fixed allowlist of hardware nodes on an authorized SM-T575.
Reports presence and short status property; never reads identifiers,
serials, MAC addresses, modem data, memory/MMIO, or partition contents.
No reboot, writes or flashing. The live kernel DT may differ from the
offline BOOT+DTBO merge due to bootloader fixups.
"""
import argparse
import subprocess
import sys

NODES = {
    "DSIM0": "dsim@0x16080000",
    "DSIM1": "dsim@0x16090000",
    "DECON-F": "decon_f@0x16030000",
    "DECON-T": "decon_t@0x16050000",
    "Panel HX83102E": "hx83102e",
    "Panel power": "decon_board_hx83102e",
    "Sound": "sound",
    "TAS2562": "hsi2c@108C0000/tas2562@4c",
    "RT5510": "hsi2c@108C0000/rt5510@34",
    "Modem memory": "reserved-memory/modem_if",
    "Modem log memory": "reserved-memory/cp_ram_logging",
}
ROOTS = ("/proc/device-tree", "/sys/firmware/devicetree/base")

def adb(*args):
    p = subprocess.run(["adb", *args], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, timeout=20)
    if p.returncode:
        return None
    return p.stdout

def validate():
    devices = adb("devices")
    if devices is None:
        raise RuntimeError("adb devices failed")
    authorized = [line for line in devices.decode("utf-8", "replace").splitlines()[1:]
                  if line.endswith("\tdevice")]
    if len(authorized) != 1:
        raise RuntimeError("exactly one authorized ADB device required")
    model = adb("shell", "getprop", "ro.product.model")
    if model is None or model.strip() != b"SM-T575":
        raise RuntimeError("device is not confirmed SM-T575")

def read_node(root, node):
    # All paths are fixed, assembled from constants above. The command only
    # checks existence and reads a single short 'status' property.
    path = root + "/" + node
    script = ('if test -d "' + path + '"; then '
              'if test -f "' + path + '/status"; then '
              'head -c 32 "' + path + '/status"; '
              'else printf "implicit"; fi; '
              'else printf "missing"; fi')
    out = adb("shell", "sh", "-c", script)
    if out is None:
        return "unavailable"
    raw = out.split(b"\x00", 1)[0].strip()
    text = raw.decode("ascii", "replace")
    if text in ("missing", "implicit", "okay", "ok", "disabled", "reserved", "fail", "fail-sss"):
        return text
    return "other-status" if text else "empty-status"

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    validate()
    root = None
    for candidate in ROOTS:
        p = adb("shell", "sh", "-c", 'test -d "' + candidate + '" && printf exists')
        if p == b"exists":
            root = candidate
            break
    print("Stage 31 — read-only running Android FDT status inventory")
    if root is None:
        print("Runtime device-tree filesystem: NOT EXPOSED")
        print("No conclusions about DT mismatch can be drawn.")
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 2
    print("Runtime tree exposed: YES")
    for label, path in NODES.items():
        print(f"  {label} ({path}): {read_node(root, path)}")
    print("Runtime statuses are kernel DT evidence, not proof Linux drivers work.")
    print("No raw FDT, identity data, or writes. RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"Stage 31 STOPPED: {exc}", file=sys.stderr)
        sys.exit(1)
