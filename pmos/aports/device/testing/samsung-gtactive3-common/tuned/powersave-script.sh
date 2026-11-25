#!/bin/sh
# LTE selective variant of upstream saver cpuset (e552df52).
# Source-stage only; opt-in. Never change parent slices or audio services.
set -eu
FLAG=/etc/t575-power/enable-saver-cpuset
TEST=/run/t575-power/enable-saver-cpuset
STATE=/run/t575-saver-cpuset-units
UNITS="accounts-daemon.service avahi-daemon.service cups.service systemd-timesyncd.service systemd-oomd.service upower.service"

note() { printf 't575-saver-cpuset: %s\n' "$*" >&2; }
prop() { systemctl show "$1" -p "$2" --value; }

mkdir -p -m 0700 "$STATE"
exec 9>"$STATE/lock"
flock -x 9

restore() {
    rc=0
    for unit in $UNITS; do
        [ -f "$STATE/$unit" ] || continue
        current=$(prop "$unit" AllowedCPUs) || { rc=1; continue; }
        case "$current" in
            0-3) systemctl set-property --runtime "$unit" AllowedCPUs= || { rc=1; continue; } ;;
            '') ;;
            *) note "$unit: external policy retained" ;;
        esac
        rm -f "$STATE/$unit"
    done
    return "$rc"
}

case "${1:-}" in
start)
    if [ ! -f "$FLAG" ] && [ ! -f "$TEST" ]; then
        restore
        exit $?
    fi
    if [ -n "$(prop system.slice AllowedCPUs)" ]; then
        note "parent restriction detected; not applying policy"
        restore
        exit 1
    fi
    # Preserve the running audio controller without restarting it.
    hp=$(prop t575-headphones.service MainPID)
    case "$hp" in
        ''|0|*[!0-9]*) note "audio controller not running; skipping"; restore; exit $? ;;
    esac
    if ! grep -Eq '^Cpus_allowed_list:[[:space:]]+0-7$' "/proc/$hp/status"; then
        note "audio CPU access is not 0-7; skipping"
        restore
        exit 1
    fi
    for unit in $UNITS; do
        [ "$(prop "$unit" ActiveState)" = active ] || continue
        [ "$(prop "$unit" ControlGroup)" = "/system.slice/$unit" ] || continue
        current=$(prop "$unit" AllowedCPUs)
        if [ -n "$current" ] && [ ! -f "$STATE/$unit" ]; then
            note "$unit: existing CPU policy retained"
            continue
        fi
        if [ -f "$STATE/$unit" ] && [ "$current" != 0-3 ] && [ -n "$current" ]; then
            note "$unit: external policy retained"
            rm -f "$STATE/$unit"
            continue
        fi
        : > "$STATE/$unit"
        if ! systemctl set-property --runtime "$unit" AllowedCPUs=0-3 ||
           [ "$(cat "/sys/fs/cgroup/system.slice/$unit/cpuset.cpus.effective" 2>/dev/null)" != 0-3 ]; then
            note "$unit: verification failed; restoring owned policies"
            restore || note "restore failed; manual inspection required"
            exit 1
        fi
        note "$unit: CPUs 0-3"
    done
    if [ "$(prop t575-headphones.service MainPID)" != "$hp" ] ||
       ! grep -Eq '^Cpus_allowed_list:[[:space:]]+0-7$' "/proc/$hp/status"; then
        note "audio verification failed; restoring owned policies"
        restore || note "restore failed; manual inspection required"
        exit 1
    fi
    ;;
stop)
    restore
    ;;
*)
    exit 0
    ;;
esac
