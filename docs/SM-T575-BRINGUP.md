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
