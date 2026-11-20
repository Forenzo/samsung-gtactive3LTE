/* SM-T575 LTE explicit-armed USB userdata installer; v4. Only /dev/sda31.
 * Protocol uses link-local IPv6 and a per-session shared bearer token.
 * Each 1 MiB chunk is fdatasync'd, read back and CRC32 checked.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define TARGET 55461281792ULL
#define IMAGE 6862950400ULL
#define SECTOR 4096ULL
#define CHUNK 1048576U
#define PORT 23457
#define TOKENLEN 32
static const char magic[]="T575WR4!";

static uint32_t crc32(const unsigned char *p, size_t n) {
 uint32_t c=~0U;
 for(size_t i=0;i<n;i++) {c^=p[i];for(int j=0;j<8;j++)c=(c>>1)^(0xedb88320U & -(int)(c&1));}
 return ~c;
}
static int exact(int s,void *p,size_t n) {
 unsigned char *b=p;
 while(n){ssize_t r=recv(s,b,n,0);if(r<=0)return -1;b+=r;n-=(size_t)r;}
 return 0;
}
static int sendall(int s,const void *p,size_t n){
 const unsigned char*b=p;while(n){ssize_t r=send(s,b,n,MSG_NOSIGNAL);if(r<=0)return -1;b+=r;n-=(size_t)r;}return 0;
}
static uint32_t be32(const unsigned char*p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static uint64_t be64(const unsigned char*p){uint64_t v=0;for(int i=0;i<8;i++)v=(v<<8)|p[i];return v;}
static void put32(unsigned char*p,uint32_t v){for(int i=3;i>=0;i--){p[i]=(unsigned char)v;v>>=8;}}
static int readtext(const char*path,char*b,size_t size){FILE*f=fopen(path,"rb");if(!f)return -1;size_t n=fread(b,1,size-1,f);b[n]=0;fclose(f);return 0;}
static int authorize_device(void){
 char b[16384];
 if(readtext("/proc/device-tree/model",b,sizeof b)||!strstr(b,"SM-T575"))return -1;
 if(readtext("/sys/class/block/sda31/uevent",b,sizeof b)||!strstr(b,"PARTNAME=userdata"))return -1;
 /* Linux sysfs size uses 512-byte sectors even when logical block size is 4096. */
 if(readtext("/sys/class/block/sda31/size",b,sizeof b)||strtoull(b,NULL,10)!=(TARGET/512ULL))return -1;
 if(readtext("/sys/block/sda/queue/logical_block_size",b,sizeof b)||strtoul(b,NULL,10)!=SECTOR)return -1;
 if(readtext("/proc/mounts",b,sizeof b))return -1;
 if(strstr(b,"/dev/sda31 ")||strstr(b,"/dev/block/sda31 ")||strstr(b,"/dev/block/by-name/userdata "))return -1;
 return 0;
}
static int write_verify(int fd,uint64_t off,const unsigned char*src,uint32_t n,unsigned char*readback){
 if(n==0||n>CHUNK||n%SECTOR||off%SECTOR||off>TARGET||n>TARGET-off)return -1;
 if(pwrite(fd,src,n,(off_t)off)!=(ssize_t)n)return -1;
 if(fdatasync(fd))return -1;
 if(pread(fd,readback,n,(off_t)off)!=(ssize_t)n)return -1;
 return memcmp(src,readback,n)==0?0:-1;
}
static int session(int s,const char*token){
 unsigned char hdr[48],*buf=NULL,*check=NULL,resp[5]={0};
 int fd=-1;uint64_t off=0;int patches=0;int result=-1;
 struct timeval tv={.tv_sec=180};
 setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof tv);setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof tv);
 if(exact(s,hdr,sizeof hdr))goto done;
 if(memcmp(hdr,magic,8)||memcmp(hdr+8,token,TOKENLEN)||be64(hdr+40)!=IMAGE)goto done;
 if(authorize_device())goto done;
 fd=open("/dev/sda31",O_RDWR|O_CLOEXEC|O_SYNC|O_NOFOLLOW);
 if(fd<0)goto done;
 uint64_t bytes=0;int sec=0;
 if(ioctl(fd,BLKGETSIZE64,&bytes)||ioctl(fd,BLKSSZGET,&sec)||bytes!=TARGET||sec!=(int)SECTOR)goto done;
 buf=malloc(CHUNK);check=malloc(CHUNK);if(!buf||!check)goto done;
 if(sendall(s,"GO",2))goto done;
 while(1){
  unsigned char h[13];
  if(exact(s,h,13))goto done;
  if(h[0]=='D'){
   uint64_t at=be64(h+1);uint32_t n=be32(h+9);
   if(at!=off||off>=IMAGE||n==0||n>CHUNK||n%SECTOR||n>IMAGE-off||patches)goto done;
   if(exact(s,buf,n)||write_verify(fd,at,buf,n,check))goto done;
   uint32_t checksum=crc32(check,n);resp[0]='K';put32(resp+1,checksum);
   if(sendall(s,resp,5))goto done;
   off+=n;
  } else if(h[0]=='P') {
   static const uint64_t patch_offs[4]={0,4096,55461261312ULL,55461277696ULL};
   static const uint32_t patch_sizes[4]={4096,4096,16384,4096};
   uint64_t at=be64(h+1);uint32_t n=be32(h+9);
   if(off!=IMAGE||patches>=4||at!=patch_offs[patches]||n!=patch_sizes[patches])goto done;
   if(exact(s,buf,n)||write_verify(fd,at,buf,n,check))goto done;
   uint32_t checksum=crc32(check,n);resp[0]='K';put32(resp+1,checksum);
   if(sendall(s,resp,5))goto done;
   patches++;
  } else if(h[0]=='F'){
   if(be64(h+1)!=0||be32(h+9)!=0||off!=IMAGE||patches!=4||fsync(fd))goto done;
   if(sendall(s,"DONE",4))goto done;
   result=0;goto done;
  }else goto done;
 }
 done:
 if(fd>=0)close(fd);
 free(buf);
 free(check);
 return result;
}
static int server(const char*token){
 int sock=socket(AF_INET6,SOCK_STREAM,0);if(sock<0)return 3;
 int yes=1;setsockopt(sock,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof yes);
 struct sockaddr_in6 bindaddr={0};bindaddr.sin6_family=AF_INET6;bindaddr.sin6_port=htons(PORT);bindaddr.sin6_addr=in6addr_any;
 if(bind(sock,(struct sockaddr*)&bindaddr,sizeof bindaddr)||listen(sock,1)){close(sock);return 4;}
 struct sockaddr_in6 peer; socklen_t plen=sizeof peer;
 int c=accept(sock,(struct sockaddr*)&peer,&plen);close(sock);
 if(c<0)return 5;
 int result=-1;
 if(IN6_IS_ADDR_LINKLOCAL(&peer.sin6_addr))result=session(c,token);
 close(c);return result?6:0;
}
int main(int argc,char**argv){
 if(argc!=3||strcmp(argv[1],"--arm")||strlen(argv[2])!=TOKENLEN){
  puts("SM-T575 v4 writer (explicitly destructive): t575-writer-v4 --arm 32_HEX_CHARACTERS");return 2;
 }
 for(int i=0;i<TOKENLEN;i++)if(!((argv[2][i]>='0'&&argv[2][i]<='9')||(argv[2][i]>='a'&&argv[2][i]<='f')))return 2;
 if(authorize_device()){puts("BLOCKED: tablet model, unmounted userdata, or geometry mismatch");return 3;}
 pid_t p=fork();if(p<0)return 4;
 if(p>0){puts("ARMED: single-session userdata writer listening on TCP/23457. NO WRITES UNTIL AUTHENTICATED HOST CONNECTS.");return 0;}
 if(setsid()<0)_exit(4);
 p=fork();
 if(p<0)_exit(4);
 if(p>0)_exit(0);
 int dn=open("/dev/null",O_RDWR);if(dn>=0){dup2(dn,0);dup2(dn,1);dup2(dn,2);if(dn>2)close(dn);}
 _exit(server(argv[2]));
}
