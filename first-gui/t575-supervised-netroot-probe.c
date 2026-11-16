/* SPDX-License-Identifier: MIT
 * SM-T575 experimental NFSv3 supervised read-only probe.
 * BUILD/REVIEW ONLY until a recoverable NFS-enabled diagnostic kernel is approved.
 * It NEVER switches PID 1, launches Plasma, writes partitions or flashes BOOT.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define ROOT "/mnt/t575-netroot-supervised"
#define SOURCE "10.77.57.1:/Volumes/T575-Plasma/rootfs"
#define SESSION ROOT "/usr/share/wayland-sessions/plasma-mobile.desktop"
#define TIMEOUT_SECONDS 25

static int has_nfs(void)
{
    FILE *f = fopen("/proc/filesystems", "r");
    char line[128];
    int found = 0;
    if (!f) return 0;
    while (fgets(line, sizeof(line), f)) {
        char first[32] = "", second[32] = "";
        int fields = sscanf(line, " %31s %31s", first, second);
        const char *type = fields == 2 ? second : first;
        if (fields >= 1 && strcmp(type, "nfs") == 0) {
            found = 1;
            break;
        }
    }
    fclose(f);
    return found;
}

static int child_probe(void)
{
    const char *options =
        "vers=3,proto=tcp,mountproto=tcp,mountport=1023,port=2049,"
        "nolock,ro,soft,timeo=10,retrans=1,addr=10.77.57.1";
    int fd = -1, mounted = 0, made = 0, status = 1;
    char buf[512];
    ssize_t n;

    if (mkdir("/mnt", 0755) != 0 && errno != EEXIST) {
        perror("mkdir /mnt");
        return 1;
    }
    /* A pre-existing target is an error, even if it looks harmless. */
    if (mkdir(ROOT, 0700) != 0) {
        perror("mkdir dedicated mountpoint");
        return 1;
    }
    made = 1;
    if (mount(SOURCE, ROOT, "nfs",
              MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, options) != 0) {
        perror("NFSv3 mount");
        goto out;
    }
    mounted = 1;
    fd = open(SESSION, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) {
        perror("open Plasma Mobile session descriptor");
        goto out;
    }
    n = read(fd, buf, sizeof(buf) - 1);
    if (n <= 0) {
        perror("read Plasma Mobile session descriptor");
        goto out;
    }
    buf[n] = '\0';
    if (!strstr(buf, "[Desktop Entry]")) {
        fputs("Session descriptor did not contain [Desktop Entry]\\n", stderr);
        goto out;
    }
    printf("PASS: read %zd bytes over read-only NFSv3; diagnostic PID 1 preserved\\n", n);
    status = 0;
out:
    if (fd >= 0) close(fd);
    if (mounted && umount2(ROOT, 0) != 0) {
        perror("umount NFS");
        status = 1;
    }
    if (made && rmdir(ROOT) != 0) {
        perror("remove temporary mountpoint");
        status = 1;
    }
    return status;
}

int main(int argc, char **argv)
{
    pid_t pid;
    int status = 0, i;
    struct timespec delay = {.tv_sec = 0, .tv_nsec = 100000000L};

    if (argc != 2 || strcmp(argv[1], "--probe-readonly") != 0) {
        fprintf(stderr, "Usage: %s --probe-readonly\\n", argv[0]);
        fputs("UNTESTED; requires explicitly approved NFS-enabled kernel. No Plasma launch.\\n", stderr);
        return 2;
    }
    if (getpid() == 1) {
        fputs("Refusing to replace diagnostic PID 1\\n", stderr);
        return 2;
    }
    if (!has_nfs()) {
        fputs("NFS not registered in /proc/filesystems; refusing.\\n", stderr);
        return 3;
    }

    fflush(NULL);
    pid = fork();
    if (pid < 0) { perror("fork"); return 1; }
    if (pid == 0) {
        int rc = child_probe();
        fflush(NULL);
        _exit(rc);
    }

    for (i = 0; i < TIMEOUT_SECONDS * 10; i++) {
        pid_t w = waitpid(pid, &status, WNOHANG);
        if (w == pid) {
            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) return 0;
            fprintf(stderr, "Probe child exited unsuccessfully (wait status %d)\\n", status);
            return 1;
        }
        if (w < 0) { perror("waitpid"); return 1; }
        nanosleep(&delay, NULL);
    }
    fputs("TIMEOUT: terminating probe child; diagnostic PID 1 remains active.\\n", stderr);
    kill(pid, SIGKILL);
    /* In uninterruptible NFS I/O, SIGKILL may not complete immediately.
       Never block the parent indefinitely waiting for the child. */
    for (i = 0; i < 20; i++) {
        if (waitpid(pid, &status, WNOHANG) == pid) break;
        nanosleep(&delay, NULL);
    }
    /* Deliberately no forced unmount here: a stuck child may still be in mount().
       Recovery must not touch unrelated mounts or Android partitions. */
    return 124;
}
