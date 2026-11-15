/* SPDX-License-Identifier: MIT
 * Experimental SM-T575 kernel-side NFSv3 mount/read/unmount test.
 * USE ONLY after an explicitly approved experimental NFS-enabled kernel boot.
 * Never run against Android mountpoints or internal block devices.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>

#define TARGET "/mnt/t575-nfs-probe"
#define SOURCE "10.77.57.1:/Volumes/T575-Plasma/rootfs"
#define FILE_PATH TARGET "/usr/share/wayland-sessions/plasma-mobile.desktop"

static int nfs_supported(void)
{
    char line[128];
    FILE *f = fopen("/proc/filesystems", "r");
    int ok = 0;
    if (!f) return 0;
    while (fgets(line, sizeof(line), f)) {
        char *p = strrchr(line, '\t');
        if (p && (!strcmp(p + 1, "nfs\n") || !strcmp(p + 1, "nfs"))) {
            ok = 1;
            break;
        }
    }
    fclose(f);
    return ok;
}

int main(int argc, char **argv)
{
    static const char *options =
        "vers=3,proto=tcp,mountproto=tcp,mountport=1023,port=2049,"
        "nolock,ro,soft,timeo=30,retrans=2,addr=10.77.57.1";
    char data[257];
    int fd = -1, ret = 1;
    ssize_t got;
    if (argc != 2 || strcmp(argv[1], "--mount-readonly-test") != 0) {
        fprintf(stderr, "Usage: %s --mount-readonly-test\n", argv[0]);
        fprintf(stderr, "Requires experimental NFS-enabled kernel and host export.\n");
        return 2;
    }
    if (!nfs_supported()) {
        fprintf(stderr, "NFS not in /proc/filesystems; refusing mount attempt.\n");
        return 3;
    }
    if (mkdir("/mnt", 0755) < 0 && errno != EEXIST) {
        perror("mkdir /mnt");
        return 1;
    }
    if (mkdir(TARGET, 0700) < 0) {
        /* Require an unused test-only mountpoint, never reuse an existing path. */
        perror("mkdir private mountpoint (must not already exist)");
        return 1;
    }
    printf("Mounting %s READ-ONLY at %s\n", SOURCE, TARGET);
    fflush(stdout);
    if (mount(SOURCE, TARGET, "nfs",
              MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC,
              options) < 0) {
        perror("NFSv3 mount");
        goto cleanup_dir;
    }
    fd = open(FILE_PATH, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) {
        perror("open Plasma Mobile session file");
        goto cleanup_mount;
    }
    got = read(fd, data, sizeof(data) - 1);
    close(fd); fd = -1;
    if (got <= 0) {
        perror("read Plasma Mobile session file");
        goto cleanup_mount;
    }
    data[got] = 0;
    if (!strstr(data, "[Desktop Entry]")) {
        fputs("Unexpected first bytes of Plasma Mobile session file\n", stderr);
        goto cleanup_mount;
    }
    printf("PASS: read %zd bytes of Plasma Mobile session file over NFSv3.\n", got);
    ret = 0;
cleanup_mount:
    if (umount2(TARGET, 0) < 0) {
        perror("umount");
        ret = 1;
    }
cleanup_dir:
    if (rmdir(TARGET) < 0) {
        perror("rmdir");
        ret = 1;
    }
    puts("No Android partition or remote file modifications requested.");
    return ret;
}
