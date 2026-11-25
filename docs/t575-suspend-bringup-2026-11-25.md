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
