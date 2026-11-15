/* SPDX-License-Identifier: MIT
 * Read-only MOUNTv3 MNT + NFSv3 GETATTR probe over USB TCP.
 * Does NOT call mount(2), alter partitions, or write remote files.
 * mountd TCP port 1023 is from the owner's 2026-11-15 rpcinfo result;
 * rerun rpcinfo and adjust if the Mac's mountd port changes.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define LIMIT 8192
#define PATH "/Volumes/T575-Plasma/rootfs"
static unsigned char buf[LIMIT], reply[LIMIT];
static size_t pos;

static void word(uint32_t v) {
    uint32_t n = htonl(v);
    if (pos + 4 > LIMIT) { fputs("Request too big\n", stderr); exit(2); }
    memcpy(buf + pos, &n, 4); pos += 4;
}
static void bytes(const void *data, size_t n) {
    size_t rounded = (n + 3) & ~(size_t)3;
    if (pos + rounded > LIMIT) { fputs("Request too big\n", stderr); exit(2); }
    memset(buf + pos, 0, rounded);
    memcpy(buf + pos, data, n);
    pos += rounded;
}
static uint32_t getword(const unsigned char *data, size_t n, size_t *off) {
    uint32_t v;
    if (*off + 4 > n) { fputs("Truncated RPC response\n", stderr); exit(2); }
    memcpy(&v, data + *off, 4); *off += 4;
    return ntohl(v);
}
static int exact(int fd, unsigned char *dst, size_t n) {
    while (n) {
        ssize_t r = recv(fd, dst, n, 0);
        if (r <= 0) return -1;
        dst += r; n -= (size_t)r;
    }
    return 0;
}
static int sendall(int fd, const unsigned char *data, size_t n) {
    while (n) {
        ssize_t r = send(fd, data, n, 0);
        if (r <= 0) return -1;
        data += r; n -= (size_t)r;
    }
    return 0;
}
static int rpc(int port, int program, int version, int procedure,
               const unsigned char *payload, size_t plen,
               size_t *body, size_t *rlen) {
    int fd = -1, result = -1;
    struct sockaddr_in addr, local;
    struct timeval timeout = {3, 0};
    uint32_t mark;
    size_t off = 0;
    static const uint32_t xid = 0x57502026;
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    memset(&addr, 0, sizeof(addr)); addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    inet_pton(AF_INET, "10.77.57.1", &addr.sin_addr);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) goto done;
    pos = 0;
    word(xid); word(0); word(2); /* CALL, RPCv2 */
    word((uint32_t)program); word((uint32_t)version); word((uint32_t)procedure);
    /* AUTH_SYS, uid=0 gid=0, hostname t575, no supplementary groups */
    word(1); word(24);
    word(0); word(4); bytes("t575", 4);
    word(0); word(0); word(0);
    /* Verifier AUTH_NULL */
    word(0); word(0);
    if (pos + plen > LIMIT) goto done;
    memcpy(buf + pos, payload, plen); pos += plen;
    mark = htonl(0x80000000u | (uint32_t)pos);
    if (sendall(fd, (unsigned char *)&mark, 4) < 0 ||
        sendall(fd, buf, pos) < 0) goto done;
    if (exact(fd, (unsigned char *)&mark, 4) < 0) goto done;
    mark = ntohl(mark);
    if (!(mark & 0x80000000u) || (mark & 0x7fffffffu) > LIMIT) goto done;
    *rlen = mark & 0x7fffffffu;
    if (exact(fd, reply, *rlen) < 0) goto done;
    if (getword(reply, *rlen, &off) != xid ||
        getword(reply, *rlen, &off) != 1 ||
        getword(reply, *rlen, &off) != 0) goto done;
    /* skip reply verifier safely */
    (void)getword(reply, *rlen, &off);
    uint32_t vlen = getword(reply, *rlen, &off);
    if (vlen > LIMIT || off + ((vlen + 3u) & ~3u) > *rlen) goto done;
    off += (vlen + 3u) & ~3u;
    if (getword(reply, *rlen, &off) != 0) goto done;
    *body = off;
    result = 0;
done:
    close(fd);
    return result;
}
int main(void) {
    size_t base, size, offset;
    unsigned char payload[256], handle[64];
    size_t handle_len;
    unsigned int status;
    const char *path = PATH;
    size_t len = strlen(path);
    printf("Read-only NFSv3 RPC probe: %s\n", path);
    pos = 0; word((uint32_t)len); bytes(path, len);
    memcpy(payload, buf, pos);
    if (rpc(1023, 100005, 3, 1, payload, pos, &base, &size)) {
        puts("MOUNTv3 RPC communication failed (mountd port may have changed)");
        return 1;
    }
    offset = base;
    status = getword(reply, size, &offset);
    if (status) {
        printf("MOUNTv3 MNT denied: status %u\n", status);
        return 1;
    }
    handle_len = getword(reply, size, &offset);
    if (!handle_len || handle_len > sizeof(handle) || offset + handle_len > size) {
        puts("Invalid NFS file handle length");
        return 1;
    }
    memcpy(handle, reply + offset, handle_len);
    printf("MOUNTv3 MNT authorized; root file handle length %zu\n", handle_len);
    pos = 0; word((uint32_t)handle_len); bytes(handle, handle_len);
    memcpy(payload, buf, pos);
    if (rpc(2049, 100003, 3, 1, payload, pos, &base, &size)) {
        puts("NFSv3 GETATTR RPC communication failed");
        return 1;
    }
    offset = base;
    status = getword(reply, size, &offset);
    if (status) {
        printf("NFSv3 GETATTR denied: status %u\n", status);
        return 1;
    }
    printf("NFSv3 GETATTR success: root type %u\n", getword(reply, size, &offset));
    puts("PASS: export authorization and read-only NFS metadata access work.");
    puts("NO mount, data transfer, remote write, or kernel switch performed.");
    return 0;
}
