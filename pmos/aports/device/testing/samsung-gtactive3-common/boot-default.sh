#!/bin/sh
# Keep systemd-boot's default on the owner's UI (phosh, gnome, ...), so an
# image of another UI on the ESP (a mistaken update, a test) never takes
# over the next boot. systemd-boot otherwise starts the highest version,
# whatever its UI, and `bootctl set-default` does not survive a reboot here
# (U-Boot keeps no EFI variables).
#
# The UI is /var/lib/gtactive3wifi/ui: written on the first boot from the
# booted image, changed only by gtactive3wifi-switch-ui (the user asking for
# another UI). The default is a pattern, so the newest version of that UI
# wins and boot counting still falls back between its A/B entries.
#
#   boot-default            (boot service) make loader.conf match the UI
#   boot-default set UI     record UI as the owner's choice, then the same
set -eu

pref=/var/lib/gtactive3wifi/ui
conf=/boot/loader/loader.conf

if [ "${1:-}" = set ]; then
	case ${2:-} in
	"" | -* | *[!a-z0-9-]*) echo "usage: boot-default set UI" >&2; exit 1 ;;
	esac
	mkdir -p "${pref%/*}"
	echo "$2" > "$pref.new" && mv -f "$pref.new" "$pref"
fi

if [ ! -s "$pref" ]; then
	# shellcheck source=/dev/null
	. /usr/lib/os-release
	mkdir -p "${pref%/*}"
	echo "$VARIANT_ID" > "$pref"
fi
ui=$(cat "$pref")
case $ui in
"" | -* | *[!a-z0-9-]*) echo "bad UI in $pref: $ui" >&2; exit 1 ;;
esac

# every name these images had (samsung-gtactive3wifi_..., then
# samsung-gtactive3-wifi_...): systemd-boot sorts entries by their image id
# and the new name sorts first, so the newest new-named image wins.
# An entry id is the UKI's file name, lower case, without the boot counter;
# systemd-boot 262 appends @<profile> only to profiles after the first, so the
# pattern ends in .efi (the main profile). Not an exact id: `default` ignores
# boot counting, while a pattern takes the first entry with tries left (used-up
# entries sort last), which keeps the A/B fallback between this UI's images.
. /usr/lib/os-release

case "${IMAGE_ID:-}" in
    samsung-gtactive3-lte)
        want="default samsung-gtactive3-lte_${ui}_edge_*.efi"
        ;;
    samsung-gtactive3-wifi|samsung-gtactive3wifi)
        want="default samsung-gtactive3*_${ui}_edge_*.efi"
        ;;
    *)
        echo "Unknown image identity; boot default unchanged"
        exit 0
        ;;
esac
[ -f "$conf" ] || { echo "no $conf"; exit 0; }
if grep -qx "$want" "$conf" && [ "$(grep -c '^default' "$conf")" = 1 ]; then
	exit 0
fi
{ grep -v '^default' "$conf" || :; echo "$want"; } > "$conf.new"
sync "$conf.new" 2>/dev/null || sync
mv -f "$conf.new" "$conf"
sync
echo "boot default: newest $ui image"
