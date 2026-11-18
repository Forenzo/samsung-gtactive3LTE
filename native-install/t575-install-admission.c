/* SM-T575 Native Installer v2: hardware admission only; FAIL-CLOSED, NO WRITES. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <unistd.h>
#define SIZE 55461281792ULL
static int readtext(const char *path,char *buf,size_t n){FILE*f=fopen(path,"rb");if(!f)return -1;size_t k=fread(buf,1,n-1,f);buf[k]=0;fclose(f);return 0;}
static int fail(const char *msg){fprintf(stderr,"BLOCKED: %s\n",msg);return 1;}
int main(void){
 char data[8192];
 if(readtext("/proc/device-tree/model",data,sizeof(data)))return fail("cannot read DT model");
 if(!strstr(data,"SM-T575"))return fail("unexpected device model");
 printf("PASS device model: %s\n",data);
 if(readtext("/sys/class/block/sda31/uevent",data,sizeof(data)))return fail("no UFS userdata device");
 if(!strstr(data,"PARTNAME=userdata"))return fail("sda31 not userdata");
 if(readtext("/proc/mounts",data,sizeof(data)))return fail("cannot read mount table");
 if(strstr(data,"/dev/sda31 ")||strstr(data,"/dev/block/sda31 "))return fail("userdata is mounted");
 int fd=open("/dev/sda31",O_RDONLY|O_CLOEXEC|O_NONBLOCK);if(fd<0)return fail("cannot open userdata read-only");
 uint64_t bytes=0;int sector=0;
 if(ioctl(fd,BLKGETSIZE64,&bytes)||ioctl(fd,BLKSSZGET,&sector)){close(fd);return fail("block ioctls unavailable");}
 close(fd);
 if(bytes!=SIZE||sector!=4096)return fail("userdata geometry mismatch");
 printf("PASS userdata /dev/sda31: %llu bytes, %d-byte sectors, unmounted\n",(unsigned long long)bytes,sector);
 puts("PASS installation target identity admission; NO DEVICE WRITES PERFORMED");
 puts("BLOCKED by design: v2 does not provide an install/write mode");
 return 0;
}
