#!/usr/bin/env python3
"""Safe, read-only SM-T575 key GPIO / watchdog STATUS snapshot.

IMPORTANT: The original interactive Volume Down hold test was RETIRED
after pressing and holding Volume Down on the physical SM-T575 entered
Samsung Download Mode (owner observation, 2026-11-18).

This replacement performs a SINGLE snapshot with NO button instructions.
Remote commands are ONLY 'peek ADDR' through the existing Linux console.
No register writes, key holds, reboot, flashing, or storage access.
The readout cannot prove a safe uniLoader fallback or watchdog recovery.
"""
import argparse
import socket
import sys

REGISTERS = [
    ("GPIO GPA0_DAT baseline (not a confirmed LTE Volume Down bit)", "0x14050024"),
    ("PMU RST_STAT", "0x14060404"),
    ("PMU WDT_DISABLE", "0x14060408"),
    ("PMU WDT_MASK_RESET", "0x1406040c"),
    ("CL0 watchdog WTCON", "0x10050000"),
    ("CL0 watchdog WTCNT", "0x10050008"),
]


def ask_console(host, interface, port, command):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as connection:
        connection.settimeout(2.0)
        connection.connect((host, port, 0, socket.if_nametoindex(interface)))
        connection.sendall((command + "\n").encode("ascii"))
        chunks = []
        size = 0
        while size < 16384:
            try:
                block = connection.recv(4096)
            except socket.timeout:
                break
            if not block:
                break
            chunks.append(block)
            size += len(block)
    return b"".join(chunks).decode("utf-8", errors="replace").replace("\r", "")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interface", default="en7")
    ap.add_argument("--host", default="fe80::57:aff:fe00:1")
    ap.add_argument("--port", type=int, default=23)
    args = ap.parse_args()

    print("SM-T575 READ-ONLY REGISTER SNAPSHOT — NO BUTTON TEST")
    print("No Volume Down hold, no watchdog reset, no flash, no device writes.")
    print("Existing Download Mode must be exited manually before this can connect.\n")
    for label, address in REGISTERS:
        print(f"=== {label}: peek {address} ===", flush=True)
        try:
            data = ask_console(args.host, args.interface, args.port,
                               f"peek {address}")
        except OSError as exc:
            print(f"Connection failed: {exc}")
            return 1
        lines = [line for line in data.splitlines()
                 if not line.startswith("SM-T570 mainline")]
        print("\n".join(lines[-12:]) or "(no response)")
        print()
    print("Snapshot complete; this does not verify watchdog/Volume Down fallback.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
