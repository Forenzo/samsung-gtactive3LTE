# SM-T575 Phosh native installation and desktop-convergence plan

**Active development branch:** `work/t575-phosh-convergence`
**Retained Plasma branch:** `work/t575-gpu-genpd-config-review`

Plasma's NFS/Cage GPU milestones remain preserved in the retained branch. Do
not merge this Phosh branch back into Plasma or rewrite its history. The
current owner choice (2026-11-17) is the upstream-style **native postmarketOS
Duranium Phosh** install, not NFS. Loss of Android `userdata` is accepted,
but protected identity/boot-security partitions must remain untouched.

## Use upstream design, adapted to the LTE device

Verified Wi-Fi architecture: Samsung S-Boot → uniLoader → U-Boot →
systemd-boot → native Duranium image with Phosh installed inside `userdata`.

Already committed in this Phosh branch:
- `.github/workflows/t575-lte-phosh-first-desktop.yml`: build the local LTE
  native Duranium Phosh `.raw.zst` image (never publishes or flashes).
- `.github/workflows/t575-lte-phosh-chain-boot-review.yml`: compile the
  separate LTE `uniLoader-chain-gtactive3` payload (never flashes).
- Existing LTE DTS, GPU power workaround and `device-samsung-gtactive3`.
- `config.toml` keeps LTE `images = false` until first boot confirmed.
- The earlier lightweight NFS userspace build is NOT the selected install
  method. It remains in Git history for reference only.

**Not yet proven** on the physical SM-T575: the complete LTE U-Boot chain,
systemd-boot, signed-image acceptance, native Phosh encrypted first boot,
and an end-to-end *non-wiping recovery after chain failure*. Successful
standalone Linux GPU/Plasma boot does not verify these handovers.

## Before writing to userdata or BOOT

1. Confirm EXACT physical model SM-T575 (not SM-T570/577), bootloader
   `T575XXSFEYI1`, unlocked state, PIT identities, and `userdata` / BOOT
   partition lengths. Do not reuse Wi-Fi assumptions without verification.
2. Keep the exact rooted Android BOOT image archived on the Mac:
   61,865,984 bytes; SHA-256
   `a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372`.
   Keep the DTBO backup (8,388,608 bytes) and the working diagnostic BOOT
   candidate separately. Verify local checksums *immediately before use*.
3. Obtain and verify final CI artifacts: LTE native `.raw.zst`, LTE
   chainloader + diagnostic loader and manifest. Require explicit LTE
   board/DTB select and offline BOOT v2 size/AVB/PIT admission.
4. Ensure a real recovery route: rooted Android BOOT restore has already
   worked; Duranium data cannot be undone simply by reflashing BOOT.
   A clean Android reset/restore procedure must account for Samsung
   KnoxGuard. EFS, SEC_EFS, PRISM, VBMETA, bootloader, PARAM, DTBO and
   unrelated partitions are never write targets.
5. The current upstream installer still **deliberately blocks LTE install**:
   `scripts/installer/lib/flow.sh` stops on `VARIANT=gtactive3`,
   `bootimg.sh` suppresses `BOOT_CHAIN`, and `release.sh` omits the LTE
   chainloader payload check. Do not bypass a single condition manually:
   a reviewed, LTE-specific opt-in path must update all three together,
   with non-bypassable model/geometry checks and a dry run first.
6. Do not run the Wi-Fi `./setup.sh install` as-is. The upstream
   `docs/INSTALL.md` currently documents SM-T570 only. Mac is the build
   host, but `setup.sh` currently requires a Linux host; any installer
   must explicitly support macOS/Heimdall or use a controlled Linux host.
7. Only after all gates pass, erase **userdata only**, verify the image
   readback, flash BOOT chain with a checked LTE loader, and perform the
   encrypted native first boot. No NFS path, no Plasma installation, no
   `super` repartition or destructive root reconfiguration.

## Verified offline progress, and first-boot input requirement (2026-11-18)

- Native LTE Phosh image, EFI and eight compressed parts passed CI and
  owner-side SHA-256 verification. Both offline Android BOOT v2 candidates
  fit the measured 61,865,984-byte BOOT and verified their AVB footers;
  neither has been physically tested.
- The measured BOOT partition is /dev/sda12, and userdata is /dev/sda31
  with 4096-byte sectors. The stock Android BOOT backup is verified.
  The previously working Linux diagnostic BOOT image is
  `~/Downloads/SM-T575-Recovery/t575-gpu-BOOT-CANDIDATE.img`,
  SHA-256 `8225061aa97b72f41f27ffc0119d84f1fd22c0d6b009d5e123b811f1796792f7`.
- The initial experimental LTE chain archive embedded Wi-Fi-default U-Boot;
  a dedicated LTE U-Boot configuration is now built for opt-in test builds.
  **Do not flash any existing chain candidate until the newly built archive
  and recovery behavior are reviewed.** The LTE uniLoader board still has
  no watchdog/volume-key fallback hooks, unlike the Wi-Fi variant.
- **Touch must work before we call Phosh usable.** The common LTE-inherited
  DTS already declares the HX83102E touchscreen on SPI21, and the packaged
  kernel config builds `CONFIG_TOUCHSCREEN_HIMAX_HX83112B=m`,
  `CONFIG_INPUT_EVDEV=y`, and `CONFIG_TOUCHSCREEN_WACOM_W9000=m`.
  This only proves build configuration: we must inspect Linux dmesg,
  SPI binding, and physical `/dev/input/event*` touch events first.
  The Wacom pen is separate from finger touch. Do not claim that Phosh's
  menus are interactive until fingers actually generate events.
- U-Boot's bootmenu is a distinct pre-Linux environment and currently uses
  physical keys through `button-kbd`; it has no HX83102E input driver.
  Keep volume/power recovery controls. Supporting touch in U-Boot would
  require a separate SPI touchscreen and menu-input implementation, not
  a Linux or Phosh setting. Do not delay Linux touch bring-up on U-Boot touch.
- The read-only Mac diagnostics script `tools/t575-touch-readonly-check.py`
  examines the running diagnostic console without writing to the tablet.

## First LTE U-Boot hardware inspection (NO FLASH PERMISSION YET)

The experimental LTE-specific U-Boot configuration now has:
- an LTE-default device tree if the S-Boot handoff has no identifying FDT;
- a dedicated `gtactive3lte.env` boot menu that never auto-boots Duranium
  or writes to userdata, with no Fastboot flash, OEM run, or USB mass storage
  transport enabled for the first inspection build;
- an Actions gate proving that this LTE environment is actually embedded
  inside the experimental LTE uniLoader chainloader.

**The LTE uniLoader board still has no watchdog or Volume Down fallback
hooks**. The USB diagnostic's `peek` commands can compare GPIO key state
and watchdog registers via `tools/t575-lte-keys-watchdog-readonly.py`.
These reads are necessary observations, NOT proof that a watchdog-driven
recovery will work. The only presently established recovery is manual
Samsung Download Mode + Heimdall restoration of a saved BOOT image.

The original `T575-BOOT-review` images precede these LTE-specific
changes and must be treated as superseded. No user-facing instructions
for flashing should be issued until a fresh successful build, valid
offline Android BOOT packaging, and an explicit recovery/rollback plan
are in place. The real Phosh OS still has not been written to userdata.

## Phosh + lightweight desktop mode

Start with native upstream Phosh/Phoc as the sole running compositor. Then
introduce a second, **exclusive** labwc session (windowed, resizeable apps,
panel, launcher, keyboard/mouse, S Pen) selected by a Touch / Desktop switch.
Never keep Phosh and labwc concurrently resident just to change modes.

For the 4 GB RAM constraint, measure actual MemAvailable, zram/swap and
process RSS/PSS on the tablet after first boot; avoid promising specific
RAM savings versus Plasma before measurements. Optimize unneeded services
only after driver, lockscreen and power-management stability are known.

## Themes

Avoid the plain gray default. Phase 1: warm cream + teal/indigo with
high-contrast controls, polished light/dark GTK/libadwaita appearances.
Phase 2: tasteful 1990s Jazz geometric textures and coordinated icon/panel
colors across Phosh and labwc. Keep themes lightweight (no animated
backgrounds or second desktop process).

## Acceptance

- [x] Native LTE Duranium full Phosh build passes CI and SHA-256 integrity checks (physical boot untested).
- [ ] LTE chainloader compiles and offline BOOT safety/admission passes.
- [ ] Installer supports exact LTE model, consented userdata erase and
      tested recovery path, without requiring NFS.
- [ ] Phosh boot + finger touch input (Himax HX83102E) + pen (Wacom) + brightness/power run on physical tablet.
- [ ] RAM measured under representative idle/desktop workload.
- [ ] Exclusive keyboard/mouse desktop mode verified.
- [ ] Coordinated non-gray themes installed and switchable.

Status is **build/review, not ready to flash**.
