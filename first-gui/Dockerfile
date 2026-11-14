# Build-only, aarch64 diagnostic Wayland userspace for the SM-T575.
# This is intentionally NOT a boot image and has no install/flash commands.
FROM --platform=linux/arm64 alpine:3.22

RUN apk add --no-cache \
    busybox bash coreutils util-linux \
    dbus eudev seatd libinput libdrm \
    mesa-dri-gallium mesa-egl mesa-gles mesa-gbm \
    weston weston-backend-drm weston-backend-headless \
    weston-shell-desktop weston-clients weston-terminal \
    font-dejavu

COPY first-gui/preflight.sh /usr/local/sbin/t575-gui-preflight
RUN chmod 0755 /usr/local/sbin/t575-gui-preflight \
    && /bin/sh -n /usr/local/sbin/t575-gui-preflight \
    && mkdir -p /run /tmp /var/log /mnt \
    && apk info -vv > /usr/share/t575-gui-packages.txt

# No CMD or ENTRYPOINT is provided for boot: this image is a build container.
