# SM-T575 Mali-G72: Exynos9810 G3D power-domain dependency (hardware evidence)

**Status: source investigation only; no kernel fix accepted; no flash approved.**

## Physical SM-T575 results (2026-11-17)

Under the experimental NFS Linux 7.3.0 diagnostic kernel:

- The Exynos DPU/KMS driver initializes and exposes `/dev/dri/card0` and `card0-DSI-1` at 1200×1920.
- Panfrost and gpu-sched modules load, but no `renderD128` render node appears.
- `/sys/bus/platform/drivers/panfrost` contains only `uevent`, `bind`, `unbind`, `module`: no bound device.
- `/sys/bus/platform/devices` has `17500000.gpu`.
- `/sys/kernel/debug/devices_deferred`: `17500000.gpu platform: supplier 14064040.power-domain not ready`.
- Live DT supplier `/soc@0/power-domain@14064040` has a **single** compatible string:
  `samsung,exynos9810-g3d-pd`; sysfs modalias:
  `of:Npower-domainT(null)Csamsung,exynos9810-g3d-pd`.

The successful read-only NFS mount and Wacom/Himax input driver initialization are independent of this GPU issue.

## Why generic Exynos genpd options alone are not a fix

The upstream `drivers/pmdomain/samsung/exynos-pm-domains.c`
match table currently recognizes `samsung,exynos4210-pd`
and `samsung,exynos5433-pd`, **not**
`samsung,exynos9810-g3d-pd`.

References:
- https://codebrowser.dev/linux/linux/drivers/pmdomain/samsung/exynos-pm-domains.c.html
- https://www.cateee.net/lkddb/web-lkddb/EXYNOS_PM_DOMAINS.html

Turning on `CONFIG_PM_GENERIC_DOMAINS=y` and
`CONFIG_EXYNOS_PM_DOMAINS=y` without implementing a compatible driver
is thus *not established* to resolve this supplier. Do **not** simply
append this custom compatible string to the generic driver's OF match
table: register layout, secure-monitor access, voltage, timing, reset,
and clock ordering might differ, and undocumented writes could damage
stability or interrupt recovery.

The early draft config-only change in this PR was reversed immediately
after the live DT compatible was inspected. No device changes were made.

## Next engineering gates

1. Locate and inspect the exact Linux kernel patch sources used in the
   NFS BOOT build, including SoC DT and the `17500000.gpu` node.
2. Identify the intended Exynos9810-specific G3D power-domain provider;
   check `14064040` base, register size, reset/clock dependencies,
   regulator and secure-monitor requirements against proven source.
3. If source support already exists behind another Kconfig option,
   enable it **only** in an opt-in build and confirm the fully generated
   kernel configuration and compiled-driver OF match table.
4. Otherwise implement an Exynos9810-specific reviewed provider,
   with hardware-safe access and explicit power-sequencing tests,
   **without** forcing binds or bypassing `-EPROBE_DEFER`.
5. Compile and audit the new kernel offline. Preserve current NFS
   BOOT image and the known-good Android BOOT backup. Any hardware
   trial requires a separate explicit approval and recovery gate.
6. Once a safe provider is running, inspect deferred probes and
   `/dev/dri/renderD128` before attempting Weston or Plasma Mobile.

No changes to device runtime, BOOT, DTBO, Android internal storage,
NFS server or network are requested by this investigation.

## 2026-11-17 — exact in-repository driver and Wi-Fi precedent found

The owner's **local `git grep`** found all of the following in the tracked source:

- `patches/linux/0081-pmdomain-samsung-Add-Exynos9810-support.patch`
  extends `drivers/pmdomain/samsung/exynos-pm-domains.c` with an OF
  match for the exact `samsung,exynos9810-g3d-pd` compatible, plus
  Exynos9810-specific D-TZPC SMC and embedded-G3D clock ordering.
- `0086` and `0087` supply later power-domain error recovery and
  adjusted GPU-clock ordering based on the SM-T570 GPL kernel.
- `0083` defines `power-domain@14064040` and GPU at `17500000`;
  `0084` enables the Mali GPU on SM-T570 assuming S-Boot left G3D on.
- **`0115-arm64-dts-exynos-gtactive3wifi-Drop-the-GPU-power-do.patch`**
  documents the *identical* deferred-probe error when
  `CONFIG_PM=n`, and drops the GPU's `power-domains` link on the
  Wi-Fi SM-T570 because S-Boot left G3D powered. This workaround was
  developed on a different board variant; it is NOT yet shown safe on
  this owner's LTE bootloader.
- `0153-arm64-dts-exynos9810-gtactive3-split-into-common-and.patch`
  creates the LTE DTB and moves shared GPU and power-domain definitions
  into `exynos9810-gtactive3-common.dtsi`, where the GPU retains an
  enabled `pd_g3d` supplier. The physical LTE DT shows that link is
  present and the provider deferred.

**Correction to the earlier investigation**: it was wrong to say a
matching driver does not exist in the repo. It DOES exist in patch
0081, even though the unmodified upstream Linux driver does not.
The likely reason it is unavailable to the NFS *diagnostic kernel* is
that this kernel is built from an `allnoconfig` baseline and the
bring-up fragment does not explicitly enable `CONFIG_PM` or
`CONFIG_EXYNOS_PM_DOMAINS`. This is a **hypothesis** until the built
`.config` is inspected.

Two candidate design paths (neither is approved for hardware changes):

1. **Wi-Fi-style staged bypass (preferred for evaluation only)**:
   add an LTE-only `&gpu { /delete-property/ power-domains; };`
   override in the final LTE DTS, *but only if a read-only G3D status
   measurement confirms the LTE bootloader left the domain enabled*,
   and S-Boot's clock and regulator state is documented. This avoids
   triggering untested power on/off cycles but also omits runtime
   power-domain management, with potential idle/power drawbacks.
2. Build in `CONFIG_PM=y`, `CONFIG_PM_GENERIC_DOMAINS=y` and
   `CONFIG_EXYNOS_PM_DOMAINS=y` so patched Exynos9810-specific driver
   can match the DT provider. **This permits power-domain transitions**
   and requires a separate safety audit of `samsung,bringup-keep-on`,
   clocks, regulator, and D-TZPC SMC behavior before any physical test.

Suggested read-only tablet probe:
`peek 0x14064044` (PMU `EMBEDDED_G3D_STATUS`; the SM-T570
reference measured `0x0010000f` when enabled). This is read-only MMIO
via the existing diagnostic console; a single status observation does
not prove complete power and voltage correctness.

Do not modify the currently running device, unload/rebind the GPU,
execute `poke`, launch a compositor, or flash a speculative image.
A safe next milestone is to record that single G3D status value and
reconcile the exact built kernel configuration and DT overlays,
then prepare an **offline-only** LTE-specific patch for review.

## 2026-11-17 — LTE status confirmed and opt-in offline DT workaround staged

Owner ran read-only diagnostic command `peek 0x14064044` on the SM-T575's
NFS-enabled diagnostic Linux and obtained:

```
G3D POWER-DOMAIN STATUS: 0x0010000f
```

This matches the SM-T570 Wi-Fi bootloader's documented powered-on G3D
value. It is useful supporting evidence for the known Wi-Fi stage-one
workaround, but **not** proof of correct clocks, voltages, safe runtime
power management, Panfrost binding, render node existence, or GUI success.

The review branch now stages this *experiment only*:
- `patches/experimental/t575-lte-gpu-bootloader-on-no-genpd.patch`
  adds a trailing `&gpu { /delete-property/ power-domains; };` override
  to the **LTE-only** `exynos9810-gtactive3.dts`. The shared DTS,
  Wi-Fi variant and vendor power-domain code remain unmodified.
- `bootchain/build.sh` has a new, explicitly opted-in
  `BRINGUP_EXTRA_DTS_PATCH` hook **after** applying the existing
  kernel patch stack, restricted to the single LTE DTS path and zero
  patch fuzz. The default kernel build without this variable is unchanged.
- `.github/workflows/t575-netroot-experimental-build.yml` supplies
  that variable to the experimental unsigned build and requires a compiled
  LTE DTB with enabled GPU and **no `power-domains` supplier property**.

A synthetic source-derived patch dry-run with `--fuzz=0` succeeded,
but the **full patched Linux source build and compiled DTB audit have
not yet been run**. This branch produces no flashable Android BOOT image.
It must not be merged into a release kernel on current evidence.

Further requirements: successful offline GitHub Actions build and
`fdtget` checks; inspect vendor GPU clock/voltage assumptions and
whether any new G3D errors appear at first probe; preserve verified
non-wiping Android BOOT restoration. An actual BOOT-only hardware
experiment is **not authorized** by this document or PR.
