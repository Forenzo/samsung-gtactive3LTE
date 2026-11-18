/* SM-T575 diagnostic transport v1: RAM-only receive test, NO DEVICE WRITES.
 * Cross-compile: aarch64-linux-gnu-gcc -O2 -Wall -Wextra -static -o t575-receiver t575-receiver.c
 * Runs as a background daemon because the existing initramfs console kills
 * direct 'run' children after 60 seconds.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define PORT 23456
#define MAX_BYTES (1024u * 1024u)
#define MAGIC "T575RAM1"
static uint32_t crc32_update(uint32_t crc, const unsigned char *p, size_t n) {
    for (size_t i=0; i<n; i++) {
        crc ^= p[i];
        for (int j=0; j<8; j++) crc = (crc>>1) ^ (0xEDB88320u & -(int)(crc&1));
    }
    return crc;
}
static int recvall(int fd, unsigned char *dst, size_t n) {
    while (n) { ssize_t got=recv(fd,dst,n,0); if(got<=0) return -1; dst+=got; n-=(size_t)got; }
    return 0;
}
static void handle(int c) {
    unsigned char hdr[12], buffer[16384], out[4];
    if (recvall(c,hdr,sizeof(hdr))) return;
    if (memcmp(hdr,MAGIC,8)) return;
    uint32_t bytes = ((uint32_t)hdr[8]<<24)|((uint32_t)hdr[9]<<16)|((uint32_t)hdr[10]<<8)|hdr[11];
    if(bytes==0 || bytes>MAX_BYTES) return;
    uint32_t crc=0xFFFFFFFFu;
    uint32_t left=bytes;
    while(left) { size_t n=left<sizeof(buffer)?left:sizeof(buffer);
       if(recvall(c,buffer,n)) return;
       crc=crc32_update(crc,buffer,n); left-=(uint32_t)n;
    }
    crc ^= 0xFFFFFFFFu;
    out[0]=(unsigned char)(crc>>24);out[1]=(unsigned char)(crc>>16);
    out[2]=(unsigned char)(crc>>8);out[3]=(unsigned char)crc;
    (void)send(c,out,4,MSG_NOSIGNAL);
}
static int server(void) {
    int s=socket(AF_INET6,SOCK_STREAM,0); if(s<0) return 3;
    int yes=1; setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    struct sockaddr_in6 a={0};a.sin6_family=AF_INET6; a.sin6_port=htons(PORT);a.sin6_addr=in6addr_any;
    if(bind(s,(struct sockaddr *)&a,sizeof(a))<0 || listen(s,2)<0) {close(s);return 4;}
    for (;;) {int c=accept(s,NULL,NULL);if(c<0){if(errno==EINTR)continue;break;}
       struct timeval tv={.tv_sec=45};setsockopt(c,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
       setsockopt(c,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));handle(c);close(c);
    }
    close(s);return 5;
}
int main(int argc,char **argv) {
    if(argc!=2 || strcmp(argv[1],"--start")) {
       puts("SM-T575 RAM-only receiver v1; usage: t575-receiver --start");return 2;
    }
    pid_t p=fork();if(p<0)return 2;
    if(p>0){puts("RAM-only transport daemon launched (TCP/23456, max 1 MiB, no disk writes)");return 0;}
    if(setsid()<0)_exit(2);
    p=fork();if(p<0)_exit(2);if(p>0)_exit(0);
    signal(SIGHUP,SIG_IGN);signal(SIGPIPE,SIG_IGN);
    int devnull=open("/dev/null",O_RDWR);if(devnull>=0){dup2(devnull,0);dup2(devnull,1);dup2(devnull,2);if(devnull>2)close(devnull);}
    _exit(server());
}
