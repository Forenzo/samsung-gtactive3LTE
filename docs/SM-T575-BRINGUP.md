# SM-T575 LTE bring-up: previous-device evidence and safety plan

Status: **compile-only DTB / static hardware validation**. A T575-specific DTB now builds in GitHub Actions, but it is not runtime validated and is not safe for flashing. No SM-T575 boot image exists in this branch. The upstream SM-T570 installer, release images and firmware packages **must not be used on the SM-T575**.

## Previously established on the actual tablet (2026-09-30 to 2026-10-01)

- Device: Samsung Galaxy Tab Active3 **SM-T575 LTE**, Android 13, region SEB, PDA/bootloader **T575XXSFEYI1**, Linux vendor kernel 4.9.191, 2025-10-01 Android patch level.
- Bootloader was unlocked on 2026-09-30. The observed properties after unlocking included `ro.boot.flash.locked=0`, `ro.boot.vbmeta.device_state=unlocked`, and verified boot **orange**. Recheck live state before any future boot attempt.
- Magisk root was verified working on 2026-10-01, with a Magisk-patched AP and **Heimdall 2.2.2 on macOS** in the recovery workflow. The device is not a pristine stock test device: preserve the installed rooted Android, user data, Magisk and restore images.
- Stock boot uses Android boot header **v2**, 2048-byte pages; the firmware contains separate DT/DTBO material (six DTBO entries were observed). The partition map includes `boot`, `recovery`, `dtbo`, `vbmeta`, `vbmeta_samsung`, `super`, `userdata`.
- A prior Odin flow encountered a hash-mismatch problem; a patched AP package was repacked with an empty `vbmeta.img` while retaining `vbmeta_samsung`. This is **historical troubleshooting evidence**, NOT a validated procedure for the Linux installer, and must not be copied into any automatic flashing path.
- OEM unlock / KnoxGuard **Prenormal** status previously complicated flashing. It was eventually resolved and root succeeded, but unlocking status must be checked immediately before further experiments.
- Prior recovery messages included “Can't load Android system” and “set policy failed: /data/bootchart”. The previous successful Android recovery involved a data wipe. **Do not repeat that wipe for this Linux project**.

Source: the device owner's earlier September 30–October 1, 2026 test sessions. This document deliberately excludes serial numbers, IMEI, device-unique IDs, private firmware and patched images.

## Differences that must be verified rather than assumed

1. Obtain a fresh **read-only** SM-T575 snapshot from its currently working rooted Android. Prefer upstream `scripts/firmware-snapshot doctor` and `scripts/firmware-snapshot run --root --no-tree` from a supported Linux environment; the script has Linux/GNU utilities, so do not assume macOS compatibility without testing. Keep output outside Git and review the redaction.
2. Compare vendor DTBs/DTBO overlays, board revision, display/touch/pen/audio devices, PMICs, regulator supplies, modem interfaces, storage partition mapping, and BOOT/vbmeta constraints against T570. Do not infer compatibility from the shared Exynos 9810.
3. Add an **independent** `exynos9810-gtactive3lte.dts` only after hardware comparison. Avoid modifying the T570 DTS to make the LTE hardware fit by assumption.
4. Add explicit T575 model/firmware and partition validation to any future boot builder. Maintain deny-by-default behavior for installer, flash, wipe, restore and signed-image update paths until a T575-specific recovery procedure and image have been verified.
5. Start with an offline kernel/DTB build and static checks. Only then consider a reversible BOOT-only experiment with the owner's preserved, tested restoration method and separate approval.
6. Treat modem/mobile data as a **separate phase** after a reliable non-cellular boot. Do not touch EFS, sec_efs, modem calibration, provisioning or identity partitions.

## Boot/flash safety invariants

- No auto-flash of T570 images to T575. **Do not invoke `./setup.sh` to install or test the LTE model**; the inherited script targets SM-T570.
- Never write `efs`, `sec_efs`, `persistent`, `param`, `up_param`, RPMB, modem identity/calibration, or bootloader partitions.
- Never use recovery factory reset to recover from a Linux test: previous Samsung KnoxGuard/Prenormal behavior makes that hazardous.
- Do not assume the T570's `undo` procedure will restore the rooted T575. Preserve the device's *actual currently working* BOOT image and matched Android firmware securely off GitHub.
- Never commit partition dumps, device identifiers, stock/vendor binaries, firmware blobs, Magisk-patched images, keys, or serial/IMEI/MAC values. This fork is public.
- The development workstation is an Apple Silicon Mac. Read-only ADB collection and source editing can run there; a Linux VM or runner is expected for the full upstream build toolchain.

## Milestones

- [x] Independent fork and LTE development branch
- [x] Capture prior root/flash experience without private artifacts
- [ ] New T575 read-only device snapshot and T570 comparison
- [ ] New LTE device-tree source and compile-only build
- [ ] T575-specific boot-chain analysis and recovery verification
- [ ] BOOT-only test (explicitly approved, reversible)
- [ ] GPU, display, touch, input and storage bring-up
- [ ] Wireless, audio, charge, suspend and S Pen
- [ ] LTE modem and GNSS
- [ ] LTE-specific postmarketOS Duranium image and updates

See the original T570 documentation for its development status, **not** as evidence of T575 hardware compatibility.

## Actual rooted-ADB inventory, 2026-11-05 (SM-T575 / T575XXSFEYI1)

Source: owner-supplied output of `scripts/t575-inventory.sh --root`. **Only non-identifying hardware facts are included here**, not raw inventory, device identifiers or partition dumps.

| Area | SM-T575 observation | SM-T570 upstream evidence | Implication |
| --- | --- | --- | --- |
| SoC | Exynos 9810, `universal9810`, vendor 4.9.191 kernel | Same Exynos 9810 / vendor 4.9.191 | Shared SoC driver work likely reusable; board wiring not proven |
| Samsung codename | `gtactive3` | `gtactive3wifi` | Separate `gtactive3lte` DTS/model verification needed |
| Audio codec | `rt5665` on 3-001b | `rt5665` on 3-001b | Likely reusable audio-codec layer |
| **Speaker amplifier** | **TAS2562** at I2C 5-004c | **RT5510** at I2C 4-0034 on tested T570 hardware revision 4; T570 hardware notes mention TAS2562 on another revision | Do not reuse RT5510 board wiring; compare the TAS2562 DT/driver and audio-machine routes |
| S Pen | `w90xx` on I2C 7-0056 | Wacom W90xx on I2C 6-0056 | Pen present; buses numbered differently, compare DT identities and wiring |
| Touchscreen | `sec_touchscreen`, SPI 21 alias `hxcommon` | Himax touchscreen on SPI 21 | Candidate reuse; need actual DT sensor ID and reset/IRQ pins |
| NFC / PMIC / MUIC | `sec-nfc`, `s2mps18mfd`, `max77705`, `sm5504_muic_pogo` | Same families documented | Likely shared drivers, but wiring still must be checked |
| Camera | camera sensor on 0-002d, 1-0037; actuator at 2-000c; EEPROM at 2-0058 | Same sensor addresses, actuator/EEPROM arrangement can vary | Confirm camera models and regulators from DTB |
| Device's boot security (current output) | `ro.boot.flash.locked=1`; `ro.boot.vbmeta.device_state=locked`; `ro.boot.verifiedbootstate=green`; `ro.boot.warranty_bit=0` | Upstream T570 used unlocked, orange verified boot | **Possibly masked Android properties**: prior Magisk unlock/root succeeded and owner confirms OEM unlocking enabled and device unlocked. Integrity-spoofing modules may explain locked/green getprop values; these properties alone cannot establish actual bootloader lock. Verify through Download mode before any flash |
| Storage | `sda` has 31 partitions, BOOT position `sda12` (60,416 KiB), DTBO `sda10` (8,192 KiB), userdata `sda31` | T570 notes list the same partition indices; sizes need strict check | Promising but **not** proof of interchangeable boot images |
| LTE modem | Not enumerated by the present I2C/SPI-only inventory | Wi-Fi model has no LTE port | Modem transport and firmware remain unknown; investigate separately |

### Immediate gate

The current Android **locked/green** properties conflict with the earlier successful unlock/root test and the owner's direct confirmation of an unlocked device. The tablet has run Magisk, TrickyStore and Play Integrity Fix, making property spoofing a possibility, not a verified explanation. Android getprop results alone should not be used to label the bootloader locked. Verify actual Download-mode state before any invasive action; no need to repeat unlocking or disrupt the working Magisk setup.

### Next read-only evidence

- On the Mac, inspect `adb shell getprop ro.boot.flash.locked`, `adb shell getprop ro.boot.vbmeta.device_state`, `adb shell getprop ro.boot.verifiedbootstate`, `adb shell su -c id` to confirm the discrepancy (no flashing).
- Extract the **live device tree** with `adb exec-out su -c 'cat /sys/firmware/fdt'` to a **local private file** (if readable). Do not publish raw DTB; some paths may include identifiers.
- Compare decompiled SM-T575 and upstream SM-T570 DTBs/DTBOs locally before drafting an LTE DTS. Verify actual amplifier regulator/GPIO routing and modem interfaces.
- Continue refusing the inherited T570 installer on the LTE device.

### Bootloader status clarified from kernel command line (2026-11-05)

The owner checked `/proc/cmdline` with Magisk root. The live kernel boot arguments report:

- `androidboot.verifiedbootstate=orange`
- `androidboot.vbmeta.device_state=unlocked`
- `androidboot.warranty_bit=1`
- `androidboot.revision=5`
- `androidboot.dtbo_idx=5`
- `androidboot.bootloader=T575XXSFEYI1`

This is strong evidence that **the tablet is unlocked**, consistent with successful patched-boot tests and the owner's confirmation. The Android `ro.boot.*` properties in the earlier inventory instead reported green/locked/warranty 0; they conflict with the kernel cmdline and may be altered by the device's Play Integrity configuration. The specific cause has not been established. Do not interpret the earlier properties as proof of a locked bootloader. This does **not** establish that a new Linux image will boot correctly; preserve restoration procedures and do not flash yet.

The owner has also extracted a **269 KiB live device tree** locally. Its validity/content has not been inspected yet. Raw DTBs and boot parameters may contain unique device identifiers; do not commit them to the public repository. The raw kernel command line included identifying fields that have deliberately been omitted here.

## Validated live FDT examination (2026-11-05)

The owner supplied a 275,783-byte FDT v17 with valid `0xd00dfeed` magic and parsable structure (1,289 nodes, 9,499 properties). This is the **running Android DT**, not a compiled mainline Linux DTS. It is deliberately **not stored in Git**.

Confirmed high-value findings:

- Board root `model = "Samsung GTACTIVE3 EUR OPEN 04 based on EXYNOS9810"`; root compatibles `samsung,armv8`, `samsung,exynos9810`. Kernel cmdline reports revision 5 and DTBO index 5. Model text is Samsung's board label and is not a Linux compatible string.
- `/hsi2c@108C0000/tas2562@4c`: `compatible = "ti,tas2562"`, address `0x4c`, `status = "ok"`. The sibling `rt5510@34` is **disabled**. The tested SM-T570 rev4 upstream DTS currently enables RT5510, while upstream HARDWARE.md already notes that its revision 5 uses TAS2562. **Mainline audio board integration must select TAS2562 and validate reset/IRQ/supplies/DAI before enabling sound.**
- `/sound`: `compatible = "samsung,exynos9810-audio-TI"`, rather than the Wi-Fi board's RT5510-oriented routes. Inspect TAS2562's audio link and upstream kernel driver coverage before constructing audio bindings.
- `/hsi2c@10910000/wacom@56`: `wacom,w90xx` at 0x56 (Wacom S Pen).
- `/reserved-memory/modem_if`: `compatible = "exynos,modem_if"`, reserved region base 0xf0000000, length 0x09200000; `/mif_pdata`: `compatible = "sec_modem,modem_pdata"`. **These prove Android describes a modem interface, not that mainline modem driver support exists.**
- `/pcie0@116A0000`: enabled; `/pcie1@116B0000`: disabled in the running Android DT. The upstream T570 Linux patch 0071 in fact uses PCIe0 for BCM4375 (an earlier summary incorrectly referred to PCIe1). **Do not assume GPIOs/regulators/firmware are identical merely because the controller is shared**. Determine actual Wi-Fi/modem bus ownership and pinctrl from the T575 DT and runtime before enabling either port.
- `/decon_board_hx83102e` exists, supporting the Himax panel-family identification, though panel timing/power sequencing still needs explicit comparison.
- Live inventory previously confirmed RT5665, MAX77705, S2MPS18, SM5504, and the other listed shared hardware families.

**Porting impact:** The first LTE-specific DTS should be based on a careful comparison of the fully assembled upstream Linux DTS to the sanitized Android hardware mapping, with LTE-specific audio, PCIe and modem sections disabled until supported. No T575 boot image, build test or flash is validated yet. The raw FDT may contain serial/identity properties and must remain private.

Next: extract the **merged effective** T570 mainline DTS from the assembled upstream Linux tree (the patch series alone is not the complete final DTS); confirm the T575 TAS2562 driver/bindings and PCIe dependencies, and create a compile-only LTE target. Keep the upstream installer blocked on SM-T575 pending separate boot-chain verification.

## First compile-only LTE source (2026-11-05)

- Added `dts/exynos9810-gtactive3lte.dts` including the assembled T570 board DTS, overriding model/compatible and deliberately disabling the inherited RT5510 sound card/amp, PCIe0 Wi-Fi and Bluetooth. This is a conservative **compile-only experiment**, not a boot-safe or production DT.
- Added `scripts/build-t575-dtb.sh` and `docs/T575-DTB-BUILD.md` for a future local build against the fully patched upstream kernel checkout.
- **No kernel compilation or boot tests have yet been performed** in the current environment (complete patched kernel checkout/build dependencies unavailable). Do not flash this target.

## Measured SM-T575 live-FDT RAM and carveouts (2026-11-05)

Read from the privately uploaded **running** Android DTB; device-specific
identifiers have been omitted. All addresses/sizes below were read from DT
`reg` cells, not inferred from a generic Exynos datasheet.

| Physical DRAM start | Length |
| --- | --- |
| `0x80000000` | `0x3c800000` |
| `0xc0000000` | `0x20000000` |
| `0xe1900000` | `0x1e700000` |
| `0x880000000` | `0x80000000` |

**These four DRAM banks agree exactly with the memory layout shown in the
initial upstream T570 Linux patch 0003.** That is promising but does not
validate all RAM reservations.

LTE-specific and important shared reserved regions observed:

| Stock node | Start | Length | End (exclusive) |
| --- | --- | --- | --- |
| `/reserved-memory/modem_if` | `0xf0000000` | `0x09200000` | `0xf9200000` |
| `/reserved-memory/cp_ram_logging` | `0xf9200000` | `0x02000000` | `0xfb200000` |
| `/reserved-memory/abox_rmem@0xEA800000` | `0xfb200000` | `0x02800000` | `0xfda00000` |
| `/reserved-memory/bootloader_fb` | `0xca000000` | `0x01400000` | `0xcb400000` |

**Caution:** The A-Box node name embeds `0xEA800000` but the live
`reg` property actually maps `0xfb200000`; use actual `reg` and
recheck downstream firmware use rather than assuming the node name is
authoritative. The vendor FDT doesn't necessarily say `no-map` for
every region; Linux should avoid loading drivers or allocating RAM that
might collide with still-active modem / coprocessor firmware.

Before any boot test, diff **all** stock `reserved-memory` entries and
`/memreserve/` entries against the fully assembled LTE DTB, confirm
bootloader/kernel ownership and all overlapping regions, then add only
the necessary carveouts with valid mainline bindings. Do not regard
matching DRAM banks or a successfully compiled identity-only DTB as
safe for flashing. The stock binary stays local and private.

## Stage 4: Non-destructive boot-chain preflight (2026-11-05)

The Stage 3 fixed memory-carveout compile/audit workflow
[run 42039820541](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/42039820541)
succeeded. This does **not** establish boot safety.

The upstream T570 documentation has a working
S-Boot → uniLoader → U-Boot → systemd-boot → UKI
chain and a device-specific installer. **Its T570 installer and images are
not validated for, and must not be run on, the T575.**

A read-only helper for the owner's Mac has been added:
`scripts/t575-boot-preflight.sh`. From the repository checkout:

```bash
bash scripts/t575-boot-preflight.sh
```

Prerequisites: Android booted, USB debugging authorized, Android platform-tools
`adb` on PATH, and exactly one ADB device connected. The script verifies
`ro.product.model=SM-T575` before collecting any data. It writes a locally
stored, private directory with Android identity/boot properties, kernel
command line, by-name partition list, kernel version and mount table.
It performs **no** reboot, root escalation, raw partition reads, write,
unlock, image generation or flashing. Because these outputs may contain
device identifiers or boot details, keep the folder local/private and never
upload it verbatim to public GitHub.

The read-only report is only **one part** of the next boot-chain gate.
Before proposing even a reversible boot attempt, still required:
- Verify actual Download-mode bootloader unlock state rather than relying
  exclusively on possibly spoofed Android `ro.boot` properties.
- Identify the exact stock T575 BOOT partition image/format including
  Magisk changes, DTB/DTBO selection, and Samsung boot header v2.
- Validate backup and reliable restore for the **current working rooted
  Android**, without factory reset or writing EFS/identity/bootloader areas.
- Check Linux kernel load addresses, U-Boot/uniLoader compatibility,
  reserved-memory safety, and the T575 display/USB debugging route.
- Decide how to obtain reversible boot testing on this Samsung model:
  Samsung Download mode is **not** evidence of Android fastboot or support
  for a generic `fastboot boot` RAM-only approach.
- Retain **deny by default** for any T575 image generation, installer,
  flash or wipe commands until those gates pass.

**Do not flash or boot with the current compile-only DTB.** Following a
successful kernel bring-up, the intended GUI remains **Plasma Mobile**.


## Stock DTBO overlay 5: verified peripherals (2026-11-05)

Owner extracted the selected Samsung overlay index 5 (Android DT table version
0, six entries; overlay at `0x900e0`, size 119332 bytes) from the private
T575 DTBO partition and decompiled it locally. These are *stock Android*
device-tree values, **not** validation of mainline driver compatibility or
permission to flash. The raw DTBO and decompiled firmware are deliberately
excluded from the public repository.

### Panel power and transport

- `hx83102e` display node: four DSI lanes, 60 Hz, power GPIO LDO
  `gpg2-2`, buck `gph1-4`, reset `gpa3-4`, `gpio_con` on `gpa2-5`.
- Stock power-up description asserts LDO, delays 2000 microseconds,
  asserts buck, delays 2000 microseconds; reset sequence is high 2000,
  low 1000, high 6000 microseconds. Do **not** transcribe vendor
  string-programmed sequences directly to Linux standard GPIO/regulator
  properties without checking polarity, voltage and sequencing.
- Panel node `resolution = <0x258 0x780>` (600×1920) while touch
  coordinates are 1200×1920, and inherited T570 simple framebuffer is
  1200×1920. Determine why the values differ before writing DRM timings.
- Framebuffer handover is 20 MiB at `0xca000000`, already reserved by
  compile-only DTS.

### Touch and stylus

- Himax `himax,hxcommon` at `spi_21`, `reg = <0>`,
  `spi-max-frequency = <0x6acfc0>` (7 MHz), IRQ `gpa1-0`,
  reset `gpg0-6`, controller-data CS `gph0-7`.
  Touch/display coordinates 1200×1920; firmware path
  `tsp_himax/hx83102e_gtactive3.bin`.
- Wacom `wacom,w90xx` at `hsi2c_23`, address `0x56`,
  IRQ `gpa3-3`, pen detect `gpa3-7`, FW enable `gpm41-0`,
  supply `wacom_ldo_en` (3.3 V, boot-on), firmware path
  `epen/w9019_gtactive3.bin`. Calibration and axis invert still
  require driver work.

### Audio amplifier selection resolved

- Earlier fragment 19 declares Richtek `rt5510@34` as enabled.
- **Later fragment 101 explicitly sets `rt5510@34 status = "disabled"`**
  and declares `ti,tas2562` at address `0x4c`, `status = "ok"`,
  reset `gpm40-0`, IRQ `gpa1-1`, `#sound-dai-cells = <1>`.
- Thus the selected overlay intends TAS2562, not RT5510. Its ASoC
  machine description also names `samsung,exynos9810-audio-TI` and
  references the `tas2562` DAI.
- **No active Linux TAS2562 device was proven by this static reading.**
  Keep inherited T570 audio disabled during any future initial boot
  bring-up until driver, supply, pinctrl and codec routing are audited.

### Important next gates

Compare parent/controller paths, pinctrl labels, and regulator supply
names to the compiled T570-derived Linux DTB; translate only verified
compatible bindings. Inspect panel timing and reset polarity; do not
enable touchscreen/S Pen/audio on an unverified kernel. Keep LTE modem
driver off for first-stage bring-up. No T575 boot testing/flash is
authorized by these findings.
