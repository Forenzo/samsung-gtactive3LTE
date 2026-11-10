# SM-T570 → postmarketOS Duranium: plan

Goal: postmarketOS **Duranium** (immutable, systemd, UKI + systemd-boot, A/B
systemd-sysupdate) with a complete GUI and every piece of hardware working, plus a
USB debug layer (NCM gadget + root console) that is on by default for development
and can be disabled.

Work is split into layers. Each layer is built by parallel agents in their own
branches (`drv/<track>` in src/linux, worktrees under build/wt/), reviewed by an
independent agent, then integrated and tested live on the device, one layer at a
time, through the USB console. A layer is only merged into `gtactive3wifi` after
its live test passes.

Rule for every test: a failure must come back to the USB console without anyone
touching the tablet (reset → Download mode → automatic reflash, or watchdog reset
→ BOOT). No boot stages on RECOVERY.

## Next three steps (2026-11-11)

1. The multi-variant change (branch `variants`): CI `check.yml` green
   (LTE DTB, U-Boot with both DTs, the Wi-Fi DTB identical to main's, the
   modem sketch compiles), then TESTPLAN V1 (the Wi-Fi image unchanged) on
   the tablet before it merges: merging publishes it to the dev channels.
2. Rename the repository to `exynos-linux/samsung-gtactive3`
   (docs/RELEASES.md, "Moving the repository"), the owner's step 2 there.
3. The open SM-T570 work of 2026-10-25, unchanged: r25 boots counted to 5
   and `scripts/pmos-verify`; r26 (autofocus, V4L2 controls,
   drv/wifi-recover, the mic slider, now `samsung-gtactive3-common` r50);
   the boot hang, C2 and deep sleep. The LTE first boot (TESTPLAN V2/V3)
   when a T575 owner joins (docs/VARIANTS.md).

The layer lists below are the original bring-up plan; docs/STATUS.md says
what is verified today.

## Done
- [x] Bootloader unlock, KnoxGuard cleared, stock firmware T570XXSFEYI1 downloaded
- [x] S-Boot → uniLoader (BOOT) → mainline Linux 7.3, automated flash/boot loop (~33 s)
- [x] USB NCM gadget + debug console with the cable never unplugged (MAX77705 switch)
- [x] UFS HS-G3 x2, simple-framebuffer console, gpio-keys, pstore
- [x] Cluster-0 watchdog reset measured (PMU 0x408/0x40c bit 24); WDT reset boots BOOT

## Layer 0: safety net
- [x] Linux watchdog (s3c2410_wdt Exynos 9810 variant), kicked by init — track `wdt`
      (docs/STATUS.md Hang recovery; the r24 hang it did not reset is open, step 3)
- [x] uniLoader dual payload: U-Boot primary, bring-up Linux fallback on watchdog
      reset or Volume Down — track `chainload`

## Layer 1: boot chain and storage
- [x] U-Boot as uniLoader payload: UFS, blkmap over userdata, EFI, systemd-boot — `chainload`
- [x] Nested GPT in userdata (sda31) visible to Linux / systemd in the initrd — `duranium`
- [x] (2026-10-21) Android wiped by UFS discard: metadata, super, cache, userdata (approved 2026-10-21: userdata + Android OS partitions; never
      efs, sec_efs, param, up_param, persistent, bootloader partitions, RPMB)

## Layer 2: Duranium image
- [x] device-samsung-gtactive3wifi + linux-postmarketos-exynos9810 packages — `pmos`
- [x] mkosi device support, UKI with embedded DTB, Phosh and GNOME images — `duranium`
- [x] `duranium-usb-debug` package/sysext: NCM gadget, root console, SSH, initrd too
- [x] Vendor firmware extracted from the stock package (never committed) — `firmware`

## Layer 3: what the GUI needs
- [x] Display (exynos9810-dpu KMS driver), rotation, auto-rotate — `display`
      (owner 2026-10-24 and 2026-10-25)
- [ ] Backlight brightness slider — `display`
- [x] Touch: SPI controller + Himax HX83102E — `touch`
- [ ] I2C buses (HSI2C/USI) — `hsi2c`; Wacom pen — `misc`

## Layer 4: power and CPU
- [ ] S2MPS18 (SPEEDY), MAX77705 charger + fuel gauge, TMU thermal — `power`
- [x] Big cores, clock driver, then cpufreq — `cpu` (all eight cores, owner
      2026-10-25); left: big-core C2, M3 above 1794 MHz
- [ ] CPU idle C2 (off by default since r25) — `cpu`

## Layer 5: acceleration and connectivity
- [x] Mali-G72 Panfrost — `gpu` (owner 2026-10-25); left: AFBC fault count, MIF floor
- [ ] Wi-Fi (Exynos PCIe + brcmfmac), Bluetooth (UART, hci_bcm) — `wifi`

## Variants: the LTE SM-T575 (docs/VARIANTS.md)

- [x] Config schema `[[variant]]`, CI matrix per variant, family names
  (boot chain, installer, build tree `contrib/samsung-gtactive3`)
- [x] Board DT split: `exynos9810-gtactive3-common.dtsi` + one file per
  variant; LTE DTS with the CP carveouts reserved, Wi-Fi firmware names
- [x] Packages: `samsung-gtactive3-common`, thin `device-samsung-gtactive3wifi`
  / `device-samsung-gtactive3`, per-variant DTB subpackages of the kernel
- [x] U-Boot board entry (T575) and both DTs; per-variant bring-up loaders
- [x] Installer: variant from the model, `--bring-up` for the LTE variant
- [x] Modem: facts and a driver plan (docs/re/modem.md), remoteproc sketch
  (patches/linux/0154, not enabled)
- [ ] CI check green; TESTPLAN V1 on the SM-T570; merge
- [ ] Repository rename (docs/RELEASES.md)
- [ ] With a T575: stock DT/PIT facts, V2 bring-up Linux, V3 chained boot,
  a local Duranium image, then `images = true`
- [ ] Speaker amp by board revision (TAS2562 on EUR rev >= 5, both variants)
- [ ] Second grip (SAR) sensor; Bluetooth firmware name on the LTE variant
- [ ] Modem P1 (vendor-style module + vendor cbd, needs the EFS read
  decision), P2 userspace, P3 mainline driver (docs/re/modem.md)

## Layer 6: the rest
- [ ] Audio (ABOX, RT5665, RT5510) — `audio`: speaker, internal mic and jack detection fixed live on r24 (2026-10-24), permanent in r25 (drv/audio-fix 7e3507579, device r48); plug passed (owner 2026-10-24); left: unplug, then TESTPLAN D11 on r25 as booted
- [ ] MUIC SM5504, hall sensor, jack, vibrator, keys, NFC (S3FWRN5), grip sensor,
      accelerometer/light sensors — `misc` (2026-10-24: accel/light/
      proximity through the BCM4775 hub verified live, Phosh auto-rotate
      works; the sensor rails (drv/shub3) are in kernel r24, D8 passed:
      docs/STATUS.md)
- [x] Cameras: rear S5K3L6 and front GC5035 on stock libcamera, fixed focus
      (owner 2026-10-24 and 2026-10-25); autofocus is step 2
- [ ] Fingerprint (TrustZone-owned), GPS: research first
