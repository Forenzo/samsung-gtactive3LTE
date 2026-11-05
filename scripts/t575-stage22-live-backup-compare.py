#!/usr/bin/env python3
"""Stage 22 — read-only compare of private Mac images to live SM-T575 partitions.

Streams *partition bytes* through SHA-256 into memory only, never saves
or prints them. Also hashes the existing local backups. Does not write,
reboot, flash, change Android, or contact any remote service.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

SPECS = {
    "boot": ("boot-current.img", 61_865_984),
    "dtbo": ("dtbo-current.img", 8_388_608),
}
BLOCK = 1024 * 1024

def command(*args, timeout=30):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)

def validate_device():
    p = command("adb", "devices")
    lines = p.stdout.decode("utf-8", "replace").splitlines()
    authorized = [line for line in lines[1:] if line.endswith("\tdevice")]
    if p.returncode or len(authorized) != 1:
        raise RuntimeError("Require exactly one authorized ADB device")
    model = command("adb", "shell", "getprop ro.product.model")
    if model.returncode or model.stdout.strip() != b"SM-T575":
        raise RuntimeError("SM-T575 device model gate failed")
    root = command("adb", "shell", "su -c id")
    if root.returncode or b"uid=0(" not in root.stdout:
        raise RuntimeError("Magisk root authorization failed")

def hash_local(path, expected):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected:
        raise RuntimeError(f"Local {path.name} is missing, symlinked, or wrong-sized")
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            part = f.read(BLOCK)
            if not part:
                break
            h.update(part)
    return h.hexdigest()

def hash_device(partition, expected):
    # Exact command format already used successfully for local backup.
    args = ["adb", "exec-out", "su", "-c",
            f"dd if=/dev/block/by-name/{partition} bs=1048576 2>/dev/null"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    count = 0
    try:
        while True:
            buf = proc.stdout.read(BLOCK)
            if not buf:
                break
            count += len(buf)
            if count > expected:
                proc.kill()
                proc.wait()
                raise RuntimeError(f"{partition}: device emitted more bytes than expected")
            digest.update(buf)
        errors = proc.stderr.read(4096)
        rc = proc.wait(timeout=30)
    except Exception:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        raise
    if rc != 0 or count != expected:
        raise RuntimeError(
            f"{partition}: streaming unsuccessful (exit={rc}, {count}/{expected} bytes); "
            "do not trust comparison"
        )
    if errors:
        print(f"  note: {partition} produced host diagnostic stderr (not displayed)")
    return digest.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path,
                        default=Path.home() / "Downloads" / "SM-T575-Recovery")
    args = parser.parse_args()
    validate_device()
    print("Stage 22 — private local backup vs live partition SHA-256")
    all_match = True
    for name, (filename, size) in SPECS.items():
        local = hash_local(args.folder.expanduser() / filename, size)
        live = hash_device(name, size)
        ok = local == live
        print(f"  {name}: {'EXACT BYTE MATCH' if ok else 'MISMATCH'} ({size} bytes)")
        all_match &= ok
    print("Comparison:", "PASS" if all_match else "FAIL — review backup before proceeding")
    print("RESTORE/BOOT GATE: BLOCKED (flashing and non-wiping recovery not validated).")
    print("Only local hashes printed as match verdicts; no images uploaded or written.")
    if not all_match:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Stage 22 STOPPED: {exc}", file=sys.stderr)
        sys.exit(1)
