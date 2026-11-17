// SPDX-License-Identifier: MIT
// SM-T575 LTE: one-shot Plasma desktop from the owner's read-only Mac NFS tree.
// No Android/internal partition access. Invoke via diagnostic console run.
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <mntent.h>
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

#define ROOT "/mnt/t575-plasma-gui-v2"
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
/*
 * RO NFS: mkdir() is forbidden even if the directory was just created
 * on macOS but is temporarily invisible in an older NFS dentry cache.
 * The Mac host pre-creates all 7 targets. Validate them before submounts.
 */
static void verify_nfs_mountpoints(void) {
    const char *names[] = { "proc", "sys", "dev", "run", "tmp", "home", "var" };
    char dest[256];
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
        struct stat st;
        snprintf(dest, sizeof(dest), ROOT "/%s", names[i]);
        if (lstat(dest, &st) < 0 || !S_ISDIR(st.st_mode)) {
            msg("FAIL: NFS export missing directory %s; Mac host must create it before mounting\n", dest);
            _exit(2);
        }
    }
    msg("PASS: seven NFS mountpoints visible without filesystem writes\n");
}
static void mount_bind(const char *src, const char *name) {
    char dest[256];
    snprintf(dest, sizeof(dest), ROOT "/%s", name);
    must(mount(src, dest, NULL, MS_BIND | MS_REC, NULL), "bind mount");
}
static void mount_tmp(const char *name, const char *opts) {
    char dest[256];
    snprintf(dest, sizeof(dest), ROOT "/%s", name);
    must(mount("tmpfs", dest, "tmpfs", MS_NOSUID | MS_NODEV, opts), "RAM tmpfs");
}
/* The diagnostic console leaves a successful NFS mount in place when a
 * subsequent step fails. Reuse only the identical READ-ONLY NFSv3 export
 * at the NEW mount path, not the prior stale /mnt/t575-plasma mount.
 * Never unmount or replace anything we do not recognize.
 */
static int existing_nfs_root(void) {
    FILE *m = setmntent("/proc/mounts", "r");
    if (!m) return -1;
    struct mntent *e;
    int result = 0;
    while ((e = getmntent(m))) {
        if (strcmp(e->mnt_dir, ROOT)) continue;
        if (strcmp(e->mnt_fsname, SOURCE) ||
            strcmp(e->mnt_type, "nfs") ||
            !hasmntopt(e, "ro")) {
            result = -1;  /* unexpected or writable mount: refuse */
        } else {
            result = 1;
        }
        break;
    }
    endmntent(m);
    return result;
}
/* Avoid glibc NSS/module lookups in a statically linked launcher after
 * entering an Alpine (musl-based) rootfs. We only need the known local
 * account that the Mac script explicitly prepared.
 */
static int guest_account_present(void) {
    FILE *fp = fopen("/etc/passwd", "r");
    char line[1024];
    int found = 0;
    if (!fp) { msg("FAIL: cannot read guest /etc/passwd: %s\n", strerror(errno)); return 0; }
    while (fgets(line, sizeof(line), fp)) {
        if (!strncmp(line, "t575:x:1000:1000:", sizeof("t575:x:1000:1000:") - 1)) {
            found = 1;
            break;
        }
    }
    fclose(fp);
    return found;
}
static int guest_supplementary_groups(gid_t ids[], size_t capacity) {
    FILE *fp = fopen("/etc/group", "r");
    char line[1024];
    int count = 0;
    if (!fp) { msg("FAIL: cannot read guest /etc/group: %s\n", strerror(errno)); return -1; }
    while (fgets(line, sizeof(line), fp)) {
        char *colon = strchr(line, ':');
        if (!colon) continue;
        *colon++ = '\0';
        if (strcmp(line, "video") && strcmp(line, "input") && strcmp(line, "render")) continue;
        char *gid_field = strchr(colon, ':');
        if (!gid_field) continue;
        gid_field++;
        char *end = NULL;
        errno = 0;
        unsigned long val = strtoul(gid_field, &end, 10);
        if (errno || !end || *end != ':' || val > 65535UL) continue;
        if ((size_t)count < capacity) ids[count++] = (gid_t)val;
    }
    fclose(fp);
    return count;
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
    int present = existing_nfs_root();
    if (present < 0) {
        msg("FAIL: %s already has an unexpected/writable mount\n", ROOT);
        _exit(2);
    }
    if (present == 1) {
        msg("PASS: reusing already-mounted READ-ONLY NFS rootfs\n");
    } else {
        if (mount(SOURCE, ROOT, "nfs", MS_RDONLY | MS_NOSUID | MS_NODEV, options) < 0) {
            if (errno != EBUSY || existing_nfs_root() != 1)
                must(-1, "NFS mount");
            msg("PASS: reusing existing READ-ONLY NFS rootfs\n");
        } else {
            msg("PASS: remote rootfs mounted READ ONLY\n");
        }
    }
    if (access(ROOT "/usr/bin/startplasma-wayland", X_OK) < 0) {
        msg("FAIL: Plasma Mobile session not installed\n"); _exit(3);
    }
    verify_nfs_mountpoints();
    mount_bind("/proc", "proc"); mount_bind("/sys", "sys"); mount_bind("/dev", "dev");
    mount_tmp("run", "size=64m,mode=0755");
    mount_tmp("tmp", "size=256m,mode=1777");
    mount_tmp("home", "size=512m,mode=0755");
    mount_tmp("var", "size=128m,mode=0755");
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
    msg("Checking guest account directly in Alpine /etc/passwd\n");
    if (!guest_account_present()) {
        msg("FAIL: t575 uid 1000 account missing from /etc/passwd; run Mac preparation\n"); _exit(3);
    }
    msg("PASS: guest t575 uid 1000 present\n");
    static const char *const udev[] = {"/sbin/udevd","--daemon",NULL};
    static const char *const seat[] = {"/usr/bin/seatd","-g","video",NULL};
    static const char *const dbus[] = {"/usr/bin/dbus-daemon","--system","--nofork",NULL};
    static const char *const trigger[] = {"/sbin/udevadm","trigger","--action=add",NULL};
    msg("Starting graphical seat and IPC services\n");
    if (!access(udev[0], X_OK)) spawn(udev);
    if (!access(seat[0], X_OK)) spawn(seat);
    else { msg("FAIL: seatd missing\n"); _exit(3); }
    if (!access(dbus[0], X_OK)) spawn(dbus);
    if (!access(trigger[0], X_OK)) spawn(trigger);
    msg("PASS: seatd / D-Bus launch requested\n");
    sleep(3);
    gid_t groups[3];
    int ngroups = guest_supplementary_groups(groups, 3);
    if (ngroups < 0) _exit(3);
    msg("PASS: parsed %d device-access groups from /etc/group\n", ngroups);
    must(setgroups(ngroups, groups), "guest groups");
    must(setgid(DESKTOP_GID), "guest gid"); must(setuid(DESKTOP_UID), "guest uid");
    msg("PASS: switched to unprivileged uid 1000 for Plasma\n");
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
