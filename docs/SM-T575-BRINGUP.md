# SM-T575 LTE bring-up: previous-device evidence and safety plan

Status: **research / read-only inventory only**. No SM-T575 boot image or validated DTB exists in this branch. The upstream SM-T570 installer, release images and firmware packages **must not be used on the SM-T575**.

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
