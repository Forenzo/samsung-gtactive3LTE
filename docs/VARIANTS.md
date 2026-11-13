# The Galaxy Tab Active3 family: variants

One board design in two variants, one port. Researched 2026-11-11 (sources
at the end; **V** = verified from a primary source, **R** = reported by a
secondary source, **?** = unknown). config.toml `[[variant]]` holds the
values; this file says what they are based on and what is still open.

| Variant (codename) | Models | Device id, images, channels | State |
|---|---|---|---|
| Wi-Fi (`gtactive3wifi`) | SM-T570 | `samsung-gtactive3wifi`, images `samsung-gtactive3-wifi_<ui>_edge[-dev]` (legacy name `samsung-gtactive3wifi_*` routed until no tablet needs it) | testing: the port's tablets run it ([STATUS.md](STATUS.md)) |
| LTE (`gtactive3`) | SM-T575, SM-T575N | `samsung-gtactive3`, no images yet (`images = false`) | bring-up: not booted; DTS, U-Boot board, device package and loaders exist, untested |
| LTE, US (`gtactive3`) | SM-T577U, SM-T577 | (would be the LTE variant) | not accepted: no confirmed bootloader unlock (below) |

## Model facts

| | SM-T570 | SM-T575 | SM-T575N | SM-T577U |
|---|---|---|---|---|
| `ro.product.device` | `gtactive3wifi` (V: config.toml, Forenzo) | `gtactive3` (V: Google Play device list; Forenzo's rooted unit) | `gtactive3` (V: Google Play list) | `gtactive3` (V: Google Play list; TWRP build.prop) |
| Firmware prefix | `T570XX` | `T575XX` (V: SamMobile) | `T575NKO`, CSC KOO only (V: SamMobile) | `T577UUE` (US), `T577UVL` (Canada) (V: SamMobile) |
| Board label (stock DT) | "GTACTIVE3WIFI EUR OPEN 04" at hw_rev 5 ([HARDWARE.md](../HARDWARE.md)) | "GTACTIVE3 EUR OPEN 04" at hw_rev 5 (V: Forenzo, live FDT) | ? | "GTACTIVE3 USA OPEN 00..05", 7 overlays (V: US GPL tree) |
| Bootloader unlock | done (owner's unit) | done first-hand twice (V: Forenzo 2026-09-30; XDA 2022) | ? | toggle present on one SM-T577U/DS, no completed unlock reported (R: XDA 2025-09) |
| LTE bands (FCC) | none | B2/4/5/12/13/17/41 (V: FCC A3LSMT575) | ? | adds B7/14/71 (V: FCC A3LSMT577U) |

RAM (4 GB, the same four DRAM banks), UFS, panel (Himax HX83102E), touch,
S Pen, cameras, PMICs (S2MPS18, MAX77705), Wi-Fi/Bluetooth (BCM4375 on
PCIe channel 0 + UART), NFC, fingerprint, the GNSS/sensor hub (Broadcom on
SPI, not in the CP) and the voice DSP are the same parts on the same buses
in both variants (V: Forenzo's T575 inventory and live FDT; the T577U's
stock DTBO).

## What differs

| Block | Wi-Fi | LTE | Where it is handled |
|---|---|---|---|
| Modem | none | the SoC's own Shannon CP ("ss360ap"): 146 MiB shared memory at 0xf0000000 + 32 MiB log buffer at 0xf9200000, MCU_IPC mailbox, PMU + EL3 start (V: T575 live FDT, T577U DTBO, GPL `modem_v1`) | reserved in the LTE DTS and U-Boot DT; driver: [re/modem.md](re/modem.md), sketch `patches/linux/0154` |
| Second grip (SAR) sensor | one A96T3X6 ("_wifi", hsi2c_34) | adds a second A96T3X6 (main, hsi2c_11, ldo_en gph1-3, IRQ gpa3-0) for the LTE antenna (V: T577U DTBO; FCC "Sensor Triggering Distance" exhibit) | not described yet: LTE DTS, once the T575's values are read |
| SIM | none | handled inside the CP (dual-SIM detect is a CP mailbox field); no SIM GPIO on the AP side (V: T577U DTBO) | modem driver |
| Speaker amp | by board revision, not by model: EUR hw_rev ≤ 4 RT5510 @0x34, EUR rev ≥ 5 TI TAS2562 @0x4c; US rev ≤ 5 RT5510, rev ≥ 6 TAS2562 (V: T570/T575 DTBOs, T577U DTBO set) | | today: common DTS has the RT5510 (the owner's rev 4 T570); the LTE DTS disables it and the sound card and has a disabled TAS2562 node. Next: pick the amp by revision for both variants |
| Touch SPI clock | 10 MHz in our DTS | 7 MHz in the T575's stock DTBO (V: Forenzo) | check on the T570's stock DTBO before changing the common DTS |

## What is shared and what is per variant

- **Per variant**: codename, device id (`IMAGE_ID`), images and update
  channels, `device-samsung-<codename>` (deviceinfo, kernel command line,
  its DTB through `linux-postmarketos-exynos9810-<codename>`), the board
  DTS `exynos9810-<codename>.dts`, U-Boot's board entry (by model prefix),
  the boot-chain loaders `uniLoader-{chain,linux}[-<codename>]`, the
  installer's tested firmware and Samsung firmware download model.
- **Family** (`device.family = gtactive3`): the repository, the kernel
  (`linux-postmarketos-exynos9810`, patch `gtactive3.patch`), the common DT
  `exynos9810-gtactive3-common.dtsi`, `samsung-gtactive3-common` (every
  shared file of the device package, installed paths unchanged), U-Boot
  (`gtactive3_defconfig`, both DTs, `OF_LIST`), uniLoader
  (`gtactive3_chain_defconfig`), the boot-chain release
  (`samsung-gtactive3_bootchain`), the installer (`gtactive3-setup`), the
  build tree (`contrib/samsung-gtactive3/`, `DEVICE=`).
- **Image names** are the variants' own (`image_id`):
  `samsung-gtactive3-wifi_*` and `samsung-gtactive3-lte_*`. The Wi-Fi
  images were `samsung-gtactive3wifi_*` until 26102403; installed tablets
  move over through the legacy routing (docs/RELEASES.md, "Image names").
- **Never renamed** (in installed SM-T570s): the Wi-Fi codename and device
  id (package names), its channel file `/usr/lib/gtactive3wifi/update-channel`,
  the signing key.
  File names inside the common package keep their `gtactive3wifi` names for
  now: renaming them changes what installed tablets run and needs its own
  on-device test.

## Firmware names

brcmfmac names its files after the board type, which defaults to the root
compatible. The LTE DTS sets `brcm,board-type = "samsung,gtactive3wifi"`,
so both variants use the same names and the installer's import serves both.
Bluetooth (btbcm) has no such override: on the LTE variant it asks for
`brcm/BCM.samsung,gtactive3.hcd`, so `tools/fw_index.py` stages the
patchram under both boards' names.

## The LTE variant: the way to its first boot

1. Owner of a T575 (Forenzo's unit is the only one known): stock DT and PIT
   read-only (partition names and BOOT size; `installer.*` assume the
   T570's), the second grip sensor and TAS2562 values, `/proc/iomem`.
2. CI compiles the LTE DTB, U-Boot with both DTs and the kernel
   (`.github/workflows/check.yml`).
3. First contact: `./setup.sh --bring-up` (or heimdall by hand) flashes BOOT
   with `uniLoader-linux-gtactive3`: the bring-up Linux with the LTE DTB and
   the USB console. Way back: Download mode + the stock BOOT image (the
   installer keeps it). Never a Samsung recovery or factory reset.
4. Then the chained boot (`uniLoader-chain-gtactive3` → U-Boot, which must
   pick `exynos9810-gtactive3` from S-Boot's "T575" model), then a local
   Duranium image (`DEVICE=samsung-gtactive3`), then `images = true` for the
   dev channels.
5. The modem after a stable non-cellular boot ([re/modem.md](re/modem.md)):
   it needs an owner decision on reading `nv_data.bin` from EFS into RAM.

## Open questions

- SM-T577U / SM-T577: is a bootloader unlock possible (Download mode with
  the OEM-unlock toggle on, first-hand)? Until then they stay out of
  `[[variant]]`. Their boards also use the US revision scheme (7 overlays).
- SM-T575N: no unlock report; firmware `T575NKO...`; assumed the T575's
  hardware (`gtactive3`).
- Which board revisions ship in which countries (only two units known: a
  T570 rev 4 and a T575 rev 5).
- BOOT's size: the installer builds the boot images' AVB footer for the
  T570's BOOT (61865984 bytes, `scripts/installer/lib/bootimg.sh`) and warns
  when the stock boot image differs; the T575's PIT is not read yet.
- The CP's memory: does U-Boot or the bring-up Linux on a T575 touch
  0xf0000000-0xfb200000 before a modem driver exists? Both reserve it now,
  except U-Boot when S-Boot passed no usable command line (only uniLoader's
  own DTB): then U-Boot runs on the Wi-Fi DT, without those reservations
  in the EFI memory map (the kernel's own DTB still has them).

## Sources

- Samsung's GPL tree of the **SM-T577U** (not of the T570): GitHub mirror
  lessthanmuir/android_kernel_samsung_gtactive3cs, defconfig
  `exynos9810-gtactive3ue_defconfig`, board DTS
  `exynos9810-gtactive3_usa_open_00..06.dts`. It is the tree this repo's
  docs call `build/ref/gtactive3cs`. Samsung's portal lists only an SM-T570
  package (T570XXSDEYC1) and none for the T575/T575N/T577U (read 2026-11-11).
- Forenzo/samsung-gtactive3LTE, branch `port/sm-t575-bringup`,
  `docs/SM-T575-BRINGUP.md` (a fork of this repo with a rooted T575, rev 5,
  T575XXSFEYI1): measured live FDT, cmdline and I2C inventory; their DTS is
  compile-only.
- Google Play's supported devices list (storage.googleapis.com/play_public/
  supported_devices.csv); SamMobile firmware lists; fccid.io A3LSMT570,
  A3LSMT575, A3LSMT577U; XDA threads 4240585 (T575 root) and 4760100
  (T577U/DS).
