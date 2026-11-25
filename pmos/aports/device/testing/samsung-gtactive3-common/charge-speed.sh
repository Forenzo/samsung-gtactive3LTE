#!/bin/sh
# Charge speed (Android's "Fast charging" switch, docs/BATTERY.md "Fast
# charging"): the kernel's charge_types control on the charger, "Standard"
# (input and charge current capped at 1.5 A) or "Fast" (what the source and
# the battery allow, still under the temperature steps). The choice lives
# in $STATE and is put back each time the charger appears (udev, 61-
# gtactive3wifi-battery-care.rules), so it survives reboots and updates.
#
#   charge-speed get              fast | standard | unsupported
#   charge-speed set fast|standard   (root; pkexec for the active user,
#                                     polkit action ...charge-speed)
#   charge-speed apply            (udev: the saved choice, if any)
#
# The charger is found by its control, not by name: the first power supply
# that is not a battery and offers Fast in charge_types.
set -eu

STATE=/var/lib/gtactive3wifi/charge-type

charger() {
	for d in /sys/class/power_supply/*; do
		[ -r "$d/charge_types" ] || continue
		[ "$(cat "$d/type" 2>/dev/null)" = Battery ] && continue
		grep -q Fast "$d/charge_types" 2>/dev/null || continue
		echo "$d"
		return 0
	done
	return 1
}

# "[Standard] Fast" -> standard
current() {
	sed -n 's/.*\[\([A-Za-z_]*\)\].*/\1/p' "$1/charge_types" | tr '[:upper:]' '[:lower:]'
}

write() {
	case $2 in
	fast) echo Fast > "$1/charge_types" ;;
	standard) echo Standard > "$1/charge_types" ;;
	*) return 1 ;;
	esac
}

case ${1:-} in
get)
	if c=$(charger); then current "$c"; else echo unsupported; fi
	;;
set)
	case ${2:-} in
	fast|standard) ;;
	*) echo "usage: charge-speed set fast|standard" >&2; exit 2 ;;
	esac
	c=$(charger) || { echo "charge-speed: no charger with a Fast mode" >&2; exit 1; }
	write "$c" "$2"
	mkdir -p "${STATE%/*}"
	echo "$2" > "$STATE.new"
	mv "$STATE.new" "$STATE"
	;;
apply)
	[ -r "$STATE" ] || exit 0
	c=$(charger) || exit 0
	write "$c" "$(cat "$STATE")" || true
	;;
*)
	echo "usage: charge-speed get | set fast|standard | apply" >&2
	exit 2
	;;
esac
