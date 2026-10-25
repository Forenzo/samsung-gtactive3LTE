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

## Next three steps (2026-10-25)

1. r25 (26102403: kernel cand/1035, device r48) on the tablet: count clean
   boots (TESTPLAN B5) to 5, run TESTPLAN D11 (audio) and D7 E/F (cameras)
   as booted, then `scripts/pmos-verify` so the release channels get a build.
2. r26: autofocus that holds still (drv/cam-caf, test with the owner),
   standard V4L2 camera controls on the lens and sensors, drv/wifi-recover
   (live swap test first), the audio mic slider (device r49).
3. Kernel root causes: the r24 boot hang the watchdog did not reset (C2
   with eight cores suspected; r25 logs RST_STAT and the PMIC on/off
   sources at boot), then C2 idle, deep sleep and a cable-out battery drain
   measurement with the owner.

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
