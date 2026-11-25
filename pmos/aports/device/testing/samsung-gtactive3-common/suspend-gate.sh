#!/bin/sh
# Allow suspend for this boot only if the kernel can suspend to idle, the
# power key is an armed wake-up source and the wake-up path has been proven
# on this tablet (marker written after the on-device suspend test).
# Otherwise suspend stays off (sleep.conf.d/50-gtactive3wifi.conf): a sleep the
# user cannot end would strand the tablet until a forced reset.
set -eu

marker=/var/lib/gtactive3wifi/suspend-wake-proven
key=/sys/devices/platform/gpio-keys/power/wakeup
drop=/run/systemd/sleep.conf.d/60-gtactive3wifi-gate.conf

reason=

# LTE wake validation must match the booted system image
# and the selected experimental idle mode.
. /usr/lib/os-release

if [ "${IMAGE_ID:-}" = samsung-gtactive3-lte ]; then
    hash=$(tr ' ' '\n' < /proc/cmdline |
        sed -n 's/^usrhash=//p')

    if ! printf '%s\n' "$hash" |
        grep -Eq '^[0-9a-f]{64}$'; then
        reason="cannot identify the booted LTE image"
    fi

    mode=normal

    param=/sys/module/cpuidle_psci/parameters/s2idle_wfi

    if [ -r "$param" ]; then
        case "$(cat "$param")" in
            Y|1) mode=wfi ;;
            N|0) mode=normal ;;
            *) reason="unknown suspend fallback state" ;;
        esac
    fi

    marker="/var/lib/gtactive3wifi/suspend-wake-proven-lte-${hash}-${mode}"

    if ! tr ' ' '\n' < /proc/cmdline |
        grep -qx 'exynos9810_c2=0'; then
        reason="LTE C2 safety setting is not confirmed"
    fi
fi

if [ -n "$reason" ]; then
    :
elif ! grep -qw freeze /sys/power/state 2>/dev/null; then
	reason="the kernel cannot suspend to idle"
elif [ "$(cat "$key" 2>/dev/null)" != enabled ]; then
	reason="the power key is not a wake-up source ($key)"
elif [ ! -e "$marker" ]; then
	reason="the wake-up path has not been proven on this tablet ($marker)"
fi

if [ -n "$reason" ]; then
	rm -f "$drop"
	echo "suspend stays disabled: $reason"
	exit 0
fi

mkdir -p "${drop%/*}"
printf '[Sleep]\nAllowSuspend=yes\n' > "$drop"
echo "suspend allowed (wake-up path proven: $(head -n1 "$marker"))"
