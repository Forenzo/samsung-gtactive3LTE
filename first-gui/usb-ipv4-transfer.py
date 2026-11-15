#!/usr/bin/env python3
"""Upload or execute the verified USB-only IPv4 tool via T575 diagnostic console.

This program communicates ONLY with the already-running TCP/23 diagnostic
console using scoped IPv6. It never flashes, mounts disks or changes NFS.
Use --upload first, then --apply in a separate explicit invocation.
"""
import argparse
import hashlib
import pathlib
import socket
import sys
import zipfile

GUEST = "fe80::57:aff:fe00:1"
REMOTE_PATH = "/t575-usb-ipv4"
FILE = "t575-usb-ipv4-aarch64"


def command(sock, payload, *, timeout=20):
    sock.settimeout(timeout)
    buf = bytearray()
    sock.sendall(payload)
    while not buf.endswith(b"\n> "):
        data = sock.recv(65536)
        if not data:
            break
        buf.extend(data)
        if len(buf) > 1024 * 1024:
            raise RuntimeError("Console response unexpectedly long")
    return bytes(buf)


def read_prompt(sock):
    sock.settimeout(12)
    buf = bytearray()
    while not buf.endswith(b"\n> "):
        data = sock.recv(8192)
        if not data:
            raise RuntimeError("Diagnostic console disconnected")
        buf.extend(data)
        if len(buf) > 65536:
            raise RuntimeError("Console greeting too long")
    return bytes(buf)


def extract_verified(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if not {FILE, "SHA256SUMS"} <= names:
            raise ValueError("Expected executable and SHA256SUMS in GitHub artifact ZIP")
        content = z.read(FILE)
        manifest = z.read("SHA256SUMS").decode()
    # sha256sum was run as 'sha256sum dist/BINARY', so the manifest
    # contains 'dist/t575-usb-ipv4-aarch64' although the artifact ZIP
    # stores the binary at its basename.
    matches = [parts for x in manifest.splitlines()
               if (parts := x.split()) and pathlib.PurePosixPath(parts[-1]).name == FILE]
    if len(matches) != 1:
        raise ValueError("Manifest must contain exactly one binary checksum")
    digest = hashlib.sha256(content).hexdigest()
    if matches[0][0].lower() != digest:
        raise ValueError("SHA256 mismatch; refusing upload")
    if content[:4] != b"\x7fELF" or content[4] != 2 or content[5] != 1 or int.from_bytes(content[18:20], "little") != 183:
        raise ValueError("Binary is not little-endian 64-bit AArch64 ELF")
    print(f"Verified ARM64 executable: {len(content)} bytes SHA256 {digest}")
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--upload", type=pathlib.Path, metavar="GITHUB_ARTIFACT_ZIP")
    actions.add_argument("--apply", action="store_true", help="Explicitly execute uploaded IPv4 helper")
    parser.add_argument("--interface", default="en7", help="Mac interface for existing NCM diagnostic link")
    args = parser.parse_args()

    if args.upload is not None and not args.upload.expanduser().is_file():
        raise ValueError(f"Artifact ZIP file not found: {args.upload}")
    payload = extract_verified(args.upload.expanduser()) if args.upload else None
    scope = socket.if_nametoindex(args.interface)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        sock.settimeout(12)
        sock.connect((GUEST, 23, 0, scope))
        greeting = read_prompt(sock)
        if b"bring-up console" not in greeting:
            raise RuntimeError("Unexpected TCP service; refusing commands")
        print(f"Connected to tablet diagnostic console via {args.interface}")
        if payload is not None:
            # The server receives exactly LEN bytes before issuing the next prompt.
            reply = command(sock, f"put {REMOTE_PATH} {len(payload)}\n".encode() + payload, timeout=35)
            print(reply.decode(errors="replace").strip())
            if f"ok {len(payload)}".encode() not in reply:
                raise RuntimeError("Upload not acknowledged in full; do not run")
            print("UPLOAD COMPLETE. To configure usb0 on the tablet, use --apply separately.")
        else:
            reply = command(sock, f"run {REMOTE_PATH} --apply-usb-only\n".encode(), timeout=75)
            result = reply.decode(errors="replace")
            print(result.strip())
            if "USB0 IPv4: 10.77.57.2" not in result or "run: exit 0 signal 0" not in result:
                raise RuntimeError("IPv4 helper did not confirm success")
            print("Tablet usb0 configured. Mac-side IPv4 is NOT configured by this tool.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        sys.exit(f"ERROR: {exc}")
