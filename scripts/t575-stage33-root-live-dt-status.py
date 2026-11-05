#!/usr/bin/env python3
"""Stage 33: read four allowlisted SM-T575 runtime DT statuses via Magisk root.

Root is used only to READ status properties that unprivileged ADB cannot
access. Does not change permissions, SELinux, partitions, software or files.
No secrets, identifying DT properties or raw binary data are reported.
"""
import subprocess
import shlex
import sys

NODES = {
    "DSIM1": "dsim@0x16090000",
    "Sound": "sound",
    "TAS2562": "hsi2c@108C0000/tas2562@4c",
    "RT5510": "hsi2c@108C0000/rt5510@34",
}
ROOTS = ("/proc/device-tree", "/sys/firmware/devicetree/base")
ALLOWED = {b"okay", b"ok", b"disabled", b"reserved", b"fail", b"fail-sss"}

def adb(*args):
    p = subprocess.run(["adb", *args], capture_output=True, timeout=20)
    return p.returncode, p.stdout

def root_command(command):
    # Quote one complete command for the Android remote shell so Magisk su
    # receives exactly one -c argument, even when it contains spaces or ';'.
    return adb("shell", "su -c " + shlex.quote(command))

def verify():
    rc, out = adb("devices")
    if rc or sum(x.endswith(b"\tdevice") for x in out.splitlines()[1:]) != 1:
        raise RuntimeError("require exactly one authorized ADB device")
    rc, model = adb("shell", "getprop", "ro.product.model")
    if rc or model.strip() != b"SM-T575":
        raise RuntimeError("device model is not SM-T575")
    rc, who = root_command("id")
    if rc or b"uid=0(" not in who:
        raise RuntimeError("Magisk root access not granted")

def run_root_read(path):
    # Only fixed path constants reach the device. Shell has no variable data
    # coming from the user, repository, or device.
    command = ('if [ ! -d "' + path + '" ]; then printf NODE_MISSING; '
               'elif [ ! -e "' + path + '/status" ]; then printf STATUS_ABSENT; '
               'else cat "' + path + '/status" || printf READ_FAILED; fi')
    rc, out = root_command(command)
    if rc:
        return "READ_FAILED"
    label = out.split(b"\x00", 1)[0].strip()
    if label in ALLOWED:
        return label.decode("ascii")
    if label in (b"NODE_MISSING", b"STATUS_ABSENT", b"READ_FAILED"):
        return label.decode("ascii")
    return "OTHER_STATUS_OR_DENIED"

def main():
    verify()
    print("Stage 33 — read-only root-assisted live DT statuses")
    root = None
    for candidate in ROOTS:
        rc, out = root_command('if [ -d "' + candidate + '" ]; then printf FOUND; fi')
        if rc == 0 and out.strip() == b"FOUND":
            root = candidate
            break
        print("  root path probe: no positive match (command status " + ("OK" if rc == 0 else "FAILED") + ")")
    if root is None:
        print("Live DT path NOT CONFIRMED by quoted Magisk root probes")
        print("Stage 32 did expose the runtime DT without root; no hardware conclusion.")
        print("RESTORE/BOOT/FLASH GATE: BLOCKED")
        return 2
    for label, rel in NODES.items():
        print(f"  {label}: {run_root_read(root + '/' + rel)}")
    print("Compares status properties only; no driver/boot claims.")
    print("No writes, MMIO access, or reboot. RESTORE/BOOT/FLASH GATE: BLOCKED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as err:
        print(f"Stage 33 STOPPED: {type(err).__name__}", file=sys.stderr)
        sys.exit(1)
