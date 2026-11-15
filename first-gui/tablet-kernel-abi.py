#!/usr/bin/env python3
"""Read-only physical SM-T575 kernel ABI check via diagnostic IPv6 TCP console.

No uploads, no module insertions, no filesystem mounts, no device changes.
Prints the running kernel release and kernel module versioning settings where
available. Kernel source CI module builds MUST be compared with these values.
"""
import argparse
import socket
import sys

HOST = "fe80::57:aff:fe00:1"
FILES = (
    "/proc/sys/kernel/osrelease",
    "/proc/version",
    "/proc/filesystems",
    "/proc/modules",
    "/proc/cmdline",
    "/proc/sys/kernel/modules_disabled",
    "/proc/sys/kernel/tainted",
)


def prompt(s):
    chunks = bytearray()
    while not chunks.endswith(b"\n> "):
        b = s.recv(8192)
        if not b:
            raise ConnectionError("diagnostic console disconnected")
        chunks.extend(b)
        if len(chunks) > 65536:
            raise ValueError("diagnostic response unexpectedly large")
    return chunks.decode(errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="en7")
    args = parser.parse_args()
    idx = socket.if_nametoindex(args.interface)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(12)
        s.connect((HOST, 23, 0, idx))
        greeting = prompt(s)
        if "bring-up console" not in greeting:
            raise RuntimeError("unexpected console; refusing requests")
        print("SM-T575 READ-ONLY ABI REPORT")
        for path in FILES:
            s.sendall(f"cat {path}\n".encode())
            value = prompt(s)
            if value.endswith("\n> "):
                value = value[:-3]
            if path == "/proc/filesystems":
                value = "\n".join(line for line in value.splitlines() if "nfs" in line.lower()) or "(no NFS filesystem currently registered)"
            print(f"{path}:\n{value.strip()}")
    print("No device changes made.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, ConnectionError) as exc:
        sys.exit(f"ERROR: {exc}")
