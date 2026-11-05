#!/usr/bin/env python3
"""Stage 32 — diagnose Android live FDT node statuses without modifying it.

Uses only fixed, allowlisted paths on a verified SM-T575 through read-only
ADB shell commands. Unlike Stage 31, uses Android's 'cat' rather than
'head -c', and differentiates no node, no status, denied status and
transport failure. Prints only safe status vocabulary, never raw bytes.
"""
import subprocess
import sys

NODES = {
 "DSIM0": "dsim@0x16080000",
 "DSIM1": "dsim@0x16090000",
 "DECON-F": "decon_f@0x16030000",
 "DECON-T": "decon_t@0x16050000",
 "Panel": "hx83102e",
 "Panel power": "decon_board_hx83102e",
 "Sound": "sound",
 "TAS2562": "hsi2c@108C0000/tas2562@4c",
 "RT5510": "hsi2c@108C0000/rt5510@34",
 "Modem memory": "reserved-memory/modem_if",
 "Modem logging": "reserved-memory/cp_ram_logging",
}
ROOTS = ("/proc/device-tree", "/sys/firmware/devicetree/base")
ALLOWED = {b"okay", b"ok", b"disabled", b"reserved", b"fail", b"fail-sss"}
def adb(*args):
    p = subprocess.run(["adb", *args], stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=18, check=False)
    return p.returncode, p.stdout

def verify():
    rc, devices = adb("devices")
    authorized = [line for line in devices.decode("utf-8", "replace").splitlines()[1:]
                  if line.endswith("\tdevice")]
    if rc or len(authorized) != 1:
        raise RuntimeError("Exactly one authorized ADB device required")
    rc, model = adb("shell", "getprop ro.product.model")
    if rc or model.strip() != b"SM-T575":
        raise RuntimeError("Connected device not confirmed SM-T575")

def node_status(root, rel):
    # All paths are internal constants. No user-supplied shell fragments.
    path = root + "/" + rel
    # Use shell builtins and cat (available in Android toybox).
    # Marker codes disambiguate failures without leaking stderr/data.
    command = ('if [ ! -d "' + path + '" ]; then echo NODE_MISSING; '
               'elif [ ! -e "' + path + '/status" ]; then echo STATUS_ABSENT; '
               'elif [ ! -r "' + path + '/status" ]; then echo STATUS_DENIED; '
               'else cat "' + path + '/status" || echo READ_FAILED; fi')
    rc, out = adb("shell", command)
    if rc:
        return "SHELL_FAILURE"
    raw = out.split(b"\x00", 1)[0].strip()
    labels = {
      b"NODE_MISSING": "NODE_MISSING", b"STATUS_ABSENT": "STATUS_ABSENT",
      b"STATUS_DENIED": "STATUS_DENIED", b"READ_FAILED": "READ_FAILED",
    }
    if raw in labels:
        return labels[raw]
    if raw in ALLOWED:
        return raw.decode("ascii")
    return "OTHER_OR_EMPTY_STATUS"

def main():
    verify()
    root = None
    for candidate in ROOTS:
        rc, out = adb("shell", 'if [ -d "' + candidate + '" ]; then echo FOUND; fi')
        if rc == 0 and out.strip() == b"FOUND":
            root = candidate
            break
    print("Stage 32 — read-only live device-tree diagnosis")
    if not root:
        print("Live DT filesystem: NOT AVAILABLE")
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 2
    for label, rel in NODES.items():
        print(f"  {label}: {node_status(root, rel)}")
    print("STATUS_ABSENT means implicit DT status, not a proven functional driver.")
    print("No writes, flash, register probes or raw vendor properties.")
    print("RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Stage 32 stopped: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
