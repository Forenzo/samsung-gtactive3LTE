// SPDX-License-Identifier: MIT
// SM-T575 LTE: one-shot Plasma desktop from the owner's read-only Mac NFS tree.
// No Android/internal partition access. Invoke via diagnostic console run.
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <net/if.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define ROOT "/mnt/t575-plasma"
#define SOURCE "10.77.57.1:/Volumes/T575-Plasma/rootfs"
#define LOG "/t575-plasma-desktop.log"
#define DESKTOP_UID 1000
#define DESKTOP_GID 1000

static void msg(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    fflush(stderr);
}
static void must(int rc, const char *what) {
    if (rc < 0) { msg("FAIL: %s: %s\n", what, strerror(errno)); _exit(2); }
}
static void mkdir_ok(const char *path, mode_t mode) {
    if (mkdir(path, mode) < 0 && errno != EEXIST) must(-1, path);
}
static void mount_bind(const char *src, const char *name) {
    char dest[256];
    snprintf(dest, sizeof(dest), ROOT "/%s", name);
    mkdir_ok(dest, 0755);
    must(mount(src, dest, NULL, MS_BIND | MS_REC, NULL), "bind mount");
}
static void mount_tmp(const char *name, const char *opts, mode_t mode) {
    char dest[256];
    snprintf(dest, sizeof(dest), ROOT "/%s", name);
    mkdir_ok(dest, mode);
    must(mount("tmpfs", dest, "tmpfs", MS_NOSUID | MS_NODEV, opts), "RAM tmpfs");
}
static void configure_usb_ipv4(void) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    must(sock, "socket IPv4");
    struct ifreq r = {0};
    strncpy(r.ifr_name, "usb0", IFNAMSIZ-1);
    struct sockaddr_in a = {.sin_family=AF_INET};
    inet_pton(AF_INET, "10.77.57.2", &a.sin_addr);
    memcpy(&r.ifr_addr, &a, sizeof(a));
    must(ioctl(sock, SIOCSIFADDR, &r), "usb0 address");
    inet_pton(AF_INET, "255.255.255.252", &a.sin_addr);
    memcpy(&r.ifr_netmask, &a, sizeof(a));
    must(ioctl(sock, SIOCSIFNETMASK, &r), "usb0 netmask");
    must(ioctl(sock, SIOCGIFFLAGS, &r), "usb0 flags");
    r.ifr_flags |= IFF_UP | IFF_RUNNING;
    must(ioctl(sock, SIOCSIFFLAGS, &r), "usb0 up");
    close(sock);
}
static void spawn(const char *const argv[]) {
    pid_t child = fork();
    if (child < 0) { msg("fork %s failed\n", argv[0]); return; }
    if (!child) {
        execv(argv[0], (char *const *)argv);
        msg("exec %s: %s\n", argv[0], strerror(errno)); _exit(127);
    }
}
static void redirect_log(void) {
    int fd = open(LOG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) _exit(2);
    dup2(fd, 1); dup2(fd, 2); if (fd > 2) close(fd);
    fd = open("/dev/null", O_RDONLY);
    if (fd >= 0) { dup2(fd, 0); if (fd > 2) close(fd); }
}
static void launch(void) {
    msg("SM-T575 Plasma Mobile direct boot over USB/NFS\n");
    configure_usb_ipv4();
    mkdir_ok("/mnt", 0755); mkdir_ok(ROOT, 0755);
    const char *options = "vers=3,proto=tcp,mountproto=tcp,mountport=1023,port=2049,nolock,ro,soft,timeo=30,retrans=2,addr=10.77.57.1";
    must(mount(SOURCE, ROOT, "nfs", MS_RDONLY | MS_NOSUID | MS_NODEV, options), "NFS mount");
    msg("PASS: remote rootfs mounted READ ONLY\n");
    if (access(ROOT "/usr/bin/startplasma-wayland", X_OK) < 0) {
        msg("FAIL: Plasma Mobile session not installed\n"); _exit(3);
    }
    mount_bind("/proc", "proc"); mount_bind("/sys", "sys"); mount_bind("/dev", "dev");
    mount_tmp("run", "size=64m,mode=0755", 0755);
    mount_tmp("tmp", "size=256m,mode=1777", 01777);
    mount_tmp("home", "size=512m,mode=0755", 0755);
    mount_tmp("var", "size=128m,mode=0755", 0755);
    must(chroot(ROOT), "chroot"); must(chdir("/"), "chdir");
    mkdir_ok("/run/user", 0755); mkdir_ok("/run/user/1000", 0700);
    must(chown("/run/user/1000", DESKTOP_UID, DESKTOP_GID), "runtime chown");
    must(chmod("/run/user/1000", 0700), "runtime chmod");
    mkdir_ok("/run/dbus", 0755); mkdir_ok("/var/log", 0755);
    mkdir_ok("/var/lib", 0755); mkdir_ok("/home/t575", 0700);
    must(chown("/home/t575", DESKTOP_UID, DESKTOP_GID), "home chown");
    if (access("/dev/dri/card0", F_OK) < 0) {
        msg("FAIL: Exynos DRM /dev/dri/card0 is absent\n"); _exit(3);
    }
    msg("DRM card0 ready; GPU render node %s\n",
        access("/dev/dri/renderD128", F_OK) ? "ABSENT" : "PRESENT");
    if (!getpwuid(DESKTOP_UID)) {
        msg("FAIL: guest uid 1000 missing from /etc/passwd; run Mac preparation\n"); _exit(3);
    }
    static const char *const udev[] = {"/sbin/udevd","--daemon",NULL};
    static const char *const seat[] = {"/usr/bin/seatd","-g","video",NULL};
    static const char *const dbus[] = {"/usr/bin/dbus-daemon","--system","--nofork",NULL};
    static const char *const trigger[] = {"/sbin/udevadm","trigger","--action=add",NULL};
    if (!access(udev[0], X_OK)) spawn(udev);
    if (!access(seat[0], X_OK)) spawn(seat);
    else { msg("FAIL: seatd missing\n"); _exit(3); }
    if (!access(dbus[0], X_OK)) spawn(dbus);
    if (!access(trigger[0], X_OK)) spawn(trigger);
    sleep(3);
    const char *names[] = {"video","input","render"};
    gid_t groups[3]; int ngroups = 0;
    for (size_t i = 0; i < 3; i++) {
        struct group *g = getgrnam(names[i]);
        if (g) groups[ngroups++] = g->gr_gid;
    }
    must(setgroups(ngroups, groups), "guest groups");
    must(setgid(DESKTOP_GID), "guest gid"); must(setuid(DESKTOP_UID), "guest uid");
    setenv("HOME","/home/t575",1);
    setenv("USER","t575",1); setenv("LOGNAME","t575",1);
    setenv("SHELL","/bin/sh",1);
    setenv("PATH","/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",1);
    setenv("XDG_RUNTIME_DIR","/run/user/1000",1);
    setenv("XDG_SESSION_TYPE","wayland",1);
    setenv("XDG_CURRENT_DESKTOP","KDE",1);
    setenv("XDG_SESSION_DESKTOP","plasma-mobile",1);
    setenv("QT_QPA_PLATFORM","wayland",1);
    setenv("KWIN_DRM_DEVICES","/dev/dri/card0",1);
    setenv("PAN_MESA_DEBUG","noafbc",1);
    msg("Starting full graphical Plasma Mobile session as uid 1000\n");
    static const char *const desktop[] = {
        "/usr/bin/dbus-run-session","--","/usr/bin/startplasma-wayland",NULL
    };
    execv(desktop[0], (char *const *)desktop);
    msg("FAIL: dbus-run-session: %s\n", strerror(errno)); _exit(4);
}
int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "--start")) {
        fprintf(stderr, "usage: %s --start\n", argv[0]); return 2;
    }
    // Console's 'run' has a 60-second limit. The desktop runs in a detached
    // descendant, while the command returns immediately.
    pid_t child = fork();
    if (child < 0) { perror("fork"); return 2; }
    if (child) {
        printf("Plasma desktop launch requested (PID %ld), log: %s\n",
               (long)child, LOG);
        return 0;
    }
    setsid(); redirect_log(); launch();
    return 1;
}
