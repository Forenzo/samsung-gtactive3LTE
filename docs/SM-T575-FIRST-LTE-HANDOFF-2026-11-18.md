# SM-T575 LTE U-Boot first-handoff safety and recovery notes (2026-11-18)

This is a test plan, **not permission to flash**. The first usable native
Duranium Phosh OS remains uninstalled. Only test the experimentally built
LTE chainloader after a fresh green CI run, artifact manifest verification,
repackaging from the owner's verified stock Android BOOT and an explicit
owner decision to accept a BOOT-only experimental test.

## Known-good observations

- Physical tablet: **SM-T575**, unlocked Samsung S-Boot revision
  `T575XXSFEYI1`, 4-KiB UFS logical blocks.
- `BOOT` PIT partition 12 (`/dev/sda12` under mainline Linux):
  exactly **61,865,984 bytes**. `userdata` is partition 31, not a test target.
- Original rooted Android BOOT, locally held in
  `~/Downloads/SM-T575-Recovery/boot-current.img`:
  SHA-256 `a69a724b75a51821a0baa4ccda424173a003b17de19e2b381bb7d4f30596e372`.
- Last known-working diagnostic GPU BOOT:
  `~/Downloads/SM-T575-Recovery/t575-gpu-BOOT-CANDIDATE.img`:
  SHA-256 `8225061aa97b72f41f27ffc0119d84f1fd22c0d6b009d5e123b811f1796792f7`.
- Heimdall v2.2.2 BOOT-only flashing of an experimental diagnostic Linux
  image has succeeded. A later accidental Download Mode exit returned to
  the existing diagnostic image **without** a partition write. **Actual
  stock rooted Android BOOT restoration has NOT been demonstrated.** The
  verified original Android BOOT is an archived option, not a tested recovery.
- With physical keys released, GPIO GPA0_DAT `0x14050024` read `0x3e`.
  Pressing Volume Down read `0x2e` (active-low bit 4). A long hold of
  volume keys interrupted the USB diagnostic by entering Download Mode;
  don't repeat long-hold key tests.
- Native Phosh disk image and UKI passed CI and SHA-256, and old
  `T575-BOOT-review-LTE-20261118` BOOT candidates passed AVB checks.
  **Those older BOOT candidates are superseded** by newer loader source.
  Verification does not imply first boot, correct FDT handover, or functioning
  touch and pen.

## First physical LTE U-Boot handoff: PASS (owner, 2026-11-18)

The owner installed the offline-reviewed `t575-phosh-chain-BOOT-UNTESTED.img`
from `~/Downloads/T575-BOOT-first-handoff/` through a BOOT-only Heimdall
experiment and supplied a photograph of the running tablet's display.
**This is the first confirmed physical S-Boot -> LTE uniLoader -> U-Boot
execution on SM-T575.**

The photograph shows the bespoke `*** U-Boot Boot Menu ***`, with:

1. `Warm reset (attempt Linux fallback)`
2. `Show U-Boot board and DRAM`
3. `Show EFI memory map`
4. `Show detected UFS partitions (READ ONLY)`
5. `Re-enter inspection menu`
0. `Exit`

The menu is visibly rendered, with one row highlighted and on-screen
instructions `Press UP/DOWN to move, ENTER to select, ESC to quit`.
The owner independently reported the physical navigation buttons work.

**Proved:** the installed first-handoff BOOT image reaches U-Boot on the
physical LTE tablet; a readable framebuffer menu is active; navigation
via hardware buttons works.

**NOT YET PROVED:** the warm-reset fallback returns to embedded Linux;
Linux diagnostic USB console reappears; EFIBoot/UKI or full Phosh boots;
Himax finger touch or Wacom S Pen works in Phosh; the inspection menu's
UFS probe works; automatic recovery from a hang; userdata installation.
No userdata or protected-partition writes were requested for this test.

Recommended next single-step observation: select the **read-only**
`Show U-Boot board and DRAM` entry, photograph its output, then use
`Warm reset (attempt Linux fallback)` to check that the physical tablet
returns to the embedded Linux diagnostic USB console. The return path
remains experimental; retain the verified diagnostic BOOT image and manual
Download Mode / Heimdall rollback in case the reset reenters the menu
or hangs. Avoid prolonged volume-key holds.

## Read-only PMU/watchdog snapshot (owner, 2026-11-18)

Physical SM-T575, running the known-working diagnostic Linux, with
physical keys released. All readings are from USB IPv6 diagnostic
`peek` commands; no register writes or reset attempt were performed.

| Address | Register | Value | Narrow observation |
|---|---|---|---|
| `0x14050024` | GPA0_DAT | `0x0000003e` | buttons released |
| `0x14060404` | PMU RST_STAT | `0x00010000` | cluster-0 WDT reset bit 24 clear |
| `0x14060408` | PMU WDT_DISABLE | `0xfeffffff` | bit 24 clear (reset not disabled by this mask) |
| `0x1406040c` | PMU WDT_MASK_RESET | `0xfeffffff` | bit 24 clear (reset not masked by this register) |
| `0x10050000` | CL0 WDT WTCON | `0x00005c39` | enable (bit 5) and reset enable (bit 0) both set |
| `0x10050008` | CL0 WDT WTCNT | `0x0000f827` | readable single counter value; no movement observed |

This supports the LTE uniLoader source's RST_STAT bit-24 test not
misidentifying an initial watchdog reset **at this sampled moment**. It
does not prove watchdog reset actually fires, the reset reason survives
S-Boot, the warm-reset handoff record persists, or an early U-Boot hang
will recover automatically. The observed diagnostic-kernel watchdog is
running with reset output permitted; do not reprogram its registers
during exploratory tests.

## Latest inspected LTE chainloader archive (offline-only)

GitHub Actions [run 44283262697](https://github.com/Forenzo/samsung-gtactive3LTE/actions/runs/44283262697)
successfully built the updated LTE passive-framebuffer / read-only GPIO
selection / inspection menu payload at commit
`af2354e40d6e62cb3011f126d0b9b2223374567b`.

Artifact ZIP locally inspected in an isolated container:
- GitHub artifact: `t575-lte-phosh-bootchain-UNTESTED` (id 14417963078).
- Downloaded ZIP SHA-256:
  `343a813907a9de1f2e84a49165aa6f7931dbc5d39d809b449b5aeb0f0e5f44b0`.
- ZIP CRC **PASS**; nested tar archive members **PASS**.
- All five payload SHA-256 values match the nested `MANIFEST`.
- `uniLoader-chain-gtactive3` SHA-256:
  `9bc42c2f09606039d3ffd5ae468954cde6d5655877a09c72d78dba6358b0e740`.
- The actual LTE chain payload contains `samsung-gtactive3lte`,
  `SM-T575 LTE RESEARCH BOOTCHAIN`, and `bootmenu 30`.
- This validates provenance and inclusion, **NOT** actual board/video boot,
  fallback behavior, or a flashable Android BOOT image. The new ZIP must be
  packaged from the owner's verified stock Samsung BOOT and checked offline.

## Latest LTE first-stage source adjustments

1. uniLoader `board-gtactive3lte.c` uses a passive `simplefb` on the
   physically observed 1200x1920 ARGB8888 handover at `0xca000000`.
   **No DECON_F MMIO writes** copied from the Wi-Fi board.
2. The optional LTE uniLoader `chain_select` samples GPIO and reset status
   **read-only**. Volume Down or cluster 0 watchdog reset status requests
   embedded diagnostic Linux instead of U-Boot. This branch still has **no
   watchdog programming or automatic recovery from a hung U-Boot**.
3. Experimental U-Boot defaults to `exynos9810-gtactive3` (LTE) with
   a *read-only* diagnostic boot menu, no Duranium autoboot, no Fastboot
   flashing, and no USB mass-storage host exposing protected partitions.
   The first menu entry attempts a **warm reset**; the 30-second menu
   timeout selects that entry. This *might* return to diagnostic Linux by
   the previous-run handoff record, but RAM retention and reset behavior are
   unproven on this LTE tablet.
4. Finger and S Pen tests are for full Linux/Phosh, not the U-Boot menu.

## Before an explicitly authorized BOOT-only experiment

- Verify fresh green CI run and SHA-256 manifest, then repackage using the
  known stock Android BOOT header and embedded Samsung DTB. Keep old files.
- Verify the new BOOT candidate's exact 61,865,984-byte length, ARM64
  header, signed AVB footer, embedded LTE identification and checksum.
- Confirm full stock Android **and working diagnostic** BOOT backups remain
  on the Mac and hash-match above. Keep their copies off the tablet.
- Prepare and practice the **manual** path to Samsung Download Mode without
  accidentally pressing buttons during U-Boot menu navigation. Have Heimdall
  `detect` working and a stable USB connection.
- Never write to `DTBO`, `VBMETA`, `EFS`, `SEC_EFS`, `super`, `userdata`
  or any other partition during this experiment. This is **BOOT only**.
- Collect a video of the boot display or a clear text observation; don't
  assume a dark screen proves U-Boot did or did not execute.

## If first boot hangs / panel stays dark

Manual recovery takes precedence over speculative watchdog commands:
enter Samsung Download Mode with the previously used physical recovery
method, reconnect the Mac and prefer the **previously boot-tested GPU
Linux diagnostic BOOT** for BOOT-only restoration. Heimdall has previously
flashed a diagnostic image successfully; this rollback itself still needs
physical verification. The stock Android BOOT image is hash-verified but
has not been restored in a completed test. Start a fresh Heimdall
session; prior `print-pit --no-reboot` caused session-end errors.
A BOOT-only restore does **not** undo future userdata erasure; don't erase
userdata during this handoff test. If Download Mode is unreachable,
stop: do not use alternative firmware partition commands.

## Exit criteria

A first controlled handoff provides evidence only after (a) a visible
U-Boot menu or readback RAM log showing that U-Boot actually ran, and
(b) successful return to diagnostic Linux via the warm-reset fallback or
manual BOOT-only restore. A successful CI build or AVB hash verification
is not a substitute for either physical result.
