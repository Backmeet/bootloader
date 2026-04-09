#include "../gnu-efi/inc/efi.h"
#include "../gnu-efi/inc/efilib.h"
#include <stdint.h>

typedef struct {
    unsigned char ident[16];
    uint16_t type;
    uint16_t machine;
    uint32_t version;
    uint64_t entry;
    uint64_t phoff;
    uint64_t shoff;
    uint32_t flags;
    uint16_t ehsize;
    uint16_t phentsize;
    uint16_t phnum;
    uint16_t shentsize;
    uint16_t shnum;
    uint16_t shstrndx;
} Elf64_Ehdr;

typedef struct {
    uint32_t type;
    uint32_t flags;
    uint64_t offset;
    uint64_t vaddr;
    uint64_t paddr;
    uint64_t filesz;
    uint64_t memsz;
    uint64_t align;
} Elf64_Phdr;

#define PT_LOAD 1

void* load_kernel_elf(EFI_HANDLE image, EFI_SYSTEM_TABLE* st) {
    EFI_BOOT_SERVICES* bs = st->BootServices;

    EFI_LOADED_IMAGE_PROTOCOL* loaded;
    EFI_SIMPLE_FILE_SYSTEM_PROTOCOL* fs;
    EFI_FILE_PROTOCOL* root;
    EFI_FILE_PROTOCOL* file;

    bs->HandleProtocol(
        image,
        &gEfiLoadedImageProtocolGuid,
        (void**)&loaded
    );

    bs->HandleProtocol(
        loaded->DeviceHandle,
        &gEfiSimpleFileSystemProtocolGuid,
        (void**)&fs
    );

    fs->OpenVolume(fs, &root);

    root->Open(
        root,
        &file,
        L"kernel.elf",
        EFI_FILE_MODE_READ,
        0
    );

    Elf64_Ehdr header;
    UINTN size = sizeof(header);

    file->Read(file, &size, &header);

    Elf64_Phdr* phdrs;

    bs->AllocatePool(
        EfiLoaderData,
        header.phnum * sizeof(Elf64_Phdr),
        (void**)&phdrs
    );

    file->SetPosition(file, header.phoff);

    size = header.phnum * sizeof(Elf64_Phdr);
    file->Read(file, &size, phdrs);

    for (uint64_t i = 0; i < header.phnum; i++) {
        if (phdrs[i].type != PT_LOAD)
            continue;

        uint64_t pages = (phdrs[i].memsz + 4095) / 4096;

        EFI_PHYSICAL_ADDRESS addr = phdrs[i].paddr;

        bs->AllocatePages(
            AllocateAddress,
            EfiLoaderData,
            pages,
            &addr
        );

        file->SetPosition(file, phdrs[i].offset);

        size = phdrs[i].filesz;
        file->Read(file, &size, (void*)addr);
    }

    return (void*)header.entry;
}

typedef void (*kernel_entry_t)(EFI_HANDLE, EFI_SYSTEM_TABLE*);

void entry(EFI_HANDLE image, EFI_SYSTEM_TABLE* st) {
    void* entry_addr = load_kernel_elf(image, st);

    kernel_entry_t kernel = (kernel_entry_t)entry_addr;

    kernel(image, st);

    while (1) {
        __asm__ __volatile__("hlt");
    }
}