#!/bin/sh
# LTE adaptation of upstream e552df52: restrict background services only
# after the separately managed audio controller is isolated and verified.
# Not enabled by default. This helper never starts/stops audio or drivers.
set -u
FLAG=/etc/t575-power/enable-saver-cpuset
OWN=/run/t575-saver-cpuset.owned
UNIT=t575-headphones.service

prop() {
    systemctl show "$1" -p "$2" --value
}
note() {
    printf 't575-saver-cpuset: %s\n' "$*" >&2
}
audio_ready() {
    [ "$(prop "$UNIT" ActiveState)" = active ] || return 1
    [ "$(prop "$UNIT" Slice)" = t575audio.slice ] || return 1
    [ "$(prop "$UNIT" ControlGroup)" = /t575audio.slice/t575-headphones.service ] || return 1
    pid=$(prop "$UNIT" MainPID) || return 1
    case "$pid" in ''|0|*[!0-9]*) return 1 ;; esac
    grep -Eq '^Cpus_allowed_list:[[:space:]]+0-7$' "/proc/$pid/status"
}
restore() {
    [ -f "$OWN" ] || return 0
    current=$(prop system.slice AllowedCPUs) || return 1
    case "$current" in
        0-3) systemctl set-property --runtime system.slice AllowedCPUs= || return 1 ;;
        '') ;;
        *) note "external CPU policy changed; not overwriting it" ;;
    esac
    rm -f "$OWN"
}
case "${1:-}" in
start)
    if [ ! -f "$FLAG" ] || ! audio_ready; then
        note "skipping: not opted in or audio not isolated"
        restore
        exit $?
    fi
    if [ -f "$OWN" ]; then
        if [ "$(prop system.slice AllowedCPUs)" = 0-3 ] &&
           [ "$(cat /sys/fs/cgroup/system.slice/cpuset.cpus.effective 2>/dev/null)" = 0-3 ]; then
            exit 0
        fi
        restore || exit 1
    fi
    current=$(prop system.slice AllowedCPUs) || exit 1
    if [ -n "$current" ]; then
        note "existing CPU policy retained"
        exit 0
    fi
    # Mark ownership before changing the property so stop can recover it.
    : > "$OWN" || exit 1
    if ! systemctl set-property --runtime system.slice AllowedCPUs=0-3 ||
       [ "$(cat /sys/fs/cgroup/system.slice/cpuset.cpus.effective 2>/dev/null)" != 0-3 ] ||
       ! audio_ready; then
        note "CPU isolation verification failed; restoring"
        restore || note "restore failed: manual recovery required"
        exit 1
    fi
    note "background CPU set applied; audio remains on CPUs 0-7"
    ;;
stop)
    restore
    ;;
*)
    exit 0
    ;;
esac
