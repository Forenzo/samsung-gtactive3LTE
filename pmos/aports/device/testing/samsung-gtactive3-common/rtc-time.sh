#!/bin/sh
# Set the system clock from the S2MPS18 PMIC's RTC (kernel r30+: rtc-s5m over
# ACPM), which keeps counting while the tablet is off. Without it the system
# starts at the image's build time until NTP, which needs a network.
# Only forward, and never to a time before the image's build (systemd's clock
# epoch): an RTC that lost power must not take the clock back. The kernel keeps
# the RTC set from NTP (RTC_SYSTOHC) and timedatectl writes it on set-time.
set -eu

rtc=${1:?usage: rtc-time rtcN}
n=${rtc#rtc}
case "$n" in
    ""|*[!0-9]*) exit 1 ;;
esac
[ "$rtc" = "rtc$n" ] || exit 1

# Only the S2MPS18 calendar RTC, never the SoC alarm RTC.
modalias=$(cat "/sys/class/rtc/$rtc/device/modalias" 2>/dev/null || :)
[ "$modalias" = "platform:s2mps18-rtc" ] || exit 0

t=$(cat "/sys/class/rtc/$rtc/since_epoch")
now=$(date +%s)
epoch=$(stat -c %Y /usr/lib/clock-epoch 2>/dev/null || echo 0)

if [ "$t" -lt "$epoch" ]; then
	echo "$rtc reads $(date -u -d "@$t" '+%F %T' 2>/dev/null || echo "$t") UTC, before this image was built: not used (lost power?)"
	exit 0
fi
if [ "$t" -le "$now" ]; then
	echo "$rtc is not ahead of the system clock: left as it is"
	exit 0
fi
date -u -s "@$t" >/dev/null
echo "clock set from $rtc: $(date -u '+%F %T') UTC"
