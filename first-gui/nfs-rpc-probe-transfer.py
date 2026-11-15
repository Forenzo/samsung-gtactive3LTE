#!/usr/bin/env python3
"""Verify, upload, and run a read-only NFS RPC probe on the Active3.

No NFS mounts, IP changes, exports, partition writes or reboots.
Requires the proven diagnostic Linux TCP/23 console over USB IPv6 and
the build-only ZIP from the t575-nfs-tcp-probe workflow.
"""
import argparse
import hashlib
from pathlib import Path
import socket
import sys
import zipfile

BINARY = "t575-nfs-rpc-probe-aarch64"
REMOTE_PATH = "/t575-nfs-rpc-probe"
HOST = "fe80::57:aff:fe00:1"


def until_prompt(sock, limit=65536):
    buf = bytearray()
    while not buf.endswith(b"\n> "):
        part = sock.recv(8192)
        if not part:
            raise RuntimeError("Diagnostic console disconnected before prompt")
        buf.extend(part)
        if len(buf) > limit:
            raise RuntimeError("Unexpectedly long console response")
    return bytes(buf)


def verify(archive):
    if not archive.is_file():
        raise ValueError(f"ZIP file missing: {archive}")
    with zipfile.ZipFile(archive) as z:
        binary = z.read(BINARY)
        manifest = z.read("SHA256SUMS").decode("ascii")
    entries = [line.split() for line in manifest.splitlines() if line.split()]
    matches = [p for p in entries if len(p) == 2 and p[1].lstrip("*").split("/")[-1] == BINARY]
    if len(matches) != 1:
        raise ValueError("Expected exactly one SHA256 manifest entry for the probe")
    digest = hashlib.sha256(binary).hexdigest()
    if digest.lower() != matches[0][0].lower():
        raise ValueError("Binary checksum mismatch; no upload performed")
    if not (binary[:6] == b"\x7fELF\x02\x01" and
            int.from_bytes(binary[18:20], "little") == 183):
        raise ValueError("Expected AArch64 ELF executable")
    print(f"SHA256 verified: {digest} ({len(binary)} bytes)", flush=True)
    return binary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("artifact_zip", type=Path)
    ap.add_argument("--interface", default="en7")
    args = ap.parse_args()
    binary = verify(args.artifact_zip.expanduser())
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(20)
        s.connect((HOST, 23, 0, socket.if_nametoindex(args.interface)))
        greeting = until_prompt(s)
        if b"bring-up console" not in greeting:
            raise RuntimeError("Not the recognized diagnostic console")
        print("Connected to diagnostic console.", flush=True)
        s.sendall(f"put {REMOTE_PATH} {len(binary)}\n".encode() + binary)
        response = until_prompt(s).decode(errors="replace")
        if f"ok {len(binary)}\n" not in response:
            raise RuntimeError(f"Upload failed: {response}")
        print("Uploaded into temporary Linux RAM; running read-only NFS RPC metadata test...", flush=True)
        s.settimeout(30)
        s.sendall(f"run {REMOTE_PATH}\n".encode())
        response = until_prompt(s).decode(errors="replace")
        print(response.strip())
        if "PASS: export authorization and read-only NFS metadata access work." in response and "run: exit 0 signal 0" in response:
            print("PASS: tablet obtained the export root handle and read NFS metadata.")
        else:
            print("NFS RPC authorization or metadata check did not pass. No NFS mount attempted.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, KeyError) as exc:
        sys.exit(f"ERROR: {exc}")
