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


## Stage 5 CI: Linux peripheral inventory (2026-11-05)

[Run 42045638678](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/42045638678)
completed successfully. The advisory audit `scripts/audit-t575-peripherals.py`
enumerated the compiled, T570-derived T575 Linux DTB. Its output
is **static evidence only** and must not be interpreted as driver probe,
device communication or proof of safe power sequencing.

Key observed compiled Linux nodes:

| Area | Compiled Linux DT path | Status / compatible |
| --- | --- | --- |
| Touch | `/soc@0/usi@13ae00c0/spi@13ae0000/touchscreen@0` | okay / `himax,hx83102e` |
| Wacom | `/soc@0/usi@109100c0/i2c@10910000/digitizer@56` | okay / `wacom,w9019` |
| Display controller | `/soc@0/display-controller@16030000` | okay / `samsung,exynos9810-decon-takeover` |
| Boot framebuffer | `/chosen/framebuffer-0` | `simple-framebuffer` |
| Native panel node | `/panel` | **disabled** |
| Headset codec | `/soc@0/usi@104800c0/i2c@10480000/audio-codec@1b` | okay / `realtek,rt5665` |
| Wi-Fi-derived amp | `/soc@0/usi@108c00c0/i2c@108c0000/amplifier@34` | **okay / `richtek,rt5510`** |
| Wacom supply | `/regulator-wacom` | okay / `regulator-fixed` |
| A-Box controller | `/soc@0/audio-controller@17c50000` | okay / `samsung,exynos9810-abox` |

**Important hardware mismatch**: The selected stock SM-T575 overlay 5
declares `ti,tas2562` at I²C address `0x4c` and explicitly disables
`rt5510@34` in a later fragment. The inherited Linux DTB still
describes RT5510 as enabled. **Do not assume the current Linux audio
configuration is safe to boot or can successfully probe the LTE hardware.**
Audit whether the appropriate TAS2562 binding and ASoC topology are
available; if any early test image is considered, explicitly exclude
or disable unverified amp probing before testing.

**Display prerequisite**: The Linux panel node remains disabled; the
current `simple-framebuffer` plus DECON takeover is not proof that
Linux can natively reinitialize HX83102E. Validate display handover,
power sequencing, resolution mismatch (600×1920 panel vendor field
vs 1200×1920 effective framebuffer/touch), and GPIO polarity.

**Touch/pen prerequisite**: Paths suggest Linux descriptions already
exist for Himax on SPI `0x13ae0000` and Wacom on I²C `0x10910000`.
Confirm Samsung's SPI21/HSI2C23 aliases map to those addresses, compare
GPIO pinctrl and supplies and verify firmware loading before assuming
device operation. The advisory audit's `okay` status reflects the
device-tree property, not actual hardware behavior.

The next step is to inspect the inherited T570 DTS/pinctrl/ASoC
binding and make **targeted compile-only LTE overrides** where
fully justified. Do not flash the current DTB.


## Stage 6: Audio isolation and display/input static gate (2026-11-05)

The inherited SM-T570 Linux DTB enabled `richtek,rt5510` at
`/soc@0/usi@108c00c0/i2c@108c0000/amplifier@34`. The selected
Samsung SM-T575 overlay 5 instead marks RT5510 **disabled** and selects
TI TAS2562 at `0x4c`. The LTE compile-only board DTS now explicitly
disables the inherited `amplifier@34` and entire `/sound` machine node.
This avoids describing the known-wrong audio configuration as active.
**No TAS2562 node is activated yet**: the exact supplies, GPIOs, binding,
and audio machine/DAI topology need a separate driver audit.

The `scripts/audit-t575-peripherals.py` CI check now fails if the compiled
DTB does not preserve the expected static configuration: RT5510 and
`/sound` disabled; Himax `himax,hx83102e` at SPI controller
`0x13ae0000`, Wacom `wacom,w9019` at I²C controller `0x10910000`,
both still described as okay; and native `/panel` disabled until
power/reset and DRM timing verification. It also rejects an unexpectedly
enabled `ti,tas2562` node. It doesn't establish actual hardware probing
or safe physical boot. A reported `okay` node is a description only.

**Next priority:** Inspect compiled properties (SPI speed/CS, pinctrl,
firmware, IRQ/reset; I²C/Wacom regulator and pen calibration) and compare
their bindings to the measured stock overlay 5 before applying functional
LTE changes. Independently validate display handover and native panel
timings. Preserve read-only testing and do not flash this DTB.


## Stage 8: Static GPIO/phandle and display handover inspection

Stage 7 CI run [42049985279](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/42049985279)
passed: the compiled LTE Linux DTB now specifies Himax SPI at **7 MHz**
(matching selected stock overlay 5), chip select 0, Wacom address
`0x56`. Stage 8 adds
`scripts/audit-t575-display-input.py`, which resolves Linux DT
phandles in the compiled binary to report the specific GPIO and pinctrl
providers, Wacom power supply, and simple framebuffer properties.

Measured *vendor* reference pins from the extracted private overlay 5:

- Touch: IRQ **GPA1_0**, reset **GPG0_6**, SPI CS **GPH0_7**.
- Wacom: IRQ **GPA3_3**, pen-detect **GPA3_7**, firmware enable **GPM4_1**,
  `wacom_ldo_en` rated at 3.3 V.
- Panel: board control **GPA2_5**, LDO enable **GPG2_2**, buck enable
  **GPH1_4**, panel reset **GPA3_4**.
- Samsung HX83102E vendor panel declares four DSI lanes, 60 Hz, and
  `resolution=<600 1920>`, while simple framebuffer and touchscreen
  indicate 1200×1920. Native panel timing, polarity, horizontal scaling,
  and power sequencing are **not** verified.

Stage 8 is a read-only *compiled FDT property audit*, **not** a probe
and **not** a guarantee of driver, pinmux or regulator compatibility.
No T575 peripheral is newly enabled. Native panel and the inherited
RT5510/AsoC board audio remain disabled until separate physical and
driver compatibility validation. Do not flash Linux binaries.


## Stage 8 results: resolved Linux phandles (2026-11-05)

[GitHub Actions run 42051671853](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/42051671853) **passed** its compile-only checks.

- Himax `/soc@0/usi@13ae00c0/spi@13ae0000/touchscreen@0`:
  interrupt-parent resolves to `/soc@0/pinctrl@14050000/gpa1-gpio-bank`;
  `interrupts=<0 2>`; `reset-gpios=<phandle 6 1>`
  resolves to `/soc@0/pinctrl@10430000/gpg0-gpio-bank`.
  Pinctrl references resolve to `touch-irq-pins` and
  `touch-rst-pins`. The SPI speed is 7 MHz.
  The numeric final GPIO/IRQ cells' precise polarity semantics
  remain dependent on the binding and driver.
- Wacom `/soc@0/usi@109100c0/i2c@10910000/digitizer@56`:
  interrupt-parent resolves to `gpa3-gpio-bank`, `interrupts=<3 8>`,
  `vdd-supply` resolves to `/regulator-wacom`, and pinctrl points to
  `epen-irq-pins`.
- Wacom supply `/regulator-wacom`: `regulator-name=wacom_3.3v`,
  minimum and maximum both 3,300,000 microvolts.
  The control `gpio=<phandle 0 0>` has not yet been traced to a bank.
- Simple framebuffer `/chosen/framebuffer-0`: width 1200, height
  1920, stride 4800 bytes, `x8r8g8b8`. It lacks a direct `reg` but
  has `memory-region` linked to
  `/reserved-memory/framebuffer@ca000000`. Confirm boot framebuffer
  driver/hand-over binding handles that representation before boot.
- Native `/panel` stays disabled, lacks `compatible`,
  reset/enable GPIO and supply properties, and references a
  `/soc@0/backlight@16080000` provider. Thus **native HX83102E
  initialization is not implemented** by the current DTB.

All findings are static phandle resolutions from a **compiled Linux
DTB**, not observations of live Linux drivers or validated pin polarity.
Do not flash or enable the panel on this evidence alone. The next gates
are controller GPIO polarity verification, Wacom enable-line mapping,
the boot framebuffer handover implementation, and suitable native
panel binding/DSI timing design.


## Stage 9: Linux display-handover validation (compile-only)

CI now runs `scripts/audit-t575-display-handover.py` against the compiled
SM-T575 DTS to verify the **description** of the bootloader framebuffer:

- `/chosen/framebuffer-0` uses `simple-framebuffer`,
  1200×1920, 4800 bytes/line, `x8r8g8b8`: visible data
  occupies 9,216,000 bytes.
- The `memory-region` phandle must point to
  `/reserved-memory/framebuffer@ca000000`, whose stock
  handover reservation is `0xca000000` + `0x01400000`
  (20 MiB), with `no-map`. The visible surface must fit.
- The Linux simple-framebuffer **YAML binding explicitly permits
  `memory-region` instead of `reg`**: its region overrides any
  `reg` property. Hence lack of `reg` by itself is not a
  correctness failure. Reference:
  https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/display/simple-framebuffer.yaml
- `/soc@0/display-controller@16030000` must describe
  `samsung,exynos9810-decon-takeover`; `/panel` must
  stay disabled while native HX83102E driver, DSI timings, regulator
  supplies, GPIO polarity and sequence are unresolved.

**LIMITATIONS:** This verifies only the compiled device-tree metadata,
not whether the kernel's actual DECON driver supports seamless
handover, whether the framebuffer address is what the bootloader
scans out, or whether display clocks/power survive Linux initialization.
No native panel/DSI power-up is authorized. The vendor overlay's
`resolution=<600 1920>` and the 1200×1920 framebuffer remain
unreconciled.

**Before considering any boot:** inspect the pinned kernel's
`exynos9810-decon-takeover` driver and simple framebuffer interaction,
verify bootloader scanout and display clock ownership, and establish
a tested, reversible restoration method. Do not flash the present DTB.


## Stage 10: actual DECON takeover driver source review (2026-11-05)

Audited the **specific pinned upstream T570 kernel patch**:
`patches/linux/0124-drm-Add-an-Exynos9810-DPU-takeover-KMS-driver.patch`
([upstream source](https://github.com/exynos-linux/samsung-gtactive3wifi/blob/main/patches/linux/0124-drm-Add-an-Exynos9810-DPU-takeover-KMS-driver.patch)).

The driver is not a native panel init implementation. Its comment says
S-Boot already configured DECON0 and **both DSI links** and window 5
from IDMA_G0 with the display controller bypassing SysMMU. Its
`e9810_probe` reads the current `IDMA_IN_BASE_ADDR_Y`,
checks only for nonzero, then evicts any existing simpledrm occupant
via `aperture_remove_conflicting_devices()` and attempts to claim
the framebuffer aperture. Its `e9810_flip` writes a new IDMA base
address and requests a DECON shadow update for the assumed window.
The driver does **not** explicitly reprogram power sequencing, DSI
timings or panel initialization. The author reports successful
framebuffer console takeover on **SM-T570**, not SM-T575.

**Important unverified SM-T575 runtime assumptions:**

1. Same S-Boot window 5, IDMA_G0 mapping, format, source geometry,
   and DECON register configuration as the T570.
2. Read IDMA base is inside the T575 0xca000000–0xcb400000 fixed
   handover reservation, is actually being scanned out, and its DMA
   mapping works with the driver-selected 32-bit DMA mask.
3. SysMMU bypass state, shadow-register update behavior, display
   clock retention, DECON IRQ routing, and vblank behavior.
4. Simpledrm availability in the kernel configuration; the
   `/chosen/framebuffer-0` DT description alone does not ensure
   a usable display or safe takeover.

**Action applied now:** The SM-T575 compile-only DTS overrides
`/soc@0/display-controller@16030000` with
`status = "disabled"`, preserving the simple-framebuffer DT
description and leaving `/panel` disabled. This prevents the
unvalidated T570 takeover device from being described as active
on T575 and avoids claiming a successful scanout transition that
has never been observed on LTE hardware. The Stage 10 CI gate
`scripts/audit-t575-decon-source.py` verifies the pinned patch's
critical takeover behavior and insists the T575 DECON + native
panel remain disabled. It does **not** prove the alternative simpledrm
display works on hardware.

Before enabling DECON takeover: collect *read-only* trustworthy
runtime S-Boot/DECON scanout register data if obtainable with
a well-understood procedure, and verify driver clock/IRQ and
framebuffer ownership assumptions. Until safe restoration is
demonstrated, keep all testing compile-only and do not flash.


## Stage 11: built-in simpledrm compile-only compatibility gate (2026-11-05)

Stage 10 left the T575 DECON takeover and native panel disabled. Stage 11
tests the *alternative early display description* at static build time
without making a boot image or touching Android.

- The CI kernel configuration requests `CONFIG_DRM=y` and
  `CONFIG_DRM_SIMPLEDRM=y`, runs `olddefconfig` to resolve dependencies,
  and fails if either is not built in. This **does not compile or test a
  complete kernel image**: it verifies the resolved configuration only.
- `scripts/audit-t575-simpledrm.py` checks the compiled DTB retains the
  1200x1920 XRGB8888 (`x8r8g8b8`) handover description, 4800-byte
  stride and 20 MiB reservation, with DECON takeover and native panel
  still disabled. The Stage 9 audit separately validates the
  `memory-region` phandle target.
- The inherited bootloader framebuffer binding uses `memory-region`,
  not a direct `reg`; support must be confirmed against the exact
  selected kernel driver at runtime. Static checks alone cannot prove
  the firmware continues scanning out or that the screen lights up.
- The existing GitHub Actions job still produces **DTB only**. No BOOT
  image, automatic installer, flashing command, or published firmware
  is created.

**Unresolved before first boot:** Review the CI result, confirm the exact
kernel source/build config and simpledrm binding, investigate actual
S-Boot scanout address and framebuffer ownership via safe read-only
methods, and prove a T575-specific reliable recovery path. No changes
to `efs`, `sec_efs`, modem identity partitions or working Android.
Do not flash this DTB.


## Stage 12: read-only Android framebuffer/boot ownership evidence (2026-11-05)

The owner reported Stage 11 finished. The connector did not expose a
successful GitHub Actions conclusion (combined commit statuses and PR-run
lookup both returned empty lists), so **Stage 11 CI success is not
independently verified here**. Stage 12 proceeds only with non-invasive work.

Added `scripts/t575-stage12-display-evidence.sh` for the owner's Mac.
It refuses anything other than exactly one authorized Android ADB device
whose `ro.product.model` is `SM-T575`, requires working Magisk `su`,
and captures read-only framebuffer/sysfs descriptions, `/proc/iomem`,
selected boot-time display logs, and boot metadata. It writes into a
private, newly created local directory. No raw partition contents, MMIO
reads, sysfs writes, reboot, flash, boot-image generation, unlock or
module load are performed.

Run from the Mac while the existing rooted Android is booted:

```bash
bash scripts/t575-stage12-display-evidence.sh
```

**Privacy:** The results may include serial-like boot parameters or other
unique identifiers. Do not commit or paste the unredacted directory into
this public repository. Inspect/redact before sharing selected excerpts.

**Interpretation boundary:** This snapshot describes **Android's** current
framebuffer and memory mapping. It does not necessarily reveal S-Boot's
pre-Linux scanout state, nor prove that the Linux `simpledrm` path can
keep the panel lit. Android may mask `/proc/iomem`; absent or zeroed
addresses are inconclusive. Directly reading live DECON MMIO registers
is deliberately *not* attempted, because safe clock/power-domain access
and read permissions have not been demonstrated.

**Stage 12 hardware gate remains open** until the private results are
reviewed and a T575-specific, tested restoration path is established.
The LTE DTB must remain compile-only. Do not flash or alter Android.
