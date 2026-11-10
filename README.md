# Samsung Galaxy Tab Active3 LTE (SM-T575) — Mainline Linux Port

**Experimental device port** of mainline Linux and postmarketOS Duranium for the **Samsung Galaxy Tab Active3 LTE (SM-T575)**, based on [exynos-linux/samsung-gtactive3wifi](https://github.com/exynos-linux/samsung-gtactive3wifi).

**SM-T575 status (2026-11-10):** An independent LTE DTB, Linux kernel Image and diagnostic initramfs compile; a dedicated uniLoader builds with static linker/relocation checks. A 55,304,208-byte **unsigned, offline-only .research BOOT-format file** was byte-verified against the rooted Android backup, but **SM-T575 Linux has never been booted, S-Boot acceptance is unknown, and no safe flash/restore procedure is approved**. The inherited installer, device-tree defaults and published SM-T570 images remain **Wi-Fi-only**: **do not flash or run them on SM-T575**.

The LTE development work lives on the [`port/sm-t575-bringup` branch](https://github.com/Forenzo/samsung-gtactive3LTE/tree/port/sm-t575-bringup), including [the dated T570-versus-T575 hardware comparison, build evidence and safety notes](https://github.com/Forenzo/samsung-gtactive3LTE/blob/port/sm-t575-bringup/docs/SM-T575-BRINGUP.md#sm-t570-wi-fi-versus-sm-t575-lte-evidence-and-porting-differences-2026-11-10) and a read-only macOS-compatible [hardware inventory script](https://github.com/Forenzo/samsung-gtactive3LTE/blob/port/sm-t575-bringup/scripts/t575-inventory.sh).

### SM-T570 versus SM-T575: key differences verified so far

- **Same Exynos 9810 foundation:** running T575 Android FDT has the same four physical DRAM banks recorded in upstream T570 source, but bootloader handover and memory ownership are not confirmed.
- **LTE modem:** T575 adds Samsung modem interface and reserved modem/CP-logging memory; cellular support is deliberately postponed.
- **Audio amplifier depends on hardware revision:** T575 selects **TAS2562**; tested T570 rev4 uses RT5510, but upstream T570 notes also identify TAS2562 on another revision. Thus this is **not necessarily an LTE-exclusive hardware change**.
- **Display and pen are related but not proven interchangeable:** T575 has HX83102E-family panel/touch hardware, W90xx pen and the same nominal 1200×1920 boot framebuffer; T575 DECON takeover and native panel remain disabled.
- **Boot chain must stay model-specific:** verified T575 rooted Android BOOT v2 uses board ID **SRPTE13A015**, distinct from inherited Wi-Fi assumptions. T575 uniLoader has its own passive board selection, ARM64 header and audited relocation changes.

The [detailed comparison](docs/SM-T575-BRINGUP.md#sm-t570-wi-fi-versus-sm-t575-lte-evidence-and-porting-differences-2026-11-10) distinguishes private T575 hardware observations, upstream T570 source references and outstanding uncertainties.

### Planned work
- Compare real T575 hardware and vendor device trees with the T570.
- Prepare a separate LTE device tree and **compile-only** kernel build before testing on hardware.
- Verify a reversible BOOT-only recovery procedure; preserve the currently rooted Android installation.
- Bring up touchscreen, display, GPU, storage, power, audio and wireless hardware; investigate cellular modem and GNSS separately.
- Package T575-specific postmarketOS images **only after** safe boot and device testing.

This fork is independent experimental work. The T570 documentation below describes the **upstream Wi-Fi model only**, not tested LTE behavior.

---

## Upstream SM-T570 documentation (reference only)

Mainline Linux on the Wi-Fi Galaxy Tab Active3 (`gtactive3wifi`, Exynos 9810),
running postmarketOS Duranium (immutable, A/B updates) with Phosh or GNOME.
The kernel and drivers are ours; the rest of the OS is unmodified
postmarketOS.

## Status

As of 2026-10-25, in postmarketOS Duranium (Phosh). The strict, per-block
table with sources and test runs is [docs/STATUS.md](docs/STATUS.md).

| Area | State |
|---|---|
| Boot chain (S-Boot → uniLoader → U-Boot → systemd-boot → UKI), signed A/B updates with rollback | ✅ |
| CPU: all 8 cores (4× Cortex-A55 + 4× Mongoose M3), frequency scaling | ✅ |
| GPU Mali-G72 (Panfrost): Phosh renders on the GPU | ✅ |
| Display (our DPU KMS driver), touch | ✅ |
| Rotation, manual and automatic (accelerometer through the sensor hub) | ✅ |
| Cameras: 8 MP rear, 5 MP front, on stock libcamera | ✅ fixed focus; autofocus in progress |
| Storage (UFS), RAM, power and volume-up keys, suspend to idle | ✅ |
| Wi-Fi (BCM4375) | ⚠️ connects at boot; the firmware hangs now and then, automatic recovery is being tested |
| Audio: speaker, microphone, headphone jack | ⚠️ speaker, mic and plug-in pass; unplug untested |
| Battery and charging | ⚠️ charges; temperature-based limits not booted yet |
| CPU idle (C2) | ❌ off by default: it hangs or slows the system |
| Bluetooth, S Pen, microSD, NFC, Home/Recent keys, flash LED | ❔ drivers load; not tested in the UI yet |
| Volume-down and Active keys, GPS, fingerprint | ❌ |

What comes next: [PLAN.md](PLAN.md).

## Layout

- `patches/linux`: our kernel commits as a patch series (base in `BASE`)
- `patches/libcamera`: libcamera patches meant for upstream (the images use
  stock postmarketOS libcamera)
- `bootchain/`: the boot chain the installer flashes (vendored U-Boot and
  uniLoader from exynos-linux/device-template, `build.sh`)
- `configs/`: kernel config fragment and initramfs list template
- `initramfs/init.c`: bring-up init (kernel nolibc): USB gadget, debug console
- `scripts/`: build, package, flash loop (`devd.sh`), console client (`tab`)
- `pmos/`: what we maintain for postmarketOS Duranium (aports incl. the kernel,
  duranium-build patches, the image signing key), exported by `scripts/pmos-export`
- `ci/`, `.github/workflows/images.yml`: builds the images when postmarketOS
  publishes or `pmos/` changes, publishes them as GitHub releases, which is where
  the tablets update from: see [docs/RELEASES.md](docs/RELEASES.md)
- `HARDWARE.md`: hardware map from the stock firmware, `PLAN.md`: roadmap

## Install

On a Linux PC, with the tablet on USB:

```
./setup.sh --stock-ap AP_<your firmware>.tar.md5
```

It first only puts our Linux into BOOT (Android stays as it is, `./setup.sh
undo` brings it back), then offers a full Android backup and the install.
Step by step, requirements and the way back to Android:
[docs/INSTALL.md](docs/INSTALL.md).

## Downloads and updates

Images (Phosh, GNOME) are in the
[releases](https://github.com/exynos-linux/samsung-gtactive3wifi/releases), rebuilt
automatically on top of each postmarketOS publish. Today only the development
channels have builds; the release channels get one once an export passes on
the device (`scripts/pmos-verify`). Installed tablets update
from there with `updatectl update` (A/B, signed, automatic rollback). Vendor
firmware is not included. [docs/RELEASES.md](docs/RELEASES.md) explains it all.

## Development loop

```
scripts/build.sh            # init + kernel + modules → build/images/boot-mainline.img
scripts/devd.sh &           # flashes BOOT whenever the tablet is in Download mode
scripts/tab reboot download # tablet reboots, gets flashed, boots, USB is back in ~35 s
scripts/tab dmesg           # debug console over IPv6 link-local (fe80::57:aff:fe00:1)
```

Stock firmware, keys and decrypted images are never committed.
