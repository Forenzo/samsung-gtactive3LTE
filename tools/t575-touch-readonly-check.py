#!/usr/bin/env python3
"""Read-only SM-T575 Linux diagnostic-console touchscreen inventory (Mac host).

Uses only cat, ls and dmesg. No device writes, module loads, flashing, reboot,
udev configuration, or input injection. Requires the established IPv6 port 23
USB diagnostic link. Does not confirm touchscreen function without touch events.
"""
import argparse
import re
import socket
import sys

COMMANDS = (
    ("Linux input devices", "cat /proc/bus/input/devices"),
    ("SPI enumerated devices", "ls /sys/bus/spi/devices"),
    ("Input class entries", "ls /sys/class/input"),
    ("Input device files", "ls /dev/input"),
    ("Himax driver module status", "ls /sys/module/himax_hx83112b"),
    ("SPI touchscreen driver binding", "ls /sys/bus/spi/drivers/himax-hx83102e-ts"),
    ("Kernel touch and SPI messages", "dmesg"),
)
FILTER = re.compile(r"himax|hx831|touch|wacom|spi21|spi.?0[.:]0|spi[-_: ]|input:|irq|probe|defer", re.I)


def request(host, port, interface, command, timeout=2.5, max_bytes=450_000):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect((host, port, 0, socket.if_nametoindex(interface)))
        connection.sendall((command + "\n").encode("utf-8"))
        data = bytearray()
        while len(data) < max_bytes:
            try:
                chunk = connection.recv(min(65536, max_bytes - len(data)))
            except socket.timeout:
                break
            if not chunk:
                break
            data.extend(chunk)
    return data.decode("utf-8", errors="replace").replace("\r", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="en7")
    parser.add_argument("--host", default="fe80::57:aff:fe00:1")
    parser.add_argument("--port", type=int, default=23)
    args = parser.parse_args()
    print("SM-T575 READ-ONLY HIMAX TOUCH INVENTORY")
    print("Only cat / ls / dmesg; no device changes.\n")
    failed = 0
    for title, command in COMMANDS:
        print(f"=== {title} | {command} ===", flush=True)
        try:
            result = request(args.host, args.port, args.interface, command)
        except OSError as exc:
            print(f"CONNECTION ERROR: {exc}\n")
            failed += 1
            continue
        if command == "dmesg":
            matching = [line for line in result.splitlines() if FILTER.search(line)]
            print("\n".join(matching[-85:]) if matching else "(no matching lines in returned dmesg)")
        else:
            print(result.strip() or "(no output)")
        print()
    print("READ-ONLY CHECK FINISHED; touchscreen activation NOT inferred.")
    if failed:
        print(f"WARNING: {failed} console request(s) failed.")
    return 1 if failed == len(COMMANDS) else 0


if __name__ == "__main__":
    sys.exit(main())
