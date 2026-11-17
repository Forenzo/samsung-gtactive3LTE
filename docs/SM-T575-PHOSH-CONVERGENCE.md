# SM-T575: Phosh and desktop-convergence design

Status: design and build-only testing; **not yet boot-tested** on LTE hardware.

## Scope and non-negotiable constraints
- Target: Samsung Galaxy Tab Active3 LTE SM-T575 (Exynos 9810, 4 GB RAM).
- Keep the working LTE **7.3.0** GPU/NFS diagnostic BOOT and previously verified Magisk-rooted Android BOOT backup. Do not flash an SM-T570 image.
- First sessions run from a **separate read-only Mac USB/NFS rootfs**. Do not touch Android `userdata`, `metadata`, `super`, EFS, DTBO or install Duranium to Android storage.
- Retain native 1200x1920 LCD, display DRM card0, Panfrost renderD128, Wacom stylus, Himax touchscreen and USB NCM paths from the demonstrated Plasma bring-up.
- Phosh is the default **touch** UI. Phoc (wlroots) replaces the nested Cage/KWin compositor chain; no Plasma components or Cage are installed in this new rootfs.
- A separate **desktop session** will use labwc plus a lightweight panel (yambar) and app launcher (fuzzel), all from the same userspace, **never active concurrently with Phosh**.
- Session switching must be clean: terminate old compositor, restore input/seat, then launch the other. Hot switching and external output require hardware verification.
- Focus first on reliability, input, power and observable idle RAM before installing applications or elaborate themes.

## Phases

### P0: Boot-only isolated rootfs (current build target)
- Alpine 3.22 AArch64, Phosh/Phoc/squeekboard + only required services.
- Include labwc/yambar/fuzzel/foot for a *future* desktop session, not automatic startup.
- Export a fully hashed userspace tarball in GitHub Actions; do not flash.
- Stage separately on the Mac SSD under `/Volumes/T575-Plasma/phosh-rootfs`; preserve the known-working Plasma rootfs untouched.
- Add a new Mac NFS **read-only** export for the new root only when a launcher is reviewed; test mount and use dynamic mountd port from `rpcinfo`.
- Build a Phosh-specific AArch64 diagnostic launcher reusing the verified non-wiping host RAM upload, network, devtmpfs, DRM, seatd, USB and input initialization. **Do not reuse the Plasma executable unmodified** because root paths, startup and user service requirements differ.

### P1: First *usable* Phosh
- Seatd/libseat + Phoc controls DRM and Panfrost directly; Phosh provides shell.
- Verify display orientation, touch event mapping, S Pen, lockscreen, screen blanking, buttons, text entry and watchdog behavior.
- Capture device log snapshots on the Mac so resets don't erase evidence.
- Measure `MemAvailable`, `MemTotal`, major process RSS/PSS, swap and rootfs size before claiming lower memory use.

### P2: Desktop mode ("DeX-like", not Samsung DeX)
- Lightweight labwc window-stacking Wayland session with yambar panel, fuzzel launcher and foot terminal.
- Window decorations, resize, maximize, multiwindow, keyboard shortcuts, external keyboard/mouse, landscape mode, S Pen.
- A user-facing **Touch / Desktop** switch initially logs out and re-launches the selected session; no simultaneous compositor duplication.
- Verify USB-C/HDMI display output from Linux *independently*. Samsung DeX compatibility in Android does not prove Linux DP Alt Mode support without kernel/DRM work.
- Consider external-display docking after a locally usable desktop is stable.

### P3: Theming
- No hard gray default. Start with a light warm-cream/teal/indigo palette, high-contrast readable controls and colorful wallpaper.
- Add dark plum/teal and retro 1990s geometric "Jazz" theme variants later.
- Apply Phosh/libadwaita-compatible color-scheme settings, GTK CSS, icons, wallpaper and matching labwc panel/theme. Avoid global fragile CSS monkey-patching of security dialogs and system components.
- Themes are optional, no background compositor and no animated wallpaper, protecting 4 GB RAM.

## Acceptance checks
1. Phosh shell drawn on SM-T575 with functional input, no nested KDE processes.
2. No Android partition writes; no unverified stock restore assumptions.
3. Responsive idle screen and recorded idle memory measurements.
4. Proper windowed desktop session can start *instead of* Phosh, with terminal and app launcher.
5. Theme switch changes actual shell/panel and application colors, not only wallpaper.

This file is a plan, not a claim that Phosh or desktop mode has booted successfully.
