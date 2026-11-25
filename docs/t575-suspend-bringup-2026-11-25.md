# SM-T575 LTE suspend bring-up — 2026-11-25

Live Duranium/Nura Phosh, kernel 7.3.0, systemd 262.2. Source r29/r31 charger backports are not installed on the running tablet.

## Initial state

Suspend intentionally disabled by vendor sleep.conf (AllowSuspend=no, SuspendState=freeze) and Phosh enable-suspend=false. Existing blank-suspend user service requests suspend two seconds after screen blank; logind refuses. Gate requires freeze support, enabled gpio-keys wakeup and /var/lib/gtactive3wifi/suspend-wake-proven. Marker remains absent. Wi-Fi and USB sleep hooks present. SSH PAM sleep inhibitor disappears upon disconnect. RTC0 s3c-rtc calendar is in 2000 but advances and accepts relative alarms.

## Tests

Awake relative +20 s alarm: IRQ 83 count 0 -> 1, cleared successfully. First scheduled suspend attempt with systemctl --check-inhibitors=yes suspend failed in userspace; kernel counters stayed 0/0, temporary override and alarm cleaned up. Second test used a transient root timer, no connected SSH, paused blank-suspend user service, temporary /run/systemd/sleep.conf.d/99-t575-suspend-test.conf (AllowSuspend=yes, SuspendState=freeze), RTC +120 s, logind CanSuspend yes and SuspendWithFlags t 1 accepted. Existing sleep hooks used. No permanent gate marker.

- Kernel suspend entry 10:51:23 CET; resume 10:53:16; exit 10:53:17.
- Successful suspend counter 0 -> 1; failed 0 -> 0.
- RTC IRQ 83 count 1 -> 2; user observed tablet turn back on without manual wake.
- Original headphone controller PID unchanged and active; TAS2562 lock N. Actual audible playback after resume still to verify.
- Wi-Fi SSH reachable again; touchscreen and USB recovery not separately tested.
- Both charge_now and charge_counter declined by 8000 uAh over about 121–122 s including awake overhead: approximately 236–238 mA, not a precise suspended-current measurement.
- Pinctrl warnings about missing retention data / external wake masks on 14220000 and 14050000. Physical button wake still needs test; no assumption these warnings are harmless.
- Temporary override removed. No persistent sleep policy enabled; blank-suspend user service remains paused pending controlled trials.

Next: repeat with physical power button well before the RTC fallback, verify early resume and unchanged alarm IRQ at resume, test actual headphones/touch/network, repeat wake trials and measure extended suspend. Keep C2 disabled and no flash. Do not create persistent wake-proven marker before validated power-button wake. Retest on updated kernel.

Private user names, endpoints, boot hashes and raw logs excluded.

## Physical power-button wake trial

Same temporary test script and +120 s RTC fallback. Kernel entered s2idle at 10:56:47 CET and exited at 10:57:21 (34 s). User pressed the power button; reported that a second press appeared necessary for the display, then normal recovery. Successful counter 1 -> 2, failed 0 -> 0, RTC alarm IRQ count unchanged at 2. Strong evidence of physical wake before RTC fallback. Audio controller PID unchanged; headphone PipeWire sink present (idle/SUSPENDED); actual playback still to verify. Speaker lock N, SSH reachable and temporary override removed. Charge fields decreased 3 mAh over 40 s; too short for accurate standby power measurement. Next: temporary screen-off-driven suspend through existing user service, then sustained standby and repeated wake validation before persistent opt-in. No permanent marker yet.

## Automatic screen-off suspend trial

2026-11-25: existing blank-suspend user service restored and temporary runtime sleep override opened with RTC +120 s fallback. The service requested suspend after two seconds of display blanking at 11:00:19 CET. Kernel entered s2idle at 11:00:25 and exited at 11:00:57 (32 s). Test cleaned up at 11:00:58. Successful counter 2 -> 3, failed 0 -> 0, RTC IRQ count unchanged at 2. Original headphone controller unchanged; headphone PipeWire sink present; speaker lock N; SSH reachable. Temporary override removed. No permanent wake-proven marker yet. Next: approximately 20-minute battery-only screen-off trial with RTC wake, before/after charge fields and elapsed time; confirm actual playback and touch after resume. Retest on updated kernel.

## Extended standby trial

2026-11-25 11:02:30–11:22:31 CET, 1201 seconds elapsed, automatic screen-off suspend with +1200 s relative RTC alarm, battery only. Headphones unplugged around display blanking. Photographed test output: capacity 65 -> 63%, charge_now 2512000 -> 2450000 uAh (62 mAh, 185.8 mA), charge_counter 2939000 -> 2878000 uAh (61 mAh, 182.8 mA). Mean of the two estimates 184.3 mA, includes entry/exit awake overhead. Battery temperature 21.8 C unchanged; user reported tablet did not get warm. Success counter 3 -> 4, fail 0 -> 0, original headphone controller unchanged, TAS2562 locked, temporary override removed, test service completed successfully. Approximate reduction 67% versus prior 564 mA screen-on idle, not matched display conditions. Upstream Wi-Fi test ~171 mA via charge_now (~219 mA via charge_counter). Actual kernel entry/exit and wake IRQ still to collect for extended trial.

Resume issue: screen did not illuminate at alarm expiry; local console later accessible. Wi-Fi hardware and radio enabled, brcmfmac and brcmfmac_wcc loaded, wlan0 present but unmanaged in NetworkManager; usb0 and Bluetooth device also unmanaged. Possible NetworkManager sleep-state or interface management issue, not yet established. Capture state/reason and sleep/resume journals before intervention. No permanent wake marker until network recovery verified. No driver reload, flash, or C2 changes.

### Extended resume: manual network recovery verified

Local console: nmcli general status reported network off while nmcli networking reported enabled; Wi-Fi hardware/radio enabled; wlan0 unmanaged with GENERAL.REASON 73. User confirmed the first explicit recovery command immediately restored connectivity:

```sh
sudo busctl call org.freedesktop.NetworkManager /org/freedesktop/NetworkManager org.freedesktop.NetworkManager Sleep b false
```

No driver reload or NetworkManager restart required. This establishes a recoverable NetworkManager sleep-state symptom, not the root cause of the missed/ineffective resume transition. Collect logind, systemd-sleep, NetworkManager and Wi-Fi recovery logs for the long trial; design a conditional post-resume safeguard respecting intentionally disabled networking and Wi-Fi. Persistent suspend enablement still pending repeated recovery validation.

### Extended resume root-cause evidence

Kernel entry 11:02:53 CET, exit 11:22:30 (1177 s). NetworkManager entered sleep at 11:02:47, and its original process stayed asleep through resume. At 11:22:30 PID 1 killed systemd-logind (original PID 743) via its 3-minute service watchdog, SIGABRT, and restarted it; the user session later exited and was recreated. Broadcom firmware and wlan0 returned at 11:22:30–31. Explicit NetworkManager Sleep(false) at 11:51:23 restored connection by 11:51:27. Lost logind resume notification is the likely explanation; reason for watchdog expiry still unproven. See https://access.redhat.com/kb/5118401 for analogous s2idle watchdog behavior involving monotonic clock advancement during suspended intervals; deep/S3 is not available here. Inspect monotonic journal timestamps and clocksource; retain hardware watchdog, avoid blanket service-watchdog changes. Consider a scoped temporary logind timeout extension only after investigation. No permanent gate marker. Post-session-recreation audio status: original service reported active but PipeWire showed t575_speaker running, headphone sink absent, TAS2562 allow_activation=N. Stop playback and audit audio state separately; sink RUNNING alone does not establish physical amp activation. Do not unlock speaker. No private network/session identifiers in documentation.
