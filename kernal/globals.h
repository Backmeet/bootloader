#pragma once
#include "../gnu-efi/inc/efi.h"
#include "../gnu-efi/inc/efilib.h"
#include <stdint.h>

static EFI_SYSTEM_TABLE* ST;
static EFI_BOOT_SERVICES* BS;
static EFI_HANDLE Image;