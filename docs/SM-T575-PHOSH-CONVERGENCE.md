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

**Proven on physical SM-T575 (2026-11-18):** the S-Boot -> LTE
uniLoader -> U-Boot inspection-menu handoff, readable framebuffer, volume-key
navigation, inactivity-triggered warm reset, and return to a responding
diagnostic Linux 7.3.0 USB console. See
[the first LTE hardware handoff log](SM-T575-FIRST-LTE-HANDOFF-2026-11-18.md).

**Not yet proven:** the native LTE U-Boot -> EFI/systemd-boot handoff,
signed-image acceptance, Phosh encrypted first boot, touch or pen events,
watchdog recovery from an actual hang, and recovery of Android userdata.
The timed warm-reset fallback is not the same as tested watchdog recovery.

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
4. Ensure a real recovery route: previous Heimdall BOOT-only flashing of
   diagnostic Linux worked, but restoration of rooted Android BOOT has
   NOT yet been independently tested. Duranium data cannot be undone
   simply by reflashing BOOT.
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

**The LTE uniLoader board has a read-only Volume Down/reset-status
selection hook but no watchdog-arm or automatic hung-boot recovery hook**. In the 2026-11-18 physical key test, GPIO GPA0_DAT
(0x14050024) changed from 0x0000003e (all keys released) to 0x0000002e
(Volume Down pressed): bit 4 (0x10) cleared, consistent with active-low
Volume Down on this T575. During the subsequent Volume Up measurement, the
tablet entered Samsung Download Mode and the USB diagnostic disconnected
with macOS Errno 6. This establishes only the GPIO observation, NOT a safe
bootloader fallback or an independent Volume Up mapping. **Do not repeat
prolonged volume-button holding to sample GPIOs.** The updated
`tools/t575-lte-keys-watchdog-readonly.py` is baseline-only (no key hold),
and can inspect current registers with `peek` commands after Linux boots.
These reads are observations, NOT proof that a watchdog-driven
recovery will work. The only presently established recovery is manual
Samsung Download Mode + Heimdall restoration of a saved BOOT image.

The original `T575-BOOT-review` images precede these LTE-specific
changes and must be treated as superseded. No user-facing instructions
for flashing should be issued until a fresh successful build, valid
offline Android BOOT packaging, and an explicit recovery/rollback plan
are in place. The real Phosh OS still has not been written to userdata.

## Native disk image geometry and Mac installation admission (2026-11-18)

The owner ran `t575-phosh-image-offline-audit.py` against
`samsung-gtactive3-lte_phosh_edge_26111790.raw.zst` and reported:

- Primary GPT header CRC **PASS**, partition-array CRC **PASS**, and
  **4096-byte** internal sectors.
- The compressed source's projected raw disk size is **6,862,950,400 B**;
  the measured `userdata` capacity is **55,461,281,792 B**.
- ESP #1 starts at **1,048,576 B** and is **1,073,741,824 B** (1 GiB).
- Verity partition #2 is **419,430,400 B** (400 MiB).
- The main usr partition #3 is **5,368,709,120 B** (5 GiB).
- With **6,861,881,344 B** reserved for first-boot partitions, remaining
  storage headroom is **41,736,450,048 B**.
- **Still unverified** by that particular audit: local backup GPT integrity,
  EFI contents, vendor firmware import, userdata flash/readback, full
  EFI chain and first Phosh boot. CI previously tested compressed frames,
  the UKI and trust configuration.

A new, strictly read-only **macOS** installation admission checker is at
`tools/t575-native-phosh-macos-preflight.py`, with
`.github/workflows/t575-native-phosh-macos-admission.yml` validating
its CLI/source. It verifies the local full-image manifest and primary GPT,
the hash-verified stock and diagnostic BOOT backups, the updated LTE chain
candidate, and exact **live** SM-T575 model and `/dev/sda12` BOOT /
`/dev/sda31` userdata sysfs geometry via the existing USB console. It
issues only `cat` commands and has **no flash or erase mode**. Pass does
not authorize wiping or prove that recovery from failed first boot works.

The LTE U-Boot source now additionally includes **an explicitly selected**
`TRY native Phosh EFI` menu item. The first (default) menu entry still
performs the physically tested timed warm return to diagnostic Linux.
The new option mounts no filesystem and writes no UFS contents: it
checks the LTE board, maps UFS partition 31 in RAM, and tries to load
`EFI/BOOT/BOOTAA64.EFI` from the nested GPT ESP. This updated bootchain
requires a new successful CI build and separate first-on-device UFS/EFI
handoff validation; old BOOT candidates do not have the new menu item.

**No native image has been installed**, the existing cross-platform
Wi-Fi installer intentionally blocks LTE, and no destructive Mac install
command is approved. Firmware availability, Android user-data backup/
explicit erase approval, storage/boot readback and rollback all require
separate handling before the first write.

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
- [x] LTE chainloader compiled, offline BOOT admission passed, and physical U-Boot menu + timed warm-reset return to diagnostic Linux confirmed.
- [ ] Installer supports exact LTE model, consented userdata erase and
      tested recovery path, without requiring NFS.
- [ ] Phosh boot + finger touch input (Himax HX83102E) + pen (Wacom) + brightness/power run on physical tablet.
- [ ] RAM measured under representative idle/desktop workload.
- [ ] Exclusive keyboard/mouse desktop mode verified.
- [ ] Coordinated non-gray themes installed and switchable.

Status: **LTE U-Boot handoff and timed diagnostic return physically verified;
native Phosh installation remains blocked pending offline image geometry and
reviewed LTE-specific installer/recovery gates.**
