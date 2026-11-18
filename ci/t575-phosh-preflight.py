#!/usr/bin/env python3
"""Static and artifact-level gates for the NON-FLASHING LTE Phosh image CI.

Modes:
  source                  check repository and variant alignment (fast)
  packages [PKGS_DIR]     check the exact LTE APKs before mkosi (fast)
  image [OUTPUT_DIR]      check image naming, compression/UKI presence (read-only)

This script never reads or writes a device or any Android partition.
"""
import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = "SM-T575"
CODENAME = "gtactive3"
IMAGE_ID = "samsung-gtactive3-lte"
FLAVOR = "phosh"
RELEASE = "edge"
VERSION = "26111790"
OUTPUT_STEM = f"{IMAGE_ID}_{FLAVOR}_{RELEASE}"
CHANNEL = f"{OUTPUT_STEM}-dev"


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def check(condition, message):
    if not condition:
        fail(message)
    print(f"PASS: {message}")


def cfg(query):
    p = subprocess.run([str(ROOT / "scripts/config"), *query],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        fail(f"scripts/config {' '.join(query)}: {p.stderr.strip()}")
    return p.stdout.strip()


def source():
    data = tomllib.loads((ROOT / "config.toml").read_text())
    lte = next((x for x in data["variant"] if x["codename"] == CODENAME), None)
    wifi = next((x for x in data["variant"] if x["codename"] == "gtactive3wifi"), None)
    check(lte is not None and MODEL in lte["models"] and
          lte.get("image_id") == IMAGE_ID and lte["images"] is False,
          "LTE model and image ID match; LTE release publishing remains disabled")
    check(wifi is not None and "SM-T570" in wifi["models"] and MODEL not in wifi["models"],
          "SM-T575 never maps to the Wi-Fi variant")
    check(cfg(["variant-of", MODEL]) == CODENAME, "installer chooses LTE device variant")
    check(cfg(["get", "variants.gtactive3.image_id"]) == IMAGE_ID,
          "build uses the LTE image ID")
    check(cfg(["get", "variants.gtactive3.channel_file"]) ==
          "/usr/lib/samsung-gtactive3/update-channel",
          "LTE has its own sysupdate channel marker")
    protected = set(data["installer"]["protected"])
    check({"efs", "sec_efs", "dtbo", "vbmeta", "persistent", "cpefs"} <= protected,
          "critical firmware/identity partitions remain protected")
    check(data["installer"]["flash_allow"] == ["BOOT", "RECOVERY"],
          "boot installer cannot flash other Samsung partitions")
    check(data["installer"]["boot_partition_bytes"] == 0,
          "LTE boot image creation stays blocked until PIT measurement is validated")
    kernel = (ROOT / "pmos/aports/device/testing/linux-postmarketos-exynos9810/APKBUILD").read_text()
    patch = ROOT / "pmos/aports/device/testing/linux-postmarketos-exynos9810/t575-gpu-first-desktop.patch"
    check("t575-gpu-first-desktop.patch" in kernel and patch.is_file(),
          "LTE GPU workaround is included in the kernel package build")
    # An accessible Phosh UI requires finger input separately from the S Pen.
    # This is a source/packaging gate, NOT proof that the SPI controller
    # successfully probes or generates touch events on the physical tablet.
    kconfig = (ROOT / "pmos/aports/device/testing/linux-postmarketos-exynos9810"
               / "config-postmarketos-exynos9810.aarch64").read_text()
    check("CONFIG_TOUCHSCREEN_HIMAX_HX83112B=m" in kconfig and
          "CONFIG_INPUT_EVDEV=y" in kconfig,
          "Himax HX83102E finger-touch module and evdev input are enabled")
    check("CONFIG_TOUCHSCREEN_WACOM_W9000=m" in kconfig,
          "Wacom pen input is enabled separately from finger touch")
    tree_split = (ROOT / "patches/linux/"
                  "0153-arm64-dts-exynos9810-gtactive3-split-into-common-and.patch").read_text()
    check('compatible = "himax,hx83102e"' in tree_split and
          "touchscreen@0" in tree_split and
          "&spi_21" in tree_split and
          '#include "exynos9810-gtactive3-common.dtsi"' in tree_split,
          "LTE device tree inherits the common HX83102E SPI21 touchscreen")
    diffs = [x for x in patch.read_text().splitlines() if x.startswith("diff --git ")]
    check(diffs == ["diff --git a/arch/arm64/boot/dts/exynos/exynos9810-gtactive3.dts b/arch/arm64/boot/dts/exynos/exynos9810-gtactive3.dts"],
          "GPU DT patch is restricted to the LTE device tree")
    check((ROOT / "pmos/sysupdate-public-key.asc").read_text().startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"),
          "sysupdate public key is available for post-build validation")
    w = (ROOT / ".github/workflows/t575-lte-phosh-first-desktop.yml").read_text()
    check("UI: phosh" in w and "DEVICE: samsung-gtactive3" in w and
          "GTA3_IMAGE_ID=samsung-gtactive3-lte" in w,
          "mkosi invocation is Phosh with the LTE device and image ID")
    check("MKOSI_CONTAINER_ARGS" in w and "--user=0:0" in w,
          "mkosi container workspace runs with a writable UID")
    check("ci/check-image" in w and "if-no-files-found: error" in w,
          "image integrity gate and required artifact upload are enabled")
    print("PASS: source-only audit; this does NOT prove a complete image boots")


def packages(dirname):
    d = Path(dirname)
    check(d.is_dir(), "package output directory exists")
    for basename in ("linux-postmarketos-exynos9810-", "linux-postmarketos-exynos9810-gtactive3-",
                     "device-samsung-gtactive3-", "device-samsung-gtactive3-initramfs-",
                     "samsung-gtactive3-common-", "duranium-usb-debug-"):
        hits = [p for p in d.glob(f"{basename}*.apk") if p.name.startswith(basename)]
        check(any(p.stat().st_size > 1024 for p in hits), f"required APK present: {basename}")
    print("PASS: LTE kernel, DTB, device packages and USB diagnostics exist")


def image(dirname):
    d = Path(dirname)
    check(d.is_dir(), "mkosi output directory exists")
    files = sorted(p for p in d.iterdir() if p.is_file())
    compressed = [p for p in files if p.name.endswith(".raw.zst")]
    check(compressed and all(p.stat().st_size > 0 for p in compressed),
          "all compressed Duranium image parts are nonempty")
    disk = d / f"{OUTPUT_STEM}_{VERSION}.raw.zst"
    check(disk.is_file() and disk.stat().st_size > 100_000_000,
          "full LTE disk image is present and plausibly sized")
    check((d / f"{OUTPUT_STEM}_{VERSION}.efi").is_file(),
          "versioned ARM64 EFI unified kernel image is present")
    check(not any("gtactive3wifi" in p.name or "_gnome_" in p.name
                  for p in files), "output does not contain Wi-Fi or GNOME images")
    check(all(p.name.startswith(OUTPUT_STEM) for p in compressed),
          "compressed image files have LTE Phosh image prefix")
    print(f"PASS: {len(compressed)} compressed image part(s), UKI present")
    print("NOT TESTED: first boot, physical display, touchscreen or Samsung LTE modem")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("source", "packages", "image"))
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()
    if args.stage == "source":
        source()
    elif args.stage == "packages":
        packages(args.path or str(ROOT / "pkgs"))
    else:
        image(args.path or str(ROOT / "work/duranium-build/mkosi.output" / OUTPUT_STEM))
