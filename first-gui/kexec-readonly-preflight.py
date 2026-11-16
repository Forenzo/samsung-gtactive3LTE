#!/usr/bin/env python3
"""Passive diagnostics for a possible future SM-T575 temporary kernel handoff.

This script NEVER calls kexec, inserts modules, uploads files, reboots,
changes configurations, or touches partitions. A PASS does not authorize boot.
"""
import argparse
import socket
import sys

HOST = "fe80::57:aff:fe00:1"
PATHS = (
    "/proc/sys/kernel/osrelease",
    "/proc/cmdline",
    "/proc/sys/kernel/kexec_load_disabled",
    "/sys/kernel/kexec_loaded",
    "/proc/sys/kernel/tainted",
    "/proc/filesystems",
)


def prompt(sock):
    data = bytearray()
    while not data.endswith(b"\n> "):
        chunk = sock.recv(8192)
        if not chunk:
            raise RuntimeError("Diagnostic console unexpectedly disconnected")
        data.extend(chunk)
        if len(data) > 65536:
            raise RuntimeError("Unexpectedly large console response")
    return data[:-3].decode(errors="replace")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interface", default="en7")
    args = ap.parse_args()
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        sock.settimeout(15)
        sock.connect((HOST, 23, 0, socket.if_nametoindex(args.interface)))
        if "bring-up console" not in prompt(sock):
            raise RuntimeError("Unexpected console; no commands issued")
        print("READ-ONLY ARM64 KEXEC PREFLIGHT")
        for path in PATHS:
            sock.sendall(f"cat {path}\n".encode())
            value = prompt(sock).strip()
            if path == "/proc/filesystems":
                value = "\n".join(x for x in value.splitlines() if "nfs" in x.lower()) or "(NFS not registered)"
            elif value == "error":
                value = "(not exposed by running kernel / path unavailable)"
            print(f"{path}: {value}")
    print("PASS: read-only queries completed.")
    print("IMPORTANT: this DOES NOT establish KEXEC_FILE support, DTB handoff,")
    print("watchdog behavior, bootloader reset, nor successful recovery.")
    print("NO kernel handoff or hardware change attempted.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        sys.exit(f"ERROR: {exc}")
