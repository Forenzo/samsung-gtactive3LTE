#!/usr/bin/env python3
"""ONE MODULE ONLY: explicitly load staged sunrpc.ko into SM-T575 diagnostic Linux.

WARNING: finit_module executes kernel code. An ABI mismatch can crash the tablet.
No flash, mount, reboot, follow-up modules, automatic retries, or recovery claims.
Requires --load-sunrpc (exact) as owner's deliberate opt-in.
"""
import argparse
import socket
import sys

HOST = "fe80::57:aff:fe00:1"
MODULE = "/t575-test-sunrpc.ko"


def prompt(sock, limit=65536):
    response = bytearray()
    while not response.endswith(b"\n> "):
        part = sock.recv(8192)
        if not part:
            raise ConnectionError("Console closed before prompt (possible device instability)")
        response.extend(part)
        if len(response) > limit:
            raise ValueError("Unusually large console response")
    return response.decode(errors="replace")


def ask(sock, cmd):
    sock.sendall(cmd.encode("ascii") + b"\n")
    return prompt(sock)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interface", default="en7")
    ap.add_argument("--load-sunrpc", action="store_true",
                    help="Explicitly insert staged sunrpc.ko; may crash the kernel")
    args = ap.parse_args()
    if not args.load_sunrpc:
        ap.error("No action taken. Explicit --load-sunrpc is required.")
    idx = socket.if_nametoindex(args.interface)
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        sock.settimeout(12)
        sock.connect((HOST, 23, 0, idx))
        if "bring-up console" not in prompt(sock):
            raise RuntimeError("Unexpected diagnostic console service")
        release = ask(sock, "cat /proc/sys/kernel/osrelease")
        if not release.startswith("7.3.0"):
            raise RuntimeError(f"Unexpected kernel release: {release!r}")
        disabled = ask(sock, "cat /proc/sys/kernel/modules_disabled")
        taint = ask(sock, "cat /proc/sys/kernel/tainted")
        mods = ask(sock, "cat /proc/modules")
        if not disabled.strip().startswith("0") or not taint.strip().startswith("0"):
            raise RuntimeError("Module loading disabled or existing kernel taint")
        if any(line.split()[0] in {"sunrpc", "lockd", "nfs", "nfsv3"} for line in mods.splitlines() if line.split()):
            raise RuntimeError("NFS module already loaded; refusing another insertion")
        print("Preflight: kernel 7.3.0, modules allowed, taint=0, no NFS modules.", flush=True)
        sock.settimeout(30)
        print(f"Executing exactly one insertion: insmod {MODULE}", flush=True)
        reply = ask(sock, f"insmod {MODULE}")
        print(reply.strip(), flush=True)
        if not reply.startswith("ok\n"):
            raise RuntimeError("Insertion not confirmed; no further actions")
        modules = ask(sock, "cat /proc/modules")
        taint = ask(sock, "cat /proc/sys/kernel/tainted")
        found = any(line.startswith("sunrpc ") for line in modules.splitlines())
        print(f"sunrpc in /proc/modules: {found}")
        print(f"Kernel taint response: {taint.strip()}")
        if not found:
            raise RuntimeError("Insertion reported ok but module not listed")
        print("FIRST MODULE LOADED. STOP HERE; do not load others yet.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, ConnectionError) as exc:
        sys.exit(f"ERROR: {exc}")
