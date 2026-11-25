#!/usr/bin/env python3
"""Client for the SM-T570 USB debug console (TCP 23 over the USB NCM link).

The same protocol is served by the gtactive3-mainline bring-up Linux (the
installer's live environment, initramfs/init.c) and, in Duranium dev
images, by gta3-console: a "> " prompt, one command per line.
  cat PATH          streams PATH (a block device: the whole device)
  put PATH LEN      then LEN raw bytes; answers "ok <received>"
  write PATH VALUE  answers "ok" / "error"
  evread PATH N S   input events "sec.usec type code value", "timeout"

usage:
  console.py probe                       prints "bringup" or "duranium VERSION VARIANT"
  console.py cmd LINE [TIMEOUT]          prints the answer
  console.py put LOCAL|- REMOTE LEN [LABEL]
  console.py get REMOTE LEN SHAFILE [LABEL]   raw bytes to stdout, sha256 to SHAFILE
  console.py hash REMOTE LEN [LABEL]     sha256 of the first LEN bytes
  console.py key DEV SECS                waits for a key press: prints its code,
                                         "timeout", or exits 3 if the console went away

Address: $GTA3_CONSOLE_ADDR (set locally; include IPv6 interface scope);
port $GTA3_CONSOLE_PORT (default 23).

Duranium dev images with duranium-usb-debug r7 or newer have no console on
port 23 (only with duranium.usb_debug=open): there probe, cmd, put, get and
hash go over the key-only USB debug ssh instead, with the paired key
$GTA3_SSH_KEY (default ~/.ssh/id_ed25519_gta3_usb, see scripts/tab-ssh
--pair). The live environment keeps the console.
"""
import hashlib
import os
import shlex
import socket
import subprocess
import sys
import time

PORT = int(os.environ.get("GTA3_CONSOLE_PORT", "23"))


def address():
    a = os.environ.get("GTA3_CONSOLE_ADDR")
    if not a:
        sys.exit("Set GTA3_CONSOLE_ADDR locally, including the USB interface scope")
    return a


def connect(timeout=10):
    s = socket.create_connection((address(), PORT), timeout=timeout)
    s.settimeout(30)
    buf = b""
    while not buf.endswith(b"> "):
        d = s.recv(65536)
        if not d:
            sys.exit("console closed before the prompt")
        buf += d
    return s


def ssh_key():
    k = os.environ.get("GTA3_SSH_KEY", os.path.expanduser("~/.ssh/id_ed25519_gta3_usb"))
    return k if os.path.exists(k) else None


def ssh_argv(shell_cmd):
    home = os.path.expanduser("~")
    return ["ssh", "-i", ssh_key(), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", f"UserKnownHostsFile={home}/.ssh/known_hosts_gta3",
            "-o", "StrictHostKeyChecking=accept-new",
            f"root@{address()}", shell_cmd]


def ssh_shell(line):
    """A console command as a shell command (the ones the installer sends
    to a booted Duranium)."""
    w = line.split(None, 2)
    if w and w[0] == "run":
        return line[4:]
    if w and w[0] == "write" and len(w) == 3:
        return f"printf '%s\\n' {shlex.quote(w[2])} > {shlex.quote(w[1])} && echo ok || echo error"
    if w[:2] == ["reboot", "download"]:
        return "systemctl reboot --reboot-argument=download"
    return line


def ssh_stream(remote, n, sink, label=None):
    """The first n bytes of remote over ssh; returns their sha256."""
    p = subprocess.Popen(ssh_argv(f"head -c {int(n)} {shlex.quote(remote)}"),
                         stdout=subprocess.PIPE)
    h, got = hashlib.sha256(), 0
    prog = Progress(label or os.path.basename(remote), n) if n > 1 << 20 else None
    while got < n:
        d = p.stdout.read(min(1 << 20, n - got))
        if not d:
            break
        h.update(d)
        sink(d)
        got += len(d)
        if prog:
            prog(got)
    if p.wait() != 0:
        sys.exit("SSH transfer failed")
    if prog:
        prog(got, True)
    if got != n:
        sys.exit(f"ssh: short read of {remote}: {got} of {n} bytes")
    return h.hexdigest()


def ssh_put(local, remote, n):
    if n < 0:
        raise ValueError("Invalid transfer length")

    q = shlex.quote(remote)

    if remote.startswith("/dev/"):
        sh = f"dd of={q} bs=1M iflag=fullblock conv=fsync"
    else:
        sh = f"cat > {q} && sync"

    f = sys.stdin.buffer if local == "-" else open(local, "rb")
    proc = subprocess.Popen(ssh_argv(sh), stdin=subprocess.PIPE)
    digest = hashlib.sha256()
    sent = 0

    try:
        while sent < n:
            data = f.read(min(1 << 20, n - sent))
            if not data:
                raise IOError("Unexpected end of input")
            proc.stdin.write(data)
            digest.update(data)
            sent += len(data)

        proc.stdin.close()

        if proc.wait() != 0:
            raise IOError("Remote write failed")

    except BaseException:
        proc.kill()
        proc.wait()
        raise

    finally:
        if local != "-":
            f.close()

    actual = ssh_stream(remote, n, lambda data: None)

    if actual != digest.hexdigest():
        sys.exit("Remote readback checksum mismatch")

    print(f"ok {n}")
    return True


def os_release(text):
    kv = dict(ln.split("=", 1) for ln in text.splitlines() if "=" in ln)
    # Duranium images say ID=nura (upstream's name); the bring-up
    # Linux has no os-release at all
    # any Galaxy Tab Active3 variant (samsung-gtactive3wifi, -gtactive3)
    if kv.get("IMAGE_ID", "").strip('"').startswith("samsung-gtactive3"):
        return " ".join(["duranium", kv.get("IMAGE_VERSION", "?").strip('"'),
                         kv.get("VARIANT_ID", "?").strip('"')])
    return "bringup"


def via_ssh(op, a):
    if op == "probe":
        r = subprocess.run(ssh_argv("cat /etc/os-release"), capture_output=True, timeout=30)
        if r.returncode:
            sys.exit("console: neither the console nor ssh answers")
        print(os_release(r.stdout.decode(errors="replace")))
    elif op == "cmd":
        r = subprocess.run(ssh_argv(ssh_shell(a[1])), capture_output=True,
                           timeout=int(a[2]) if len(a) > 2 else 30)
        sys.stdout.write(r.stdout.decode(errors="replace"))
        sys.stderr.write(r.stderr.decode(errors="replace"))
        if r.returncode:
            sys.exit(r.returncode)
    elif op == "put":
        sys.exit(0 if ssh_put(a[1], a[2], int(a[3])) else 1)
    elif op == "get":
        out = sys.stdout.buffer
        digest = ssh_stream(a[1], int(a[2]), out.write, a[4] if len(a) > 4 else None)
        out.flush()
        with open(a[3], "w") as f:
            f.write(digest + "\n")
    elif op == "hash":
        print(ssh_stream(a[1], int(a[2]), lambda d: None, a[3] if len(a) > 3 else None))
    else:
        sys.exit(f"console: {op} needs the console (port {PORT}), which this image does not run")


def until_prompt(s):
    buf = b""
    while not buf.endswith(b"> "):
        d = s.recv(65536)
        if not d:
            break
        buf += d
    return buf[:-2] if buf.endswith(b"> ") else buf


def cmd(line, timeout=30):
    s = connect()
    s.settimeout(timeout)
    s.sendall(line.encode() + b"\n")
    out = until_prompt(s)
    s.close()
    return out.decode(errors="replace")


class Progress:
    """One line per 5 % when not on a terminal, a live line on one."""

    def __init__(self, label, total):
        self.label, self.total, self.t0 = label, total, time.time()
        self.tty = sys.stderr.isatty()
        self.last = -1

    def __call__(self, done, final=False):
        pct = 100 * done // self.total if self.total else 100
        if not final and (pct == self.last or (not self.tty and pct % 5)):
            return
        self.last = pct
        dt = max(time.time() - self.t0, 1e-3)
        rate = done / dt
        eta = int((self.total - done) / rate) if rate > 0 else 0
        msg = (f"  {self.label}: {done / 2**30:.2f} / {self.total / 2**30:.2f} GiB "
               f"{pct:3d}% {rate / 1e6:.1f} MB/s ETA {eta // 60}:{eta % 60:02d}")
        if self.tty:
            sys.stderr.write("\r" + msg + ("\n" if final else ""))
        else:
            sys.stderr.write(msg + "\n")
        sys.stderr.flush()


def put(local, remote, n, label=None):
    s = connect(timeout=30)
    s.sendall(f"put {remote} {n}\n".encode())
    prog = Progress(label or os.path.basename(remote), n) if n > 1 << 20 else None
    f = sys.stdin.buffer if local == "-" else open(local, "rb")
    sent = 0
    while sent < n:
        c = f.read(min(1 << 20, n - sent))
        if not c:
            sys.exit(f"short read of {local} at {sent} of {n} bytes")
        s.sendall(c)
        sent += len(c)
        if prog:
            prog(sent)
    if prog:
        prog(sent, True)
    s.settimeout(300)  # the last page-cache flush happens before the reply
    r = b""
    while b"\n" not in r:
        d = s.recv(4096)
        if not d:
            break
        r += d
    line = r.split(b"\n")[0].decode(errors="replace").strip()
    s.close()
    print(line)
    return line == f"ok {n}"


def stream(remote, n, sink, label=None):
    """cat REMOTE, feed exactly n bytes to sink(bytes), then hang up (a
    block device would otherwise stream to its end)."""
    s = connect()
    s.settimeout(120)
    s.sendall(f"cat {remote}\n".encode())
    h = hashlib.sha256()
    prog = Progress(label or os.path.basename(remote), n) if n > 1 << 20 else None
    got = 0
    while got < n:
        d = s.recv(min(1 << 20, n - got))
        if not d:
            sys.exit(f"console closed after {got} of {n} bytes of {remote}")
        if got == 0 and d.startswith(b"error\n"):
            sys.exit(f"cannot read {remote}")
        h.update(d)
        sink(d)
        got += len(d)
        if prog:
            prog(got)
    if prog:
        prog(got, True)
    s.close()
    return h.hexdigest()


def key(dev, secs):
    """Wait up to secs for a key press on dev; print its code."""
    end = time.time() + secs
    while time.time() < end:
        left = max(1, min(30, int(end - time.time())))
        try:
            out = cmd(f"evread {dev} 16 {left}", timeout=left + 15)
        except OSError:
            sys.exit(3)
        for ln in out.splitlines():
            f = ln.split()
            # "sec.usec type code value": EV_KEY (1), pressed (1)
            if len(f) == 4 and f[1] == "1" and f[3] == "1":
                print(int(f[2], 16))
                return
            if ln.strip() == "error":
                sys.exit(f"cannot read {dev}")
    print("timeout")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    op = a[0]
    try:
        if op == "probe":
            s = connect(timeout=3)
            s.sendall(b"cat /etc/os-release\n")
            r = until_prompt(s).decode(errors="replace")
            s.close()
            print(os_release(r))
        elif op == "cmd":
            sys.stdout.write(cmd(a[1], int(a[2]) if len(a) > 2 else 30))
        elif op == "put":
            sys.exit(0 if put(a[1], a[2], int(a[3]), a[4] if len(a) > 4 else None) else 1)
        elif op == "get":
            out = sys.stdout.buffer
            digest = stream(a[1], int(a[2]), out.write, a[4] if len(a) > 4 else None)
            out.flush()
            with open(a[3], "w") as f:
                f.write(digest + "\n")
        elif op == "hash":
            print(stream(a[1], int(a[2]), lambda d: None, a[3] if len(a) > 3 else None))
        elif op == "key":
            key(a[1], int(a[2]))
        else:
            sys.exit(__doc__)
    except ConnectionRefusedError as e:
        # no console on port 23: a Duranium dev image with the key-only
        # debug layer (r7+); its ssh does the same jobs
        if ssh_key() and os.environ.get("GTA3_CONSOLE_ADDR"):
            via_ssh(op, a)
        else:
            sys.exit(f"console: {e} (pair with scripts/tab-ssh --pair for ssh)")
    except (OSError, socket.timeout) as e:
        sys.exit(f"console: {e}")


if __name__ == "__main__":
    main()
