import subprocess
from pathlib import Path
import struct
import math

ROOT = Path(__file__).parent
BIN = ROOT / "bin"

BOOT_EFI = BIN / "BOOTX64.EFI"
KERNEL = BIN / "kernel.elf"
IMG = BIN / "disk.img"

BIN.mkdir(exist_ok=True)

def run(cmd):
    subprocess.check_call([str(x) for x in cmd])

def build_bootloader():

    startup_o = BIN / "startup.o"
    boot_o = BIN / "boot.o"
    boot_so = BIN / "bootloader.so"

    run([
        "gcc","-c","boot/starup.c",
        "-ffreestanding","-fno-stack-protector",
        "-fpic","-mno-red-zone","-m64",
        "-Ignu-efi/inc","-Ignu-efi/inc/x86_64",
        "-o",startup_o
    ])

    run([
        "nasm","-f","elf64",
        "boot/boot.s",
        "-o",boot_o
    ])

    run([
        "ld",
        str(boot_o),str(startup_o),
        "gnu-efi/x86_64/crt0-efi-x86_64.o",
        "-nostdlib",
        "-T","gnu-efi/gnuefi/elf_x86_64_efi.lds",
        "-shared","-Bsymbolic",
        "-L","gnu-efi/x86_64/lib",
        "-lefi","-lgnuefi",
        "-o",boot_so
    ])

    run([
        "objcopy",
        "-j",".text","-j",".sdata","-j",".data",
        "-j",".dynamic","-j",".dynsym",
        "-j",".rel","-j",".rela","-j",".reloc",
        "--target=efi-app-x86_64",
        boot_so,
        BOOT_EFI
    ])

def build_kernel():

    kernel_o = BIN/"kernel.o"

    run([
        "gcc",
        "-ffreestanding",
        "-m64",
        "-c","kernal/kernal.c",
        "-o",kernel_o
    ])

    run([
        "ld",
        kernel_o,
        "-nostdlib",
        "-Ttext","0x100000",
        "-o",KERNEL
    ])

def create_fat32():

    size = 64*1024*1024
    sector = 512
    sectors = size//sector

    reserved = 32
    fat_size = 512
    fats = 2
    spc = 8

    fat_start = reserved
    data_start = reserved + fat_size*fats

    cluster_bytes = spc*sector

    with open(IMG,"wb") as f:
        f.truncate(size)

    with open(IMG,"r+b") as f:

        boot = bytearray(512)

        boot[0:3] = b'\xEB\x58\x90'
        boot[3:11] = b"MSWIN4.1"

        struct.pack_into("<H",boot,11,512)
        boot[13] = spc
        struct.pack_into("<H",boot,14,reserved)

        boot[16] = fats
        struct.pack_into("<H",boot,17,0)
        struct.pack_into("<H",boot,19,0)

        boot[21] = 0xF8
        struct.pack_into("<H",boot,22,0)

        struct.pack_into("<H",boot,24,63)
        struct.pack_into("<H",boot,26,255)

        struct.pack_into("<I",boot,28,0)
        struct.pack_into("<I",boot,32,sectors)

        struct.pack_into("<I",boot,36,fat_size)

        struct.pack_into("<H",boot,40,0)
        struct.pack_into("<H",boot,42,0)

        struct.pack_into("<I",boot,44,2)

        struct.pack_into("<H",boot,48,1)
        struct.pack_into("<H",boot,50,6)

        boot[64]=0x80
        boot[66]=0x29

        struct.pack_into("<I",boot,67,123456)

        boot[71:82]=b"BOOTDISK   "
        boot[82:90]=b"FAT32   "

        boot[510]=0x55
        boot[511]=0xAA

        f.seek(0)
        f.write(boot)

        fat = bytearray(fat_size*sector)

        struct.pack_into("<I",fat,0,0x0FFFFFF8)
        struct.pack_into("<I",fat,4,0xFFFFFFFF)
        struct.pack_into("<I",fat,8,0x0FFFFFFF)

        def cluster_to_offset(c):
            return (data_start + (c-2)*spc)*sector

        def write_cluster(c,data):
            off = cluster_to_offset(c)
            f.seek(off)
            f.write(data.ljust(cluster_bytes,b'\x00'))

        def alloc_file(data,start_cluster):

            clusters = math.ceil(len(data)/cluster_bytes)
            first = start_cluster

            for i in range(clusters):
                c = start_cluster+i

                chunk = data[i*cluster_bytes:(i+1)*cluster_bytes]
                write_cluster(c,chunk)

                if i==clusters-1:
                    struct.pack_into("<I",fat,c*4,0x0FFFFFFF)
                else:
                    struct.pack_into("<I",fat,c*4,c+1)

            return first, start_cluster+clusters

        def dir_entry(name,cluster,size,attr):

            e = bytearray(32)

            n,ext=(name.split(".")+[""])[:2]
            n=n.upper().ljust(8)
            ext=ext.upper().ljust(3)

            e[0:8]=n.encode()
            e[8:11]=ext.encode()

            e[11]=attr

            struct.pack_into("<H",e,20,cluster>>16)
            struct.pack_into("<H",e,26,cluster&0xFFFF)

            struct.pack_into("<I",e,28,size)

            return e

        with open(BOOT_EFI,"rb") as f2:
            efi=f2.read()

        with open(KERNEL,"rb") as f2:
            kern=f2.read()

        cluster=3

        efi_cluster,cluster = alloc_file(efi,cluster)
        kern_cluster,cluster = alloc_file(kern,cluster)

        boot_cluster = cluster
        boot_dir = bytearray(cluster_bytes)
        boot_dir[0:32]=dir_entry("BOOTX64.EFI",efi_cluster,len(efi),0x20)
        write_cluster(boot_cluster,boot_dir)
        struct.pack_into("<I",fat,boot_cluster*4,0x0FFFFFFF)
        cluster+=1

        efi_cluster_dir = cluster
        efi_dir = bytearray(cluster_bytes)
        efi_dir[0:32]=dir_entry("BOOT",boot_cluster,0,0x10)
        write_cluster(efi_cluster_dir,efi_dir)
        struct.pack_into("<I",fat,efi_cluster_dir*4,0x0FFFFFFF)
        cluster+=1

        root_cluster = 2
        root = bytearray(cluster_bytes)
        root[0:32]=dir_entry("EFI",efi_cluster_dir,0,0x10)
        root[32:64]=dir_entry("KERNEL.ELF",kern_cluster,len(kern),0x20)
        write_cluster(root_cluster,root)

        f.seek(fat_start*sector)
        f.write(fat)

        f.seek((fat_start+fat_size)*sector)
        f.write(fat)

def run_qemu():

    run([
        "qemu-system-x86_64",
        "-bios","OVMF.fd",
        "-drive",f"format=raw,file={IMG}"
    ])

if __name__ == "__main__":

    build_bootloader()
    build_kernel()
    create_fat32()
    run_qemu()