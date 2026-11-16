#!/usr/bin/env python3
"""Read-only diagnostics after the FIRST NFS module insertion failed.

Queries existing T575 diagnostic TCP/23 console. No upload, insmod,
rmmod, mount, reboot, write, or flash operations are performed.
"""
import argparse
import socket
import sys

HOST = "fe80::57:aff:fe00:1"
STAGED = "t575-test-sunrpc.ko"


def until_prompt(sock, limit=262144):
    data = bytearray()
    while not data.endswith(b"\n> "):
        chunk = sock.recv(16384)
        if not chunk:
            raise ConnectionError("Diagnostic console connection closed")
        data.extend(chunk)
        if len(data) > limit:
            raise RuntimeError("Diagnostic console response exceeded limit")
    return data.decode("utf-8", errors="replace")[:-3]


def ask(sock, command):
    sock.sendall(command.encode("ascii") + b"\n")
    return until_prompt(sock)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interface", default="en7")
    args = ap.parse_args()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(15)
        s.connect((HOST, 23, 0, socket.if_nametoindex(args.interface)))
        if "bring-up console" not in until_prompt(s):
            raise RuntimeError("Unexpected TCP service")
        names = ask(s, "ls /").splitlines()
        print(f"STAGED SUNRPC FILE PRESENT IN ROOT DIRECTORY: {STAGED in names}")
        print("RUNNING KERNEL:", ask(s, "cat /proc/sys/kernel/osrelease").strip())
        modules = ask(s, "cat /proc/modules")
        selected = [line for line in modules.splitlines()
                    if line.startswith(("sunrpc ", "grace ", "lockd ", "nfs ", "nfsv3 "))]
        print("NFS MODULES CURRENTLY LOADED:", selected or "(none)")
        print("KERNEL TAINT:", ask(s, "cat /proc/sys/kernel/tainted").strip())
        print("\nRELEVANT RECENT KERNEL LOG LINES:")
        log = ask(s, "dmesg").splitlines()
        needles = ("sunrpc", "unknown symbol", "disagrees about version",
                   "invalid module", "module verification", "module_layout",
                   "unknown relocation", "module", "symbol", "nfs")
        matched = [line for line in log if any(word in line.lower() for word in needles)]
        if matched:
            print("\n".join(matched[-55:]))
        else:
            print("(no matching lines in the kernel log)")
        print("\nREAD-ONLY DIAGNOSTICS COMPLETE; no insertion attempted.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ConnectionError, RuntimeError, ValueError) as exc:
        sys.exit(f"ERROR: {exc}")
