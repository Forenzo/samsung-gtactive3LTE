#!/usr/bin/env python3
"""Offline tests of scripts/config: the port's config.toml and the variant
schema (docs/CONFIG.md). Run: python3 -I tests/config/test_config.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "scripts" / "config"
TOML = (ROOT / "config.toml").read_text()


def run(*args, toml=None, env=None):
    e = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
    e.update(env or {})
    with tempfile.TemporaryDirectory() as d:
        if toml is not None:
            p = Path(d) / "config.toml"
            p.write_text(toml)
            e["CONFIG"] = str(p)
        return subprocess.run([sys.executable, "-I", str(CONFIG), *args], env=e,
                              capture_output=True, text=True)


def ok(*args, **kw):
    r = run(*args, **kw)
    if r.returncode:
        raise AssertionError(f"scripts/config {' '.join(args)} failed: {r.stderr}")
    return r.stdout


def single_device(toml):
    """The port as it was before [[variant]]: [device] + [android] only."""
    head, _, rest = toml.partition("# Wi-Fi only:")
    _, _, tail = rest.partition('fus_model = "SM-T575"\n')
    head = head.replace('family = "gtactive3"\n', "")
    head = head.replace('models = ["SM-T570", "SM-T575", "SM-T575N"]', 'models = ["SM-T570"]')
    return head + '''[android]
product_device = "gtactive3wifi"
firmware_pattern = "T570[A-Z0-9]{8}"
tested_firmware = "T570XXSFEYI1"
tested_bootloader_rev = "F"
fus_model = "SM-T570"
''' + tail


class PortConfig(unittest.TestCase):
    def test_check_passes(self):
        self.assertIn("ok", ok("check"))

    def test_wifi_identity_unchanged(self):
        # baked into every installed SM-T570: never changes
        self.assertEqual(ok("get", "device.id").strip(), "samsung-gtactive3wifi")
        self.assertEqual(ok("get", "update.channel_file").strip(), "/usr/lib/gtactive3wifi/update-channel")
        self.assertEqual(ok("get", "android.fus_model").strip(), "SM-T570")
        self.assertEqual(ok("get", "installer.name").strip(), "gtactive3-setup")

    def test_channels_only_for_variants_with_images(self):
        lines = [ln.split() for ln in ok("channels").splitlines()]
        self.assertEqual(sorted(ln[2] for ln in lines), [
            "samsung-gtactive3wifi_gnome_edge", "samsung-gtactive3wifi_gnome_edge-dev",
            "samsung-gtactive3wifi_phosh_edge", "samsung-gtactive3wifi_phosh_edge-dev"])
        self.assertTrue(all(ln[3] == "gtactive3wifi" for ln in lines))
        m = json.loads(ok("matrix"))["include"]
        self.assertEqual({x["device"] for x in m}, {"samsung-gtactive3wifi"})

    def test_variants(self):
        v = {ln.split()[0]: ln.split() for ln in ok("variants").splitlines()}
        self.assertEqual(set(v), {"gtactive3wifi", "gtactive3"})
        self.assertEqual(v["gtactive3"][1:4], ["samsung-gtactive3", "bring-up", "false"])
        self.assertEqual(ok("variant-of", "SM-T575N").strip(), "gtactive3")
        self.assertEqual(ok("variant-of", "SM-T570").strip(), "gtactive3wifi")
        self.assertNotEqual(run("variant-of", "SM-T577U").returncode, 0)

    def test_family_names(self):
        self.assertEqual(ok("get", "bootchain.tag").strip(), "samsung-gtactive3_bootchain")
        self.assertEqual(ok("get", "bootchain.u_boot_defconfig").strip(), "gtactive3_defconfig")
        self.assertTrue((ROOT / "bootchain/u-boot/configs/gtactive3_defconfig").is_file())
        self.assertTrue((ROOT / "bootchain/uniLoader/configs/gtactive3_chain_defconfig").is_file())
        self.assertEqual(ok("get", "bootchain.dtbs").split(),
                         ["exynos/exynos9810-gtactive3wifi.dtb", "exynos/exynos9810-gtactive3.dtb"])
        self.assertEqual(ok("get", "variants.gtactive3.kernel_dtb_package").strip(),
                         "linux-postmarketos-exynos9810-gtactive3")

    def test_every_variant_has_an_aport_and_dtb_subpackage(self):
        c = json.loads(ok("json"))
        kernel = (ROOT / c["kernel"]["aport"] / "APKBUILD").read_text()
        for cn, v in c["variants"].items():
            self.assertTrue((ROOT / v["aport"] / "deviceinfo").is_file(), cn)
            self.assertIn(f"$pkgname-{cn}:_dtb", kernel)
            self.assertIn(v["kernel_dtb_package"], (ROOT / v["aport"] / "APKBUILD").read_text())
        self.assertTrue((ROOT / c["device"]["common_aport"] / "APKBUILD").is_file())


class Schema(unittest.TestCase):
    def test_single_device_port_still_works(self):
        t = single_device(TOML)
        self.assertNotIn("\n[[variant]]\n", t)
        self.assertIn("ok", ok("check", toml=t))
        self.assertEqual(ok("variants", toml=t).split()[:2], ["gtactive3wifi", "samsung-gtactive3wifi"])
        self.assertEqual(ok("get", "device.family", toml=t).strip(), "gtactive3wifi")
        self.assertEqual(len(ok("channels", toml=t).splitlines()), 4)

    def test_duplicate_model_is_an_error(self):
        t = TOML.replace('models = ["SM-T575", "SM-T575N"]', 'models = ["SM-T575", "SM-T570"]')
        r = run("check", toml=t)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("model SM-T570 is in variants", r.stderr)

    def test_u_boot_match_must_prefix_models(self):
        t = TOML.replace('u_boot_match = "T575"', 'u_boot_match = "T577"')
        r = run("check", toml=t)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("u_boot_match", r.stderr)

    def test_tested_firmware_must_match_pattern(self):
        t = TOML.replace('tested_firmware = "T575XXSFEYI1"', 'tested_firmware = "T570XXSFEYI1"')
        self.assertIn("does not match firmware_pattern", run("check", toml=t).stderr)

    def test_no_variant_with_images_is_an_error(self):
        t = TOML.replace("images = true", "images = false")
        self.assertIn("no variant publishes images", run("check", toml=t).stderr)

    def test_unknown_default_codename_falls_back_to_first(self):
        t = TOML.replace('codename = "gtactive3wifi"\nname = "Samsung Galaxy Tab Active3"\n',
                         'codename = "nosuch"\nname = "Samsung Galaxy Tab Active3"\n', 1)
        self.assertEqual(ok("get", "device.codename", toml=t).strip(), "gtactive3wifi")


if __name__ == "__main__":
    unittest.main(verbosity=1)
