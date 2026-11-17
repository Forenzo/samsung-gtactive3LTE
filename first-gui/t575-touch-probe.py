#!/usr/bin/env python3
"""Read-only SM-T575 diagnostic console touch/udev probe from macOS.

Requires the existing BOOT-only diagnostic Linux and USB NCM connection.
NO device writes, no installs, no Android storage access, no root needed.
Run while the Plasma Mobile welcome screen is displayed.
"""
import socket
import sys

IFACE = "en7"
TARGET = "fe80::57:aff:fe00:1"
PORT = 23
MAX = 2_000_000

def reply(sock):
    out = bytearray()
    while not out.endswith(b"\n> "):
        data = sock.recv(16384)
        if not data:
            raise RuntimeError("Diagnostic connection closed")
        out.extend(data)
        if len(out) > MAX:
            raise RuntimeError("Diagnostic reply too large")
    return out[:-3].decode("utf-8", "replace").strip()

def request(sock, line):
    sock.sendall((line + "\n").encode())
    return reply(sock)

def main():
    if sys.platform != "darwin":
        raise RuntimeError("This utility is for the established Mac USB diagnostic connection")
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        sock.settimeout(28)
        scope = socket.if_nametoindex(IFACE)
        sock.connect((TARGET, PORT, 0, scope))
        greeting = reply(sock)
        if "bring-up console" not in greeting:
            raise RuntimeError("Unexpected service: refusing commands")
        checks = [
            ("Kernel input devices (names and handlers)", "cat /proc/bus/input/devices"),
            ("Input module status", "cat /proc/modules"),
            ("Himax driver name", "cat /sys/class/input/event2/device/name"),
            ("Wacom driver name", "cat /sys/class/input/event1/device/name"),
            ("Udev input database entries", "ls /mnt/t575-plasma-gui-v2/run/udev/data"),
            ("Himax event2 udev properties", "cat /mnt/t575-plasma-gui-v2/run/udev/data/c13:66"),
            ("Wacom event1 udev properties", "cat /mnt/t575-plasma-gui-v2/run/udev/data/c13:65"),
        ]
        for title, cmd in checks:
            print(f"\n=== {title} ===", flush=True)
            data = request(sock, cmd)
            if cmd == "cat /proc/modules":
                lines = [x for x in data.splitlines()
                         if any(term in x.lower() for term in
                                ("himax", "wacom", "spi", "udev", "input"))]
                data = "\n".join(lines) or "(No matching modules)"
            print(data, flush=True)
        print("\n=== TOUCH TEST: Tap and swipe on the GLASS repeatedly NOW ===", flush=True)
        print("Monitoring /dev/input/event2 for up to 10 seconds. No touch settings are changed.",flush=True)
        data = request(sock, "evread /dev/input/event2 40 10")
        print(data, flush=True)
        found = any(x.strip().startswith("3 ") or " 3 " in x for x in data.splitlines())
        if found:
            print("\nRESULT: ABS touch-position events reached the Linux kernel.")
            print("Next fix should target udev/libinput/seat classification or screen rotation.")
        elif "name:" in data:
            print("\nRESULT: event2 opened, but no ABS position events were captured.")
            print("The controller may not be reporting contact; inspect driver probe and interrupt logs.")
        else:
            print("\nRESULT: event2 was not readable or the console failed.")
        print("No flash, partition write, or reboot occurred.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as err:
        sys.exit("Probe stopped: " + str(err))
