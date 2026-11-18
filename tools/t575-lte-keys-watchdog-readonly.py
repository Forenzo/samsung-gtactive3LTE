#!/usr/bin/env python3
"""Read-only SM-T575 key and watchdog register observations over USB IPv6.

Designed for the already-running Linux diagnostic on physical SM-T575.
The remote diagnostic console receives ONLY 'peek ADDR' commands.
NO 'poke', 'write', 'reboot', 'insmod', flashing, or filesystem changes.

The resulting readings are evidence for auditing the LTE uniLoader's
proposed Volume Down fallback. This DOES NOT test watchdog reset behavior.
"""
import argparse
import re
import socket
import sys

# The Wi-Fi uniLoader source assumes GPA0_DAT and PMU/cluster-0 watchdog.
REGISTERS = [
    ("GPIO GPA0_DAT (Wi-Fi assumed Volume Down bit 4)", "0x14050024"),
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


def read_register(label, address, args):
    print(f"\n  {label} | peek {address}")
    data = ask_console(args.host, args.interface, args.port, f"peek {address}")
    # Keep raw output: register presentation differs among diagnostic builds.
    lines = [x for x in data.splitlines() if not x.startswith("SM-T570 mainline")]
    print("\n".join(lines[-12:]) or "(no response)")
    # Parse conservatively only when an explicit hexadecimal address:value
    # response exists. Never use an ambiguous hex number as proof of a key.
    found = re.findall(r"(?:0x)?[0-9a-fA-F]{8,16}\s*[:=]\s*(0x[0-9a-fA-F]{1,16})", data)
    return int(found[-1], 16) if found else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interface", default="en7")
    ap.add_argument("--host", default="fe80::57:aff:fe00:1")
    ap.add_argument("--port", type=int, default=23)
    args = ap.parse_args()
    print("SM-T575 USB DIAGNOSTIC: READ-ONLY KEY / PMU REGISTER CHECK")
    print("Remote commands: peek only. No persistent changes or reboots.")
    try:
        input("\nRelease ALL physical keys, then press Return on your Mac...")
        released = read_register(*REGISTERS[0], args)
        input("\nHold VOLUME DOWN on the tablet, then press Return on your Mac (keep holding)...")
        voldown = read_register(*REGISTERS[0], args)
        input("\nRelease all keys and hold VOLUME UP, then press Return on your Mac (keep holding)...")
        volup = read_register(*REGISTERS[0], args)
        input("\nRelease all keys. Press Return to inspect read-only watchdog registers...")
        for label, address in REGISTERS[1:]:
            read_register(label, address, args)
    except (OSError, EOFError, KeyboardInterrupt) as exc:
        print(f"\nStopped: {exc}")
        return 1

    print("\n=== KEY OBSERVATIONS ===")
    if released is not None and voldown is not None and volup is not None:
        print(f"Released: 0x{released:08x}; Down: 0x{voldown:08x}; Up: 0x{volup:08x}")
        delta = released ^ voldown
        print(f"GPIO bit changes on Volume Down: 0x{delta:08x}")
        if (released & 0x10) and not (voldown & 0x10) and (volup & 0x10):
            print("OBSERVED: active-low bit 4 is consistent with Volume Down.")
        else:
            print("NOT VERIFIED: the Wi-Fi uniLoader's bit-4 assumption did not clearly match.")
    else:
        print("Exact key GPIO values could not be parsed; inspect the raw console responses.")
    print("\nREAD-ONLY check complete. No watchdog reset was attempted.")
    print("These observations alone do not authorize BOOT flashing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
