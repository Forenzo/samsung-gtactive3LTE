#!/usr/bin/env python3
"""One command to request FULL Plasma Mobile on SM-T575 from macOS.

REQUIRES: a running BOOT-only SM-T575 diagnostic kernel with NFS and the
LTE GPU power-domain override, plus the owner's already-staged Plasma NFS
tree on /Volumes/T575-Plasma/rootfs. Never writes tablet partitions.

sudo python3 launch-t575-plasma.py /path/to/t575-plasma-launch-aarch64

Mac-side changes: configures an ephemeral guest account in the staged NFS
tree, starts NFS, assigns the established 10.77.57.1/30 USB host IP.
"""
from pathlib import Path
import os
import re
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path("/Volumes/T575-Plasma/rootfs")
IFACE = "en7"
ADDRESS = "fe80::57:aff:fe00:1"
DRIVERS = ("wacom_w9000", "spi-s3c64xx", "himax_hx83112b")

def run(*args, checked=True):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    if checked and p.returncode:
        raise RuntimeError(f"{' '.join(args)} failed ({p.returncode}): {p.stdout[-1500:]}")
    return p.stdout

def prepare_guest():
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Mount the T575-Plasma external disk containing rootfs")
    for name in ("etc/passwd","etc/group","usr/bin/startplasma-wayland",
                 "usr/bin/dbus-run-session","usr/bin/seatd"):
        p = ROOT / name
        if not p.is_file():
            raise RuntimeError(f"Expected Plasma rootfs file missing: {p}")
    passwd = ROOT / "etc/passwd"
    group = ROOT / "etc/group"
    if passwd.is_symlink() or group.is_symlink():
        raise RuntimeError("Refusing to modify symlinked account files")
    text = passwd.read_text()
    if not re.search(r"(?m)^t575:x:1000:1000:", text):
        if re.search(r"(?m)^[^:]+:[^:]*:1000:", text):
            raise RuntimeError("UID 1000 already in use. Review the NFS rootfs first.")
        text += "\nt575:x:1000:1000:Temporary T575 Desktop:/home/t575:/bin/sh\n"
        passwd.write_text(text)
    lines = group.read_text().splitlines()
    if not any(x.startswith("t575:x:1000:") for x in lines):
        if any(re.match(r"^[^:]+:[^:]*:1000:", x) for x in lines):
            raise RuntimeError("GID 1000 already in use. Review the NFS rootfs first.")
        lines.append("t575:x:1000:")
    out = []
    for line in lines:
        fields = line.split(":")
        if len(fields) == 4 and fields[0] in ("video", "input", "render"):
            users = [u for u in fields[3].split(",") if u]
            if "t575" not in users: users.append("t575")
            fields[3] = ",".join(users)
            line = ":".join(fields)
        out.append(line)
    group.write_text("\n".join(out) + "\n")
    machine = ROOT / "etc/machine-id"
    if machine.is_symlink():
        raise RuntimeError("Refusing symlinked /etc/machine-id")
    if not machine.exists() or not machine.read_text().strip():
        machine.write_text(uuid.uuid4().hex + "\n")
    # The tablet receives this tree as a READ-ONLY NFS export.
    # Mount-point directories MUST exist before it is mounted on Linux:
    # Linux cannot create /proc, /sys, /dev, /run, /tmp, /home, /var
    # below a read-only NFS mount. Create only directories on the Mac host.
    # Android internal partitions are never accessed.
    for name in ("proc", "sys", "dev", "run", "tmp", "home", "var"):
        p = ROOT / name
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            raise RuntimeError(f"Unsafe NFS rootfs mountpoint: {p}")
        p.mkdir(mode=0o755, exist_ok=True)
    print("Mac NFS rootfs guest and read-only mountpoints ready (Android untouched)")

def response(s, maximum=1000000):
    data = bytearray()
    while not data.endswith(b"\n> "):
        chunk = s.recv(16384)
        if not chunk: raise RuntimeError("USB diagnostic connection lost")
        data.extend(chunk)
        if len(data) > maximum: raise RuntimeError("USB response too long")
    return data[:-3].decode(errors="replace").strip()

def cmd(s, text):
    s.sendall(text.encode() + b"\n")
    return response(s)

def host_mountd_port():
    """Discover current TCP NFSv3 mountd port; macOS may change it on restart."""
    lines = run("rpcinfo", "-p", "localhost").splitlines()
    ports = []
    has_nfs_tcp3 = False
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        program, version, proto, port = fields[:4]
        if (program, version, proto) == ("100005", "3", "tcp"):
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                raise RuntimeError("Invalid NFSv3 mountd TCP port in rpcinfo")
            ports.append(int(port))
        if (program, version, proto, port) == ("100003", "3", "tcp", "2049"):
            has_nfs_tcp3 = True
    if len(set(ports)) != 1 or not has_nfs_tcp3:
        raise RuntimeError("Mac must advertise NFSv3 TCP/2049 and exactly one NFSv3 mountd TCP port")
    selected = ports[0]
    print(f"Mac NFSv3 mountd TCP port (discovered via rpcinfo): {selected}")
    return selected

def start_desktop(s, binary, mountport):
    raw = binary.read_bytes()
    if binary.is_symlink() or raw[:4] != b"\x7fELF" or len(raw) > 5_000_000:
        raise RuntimeError("Invalid launcher executable")
    if int.from_bytes(raw[18:20], "little") != 183:
        raise RuntimeError("Launcher is not ARM64")
    s.sendall(f"put /t575-plasma-launch {len(raw)}\n".encode())
    s.sendall(raw)
    status = response(s)
    if f"ok {len(raw)}" not in status:
        raise RuntimeError("Upload failure: " + status)
    loaded = cmd(s,"cat /proc/modules")
    available = cmd(s,"ls /lib/modules").splitlines()
    for driver in DRIVERS:
        normalized = driver.replace("-", "_")
        if re.search(rf"(?m)^{re.escape(normalized)}\s", loaded):
            print("Already loaded:", driver); continue
        if driver + ".ko" not in available:
            raise RuntimeError("Input driver missing: " + driver)
        result = cmd(s, "insmod /lib/modules/" + driver + ".ko")
        if not result.startswith(("ok","already loaded")):
            raise RuntimeError("Could not initialize " + driver + ": " + result)
        print("Input driver ready:", driver)
    print(cmd(s,f"run /t575-plasma-launch --start {mountport}"))
    print("Attempting Plasma Mobile; saving a log trail on this Mac in case the tablet resets...", flush=True)
    capture = Path.cwd() / ("t575-plasma-capture-" + time.strftime("%Y%m%d-%H%M%S") + ".log")
    capture.touch(exist_ok=False)
    capture.chmod(0o644)
    print(f"Mac evidence file: {capture}", flush=True)
    latest = ""
    disconnected = False
    # Each snapshot is written to the Mac BEFORE waiting for another sample.
    # The tablet's /t575-plasma-desktop.log is RAM-only and lost on reboot.
    s.settimeout(12)
    for sample in range(1, 9):
        time.sleep(8)
        try:
            latest = cmd(s, "cat /t575-plasma-desktop.log")
            with capture.open("a", encoding="utf-8") as fp:
                fp.write(f"\n========== CAPTURE {sample} ({time.strftime('%H:%M:%S')}) ==========\n")
                fp.write(latest + "\n")
            print(f"Captured startup log snapshot {sample}/8 ({len(latest)} characters)", flush=True)
            if latest.strip() == "error":
                print("Tablet reported no current log; it may have restarted.", flush=True)
                break
        except (OSError, RuntimeError) as ex:
            disconnected = True
            with capture.open("a", encoding="utf-8") as fp:
                fp.write(f"\nUSB console lost after snapshot {sample-1}: {type(ex).__name__}: {ex}\n")
            print(f"USB diagnostic console lost: {type(ex).__name__}: {ex}", flush=True)
            print("Saved earlier log snapshots remain on the Mac.", flush=True)
            break
    print("\n=== LAST AVAILABLE PLASMA STARTUP LOG ===")
    print(latest[-40000:] if latest else "(No startup output captured)")
    print("\nMac capture saved at:", capture)
    if disconnected:
        print("Tablet reboot or USB disconnect detected. Check screen and preserve Mac capture.")
    elif "Starting Cage (seatd / DRM)" in latest:
        print("Cage startup reached; look for Plasma graphical desktop on tablet.")
    elif "FAIL:" in latest:
        print("Desktop setup reported a failure; inspect full Mac capture.")
    else:
        print("Inspect capture for last startup stage; no flash or wipe was performed.")

def main():
    if sys.platform != "darwin":
        raise RuntimeError("This helper targets the owner's macOS NFS host")
    if os.geteuid():
        raise RuntimeError("Run with sudo to configure macOS NFS and USB IPv4")
    if len(sys.argv) != 2:
        raise RuntimeError("Usage: sudo python3 launch-t575-plasma.py ./t575-plasma-launch-aarch64")
    executable = Path(sys.argv[1]).expanduser().resolve(strict=True)
    prepare_guest()
    if "10.77.57.1" not in run("ifconfig",IFACE):
        run("ifconfig",IFACE,"inet","10.77.57.1",
            "netmask","255.255.255.252","alias")
    run("nfsd","start")
    if str(ROOT) not in run("showmount","-e","localhost"):
        raise RuntimeError("NFS export not advertised: check the existing read-only /etc/exports, then sudo nfsd update")
    mountport = host_mountd_port()
    print("Mac USB/NFS host ready")
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(30)
        s.connect((ADDRESS,23,0,socket.if_nametoindex(IFACE)))
        greeting = response(s)
        if "bring-up console" not in greeting:
            raise RuntimeError("Unexpected USB service. Refusing to upload.")
        start_desktop(s, executable, mountport)
    print("No bootloader, Android BOOT, DTBO or userdata writes were issued.")

if __name__ == "__main__":
    try: main()
    except (OSError, RuntimeError, ValueError) as ex:
        sys.exit("STOP: " + str(ex))
