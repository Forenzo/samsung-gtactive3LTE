#!/usr/bin/env python3
"""Stage five checksum-verified NFS modules in the tablet's RAM (NO INSMOD).

Uploads via the known USB IPv6 diagnostic console. Does NOT attempt module
insertion, mounts, reboots, kexec, flashing, or storage writes. This does not
prove kernel ABI compatibility. A successful upload is NOT permission to load.
"""
import argparse
import hashlib
from pathlib import Path
import socket
import sys
import zipfile

ORDER = ("sunrpc", "grace", "lockd", "nfs", "nfsv3")
VERMAGIC = b"vermagic=7.3.0 SMP preempt mod_unload aarch64\x00"
HOST = "fe80::57:aff:fe00:1"
TARGET_PREFIX = "/t575-test-"


def prompt(sock):
    data = bytearray()
    while not data.endswith(b"\n> "):
        chunk = sock.recv(8192)
        if not chunk:
            raise RuntimeError("Diagnostic console disconnected")
        data.extend(chunk)
        if len(data) > 65536:
            raise RuntimeError("Diagnostic reply exceeds safety limit")
    return bytes(data)


def validate(archive):
    if not archive.is_file():
        raise ValueError(f"Missing artifact ZIP: {archive}")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entry")
        digest_map = {}
        for line in z.read("SHA256SUMS").decode("ascii").splitlines():
            tokens = line.split()
            if len(tokens) != 2:
                raise ValueError("Invalid SHA256SUMS record")
            if tokens[1] in digest_map:
                raise ValueError("Duplicate manifest entry")
            digest_map[tokens[1]] = tokens[0].lower()
        expected = {n for n in names if n.startswith("modules/") and n.endswith(".ko")}
        if expected != set(digest_map):
            raise ValueError("Checksum manifest doesn't match module list")
        for name in expected:
            blob = z.read(name)
            if hashlib.sha256(blob).hexdigest() != digest_map[name]:
                raise ValueError(f"Checksum mismatch: {name}")
        result = []
        for name in ORDER:
            member = f"modules/{name}.ko"
            if member not in expected:
                raise ValueError(f"Missing required NFS module: {member}")
            blob = z.read(member)
            if (blob[:6] != b"\x7fELF\x02\x01"
                    or int.from_bytes(blob[18:20], "little") != 183
                    or VERMAGIC not in blob):
                raise ValueError(f"Wrong ELF architecture or vermagic: {member}")
            result.append((name, blob))
        return len(expected), result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_zip", type=Path)
    parser.add_argument("--interface", default="en7")
    args = parser.parse_args()
    count, modules = validate(args.artifact_zip.expanduser())
    print(f"PASS: artifact manifest verifies {count} modules; staging only five.", flush=True)
    print("This operation writes to diagnostic initramfs RAM only; DOES NOT load modules.", flush=True)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(30)
        s.connect((HOST, 23, 0, socket.if_nametoindex(args.interface)))
        if b"bring-up console" not in prompt(s):
            raise RuntimeError("Unrecognized console")
        for name, data in modules:
            remote = TARGET_PREFIX + name + ".ko"
            s.sendall(f"put {remote} {len(data)}\n".encode() + data)
            response = prompt(s).decode(errors="replace")
            if f"ok {len(data)}\n" not in response:
                raise RuntimeError(f"{name}: incomplete or rejected upload: {response}")
            print(f"STAGED: {name}.ko ({len(data)} bytes) to {remote}", flush=True)
    print("STAGING COMPLETE. Modules have NOT been loaded. Do not run insmod.", flush=True)
    print("Further kernel compatibility and physical recovery checks remain required.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        sys.exit(f"ERROR: {exc}")
